"""python -m watcher {setup-telegram|setup-email|test-alerts|learn|watch}"""

import argparse
import getpass
import os
import smtplib
import sys
from pathlib import Path

from .config import (
    ConfigError,
    email_configured,
    load_captures,
    load_config,
    require_alerts,
    save_captures,
    telegram_configured,
)
from .email_alerts import Email
from .telegram import Telegram, TelegramError, call, find_chats


def _write_env(path, values):
    lines = path.read_text().splitlines() if path.exists() else []
    remaining = dict(values)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in remaining.items()]
    path.write_text("\n".join(out) + "\n")


def setup_telegram(_args):
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or input("Paste the bot token from @BotFather: ").strip()
    try:
        bot = call(token, "getMe")
    except TelegramError as e:
        sys.exit(f"That token didn't work: {e}")
    print(f"\nBot found: @{bot['username']}")
    input(f"In Telegram, open @{bot['username']}, tap Start (or send it any message), then press Enter here... ")

    chats = find_chats(token)
    if not chats:
        sys.exit("No messages found yet. Send the bot a message in Telegram and run this again.")
    if len(chats) == 1:
        chat_id, name = chats[0]
    else:
        for i, (cid, name) in enumerate(chats, 1):
            print(f"  {i}. {name} ({cid})")
        chat_id, name = chats[int(input("Which chat should get alerts? Number: ")) - 1]

    _write_env(Path(".env"), {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": str(chat_id)})
    Telegram(token, chat_id).send("✅ Visa slot watcher is connected. Alerts will arrive here.")
    print(f"Saved to .env. A test message was sent to {name}.")


def alert_channels(cfg):
    """(name, sender) for every alert channel that's set up."""
    channels = []
    if telegram_configured(cfg):
        channels.append(("Telegram", Telegram(cfg.telegram_bot_token, cfg.telegram_chat_id).send))
    if email_configured(cfg):
        email = Email(cfg.email_smtp_host, cfg.email_smtp_port, cfg.email_username, cfg.email_password, cfg.email_to)
        channels.append((f"email to {cfg.email_to}", email.send))
    return channels


def fan_out(channels):
    def notify(text):
        for _name, send in channels:
            send(text)

    return notify


def setup_email(_args):
    print(
        "Alerts are sent from your Gmail account to whichever address you choose.\n"
        "You need a Gmail *app password* (not your normal password):\n"
        "  1. Turn on 2-Step Verification: https://myaccount.google.com/signinoptions/twosv\n"
        "  2. Create an app password:      https://myaccount.google.com/apppasswords\n"
        "     (name it 'visa watcher'; Google shows a 16-letter password once)\n"
    )
    username = input("Your Gmail address: ").strip()
    password = getpass.getpass("App password (typing is hidden): ").replace(" ", "").strip()
    to = input(f"Send alerts to [{username}]: ").strip() or username

    try:
        Email("smtp.gmail.com", 587, username, password, to).deliver(
            "✅ Visa slot watcher email alerts are connected\nAlerts will arrive at this address."
        )
    except smtplib.SMTPAuthenticationError:
        sys.exit("Gmail rejected the login. Check the address and that you used an app password, then try again.")
    except (smtplib.SMTPException, OSError) as e:
        sys.exit(f"Couldn't send the test email: {e}")

    _write_env(Path(".env"), {"EMAIL_USERNAME": username, "EMAIL_PASSWORD": password, "EMAIL_TO": to})
    print(f"Saved to .env. A test email was sent to {to} (check spam the first time).")


def test_alerts(_args):
    cfg = load_config()
    require_alerts(cfg)
    failed = []
    for name, send in alert_channels(cfg):
        if send("🔔 Test alert from your visa slot watcher\nIf you can read this, alerts work."):
            print(f"Sent via {name}.")
        else:
            failed.append(name)
    if failed:
        sys.exit(f"Couldn't send via {', '.join(failed)}; see the error above.")


def learn(_args):
    from playwright.sync_api import sync_playwright

    from .browser import learn as run_learn

    cfg = load_config()
    with sync_playwright() as p:
        captures = run_learn(p, cfg)
    if not captures:
        sys.exit("\nNothing saved. Run learn again and open at least one calendar of available dates.")
    save_captures(cfg.captures_file, captures)
    print(f"\nSaved {len(captures)} location(s) to {cfg.captures_file}. Now run: python -m watcher watch")


def watch(_args):
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    from .browser import BrowserChecker, launch
    from .watch import Watcher

    cfg = load_config()
    require_alerts(cfg)
    captures = load_captures(cfg.captures_file)
    channels = alert_channels(cfg)
    notify = fan_out(channels)
    print("Alerts go to: " + ", ".join(name for name, _ in channels))

    stopped_by_user = False
    try:
        with sync_playwright() as p:
            context = launch(p, cfg)
            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(captures[0].page_url)
            except PlaywrightError as e:
                print(f"Couldn't open the portal yet ({e.message.splitlines()[0]}); will keep trying.")
            print("Watching. Keep the browser window open (minimizing is fine). Press Ctrl+C here to stop.\n")
            try:
                Watcher(cfg, captures, notify, BrowserChecker(page)).run()
            except KeyboardInterrupt:
                stopped_by_user = True
                notify("⏹️ Visa watcher stopped.")
            except PlaywrightError as e:
                notify("⏹️ Visa watcher stopped: the browser window was closed or crashed.")
                sys.exit(f"Browser error: {e}")
            except Exception as e:
                notify(f"⏹️ Visa watcher stopped with an error: {e}")
                raise
            context.close()
    except Exception:
        # Ctrl+C also stops Playwright's helper process, so cleanup can fail noisily. Ignore that.
        if not stopped_by_user:
            raise
    print("Stopped.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m watcher", description="Telegram/email alerts for earlier US visa slots.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup-telegram", help="connect your Telegram bot (one time)").set_defaults(fn=setup_telegram)
    sub.add_parser("setup-email", help="connect Gmail for email alerts (one time)").set_defaults(fn=setup_email)
    sub.add_parser("test-alerts", help="send a test alert to every channel").set_defaults(fn=test_alerts)
    sub.add_parser("learn", help="log in and open each calendar so the watcher learns what to check").set_defaults(fn=learn)
    sub.add_parser("watch", help="start watching").set_defaults(fn=watch)
    args = parser.parse_args(argv)
    try:
        args.fn(args)
    except ConfigError as e:
        sys.exit(f"Setup problem: {e}")


if __name__ == "__main__":
    main()

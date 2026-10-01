"""python -m watcher {setup-telegram|learn|watch|test-telegram}"""

import argparse
import os
import sys
from pathlib import Path

from .config import ConfigError, load_captures, load_config, require_telegram, save_captures
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


def test_telegram(_args):
    cfg = load_config()
    require_telegram(cfg)
    if Telegram(cfg.telegram_bot_token, cfg.telegram_chat_id).send("🔔 Test alert from your visa slot watcher."):
        print("Sent. Check Telegram.")
    else:
        sys.exit("Couldn't send; see the error above.")


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
    require_telegram(cfg)
    captures = load_captures(cfg.captures_file)
    tg = Telegram(cfg.telegram_bot_token, cfg.telegram_chat_id)

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
                Watcher(cfg, captures, tg.send, BrowserChecker(page)).run()
            except KeyboardInterrupt:
                stopped_by_user = True
                tg.send("⏹️ Visa watcher stopped.")
            except PlaywrightError as e:
                tg.send("⏹️ Visa watcher stopped: the browser window was closed or crashed.")
                sys.exit(f"Browser error: {e}")
            except Exception as e:
                tg.send(f"⏹️ Visa watcher stopped with an error: {e}")
                raise
            context.close()
    except Exception:
        # Ctrl+C also stops Playwright's helper process, so cleanup can fail noisily. Ignore that.
        if not stopped_by_user:
            raise
    print("Stopped.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m watcher", description="Telegram alerts for earlier US visa slots.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup-telegram", help="connect your Telegram bot (one time)").set_defaults(fn=setup_telegram)
    sub.add_parser("test-telegram", help="send a test alert").set_defaults(fn=test_telegram)
    sub.add_parser("learn", help="log in and open each calendar so the watcher learns what to check").set_defaults(fn=learn)
    sub.add_parser("watch", help="start watching").set_defaults(fn=watch)
    args = parser.parse_args(argv)
    try:
        args.fn(args)
    except ConfigError as e:
        sys.exit(f"Setup problem: {e}")


if __name__ == "__main__":
    main()

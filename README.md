# US visa slot watcher (India, B1/B2)

Checks your own account on [usvisascheduling.com](https://www.usvisascheduling.com/) for **earlier
appointment dates** and alerts you by **Telegram, email, or both** the moment one opens in your date window.
**You book it yourself.**

What it does:
- Checks every ~15 minutes (randomized), at each location you choose (OFC/biometrics and/or interview).
- Alerts only for **new** dates inside your window, so it won't keep repeating itself.
- Alerts you if you get logged out, and again when it's working after you log back in.
- Sends one "still running" message a day so you know it's alive.

What it doesn't do: solve CAPTCHAs, book or reschedule anything, or send your password anywhere.
Your login lives only in a browser profile folder on your own computer.

> **Where it runs:** on your laptop (below), or 24/7 on a Google Cloud VM that you open from
> your phone. For the VM, see **[docs/google-cloud.md](docs/google-cloud.md)**. Either way, you log in
> yourself because the portal has a CAPTCHA, so serverless hosts like Vercel, Supabase or Firebase
> can't run it.

---

## One-time setup (about 15 minutes)

You need **Python 3.11 or newer** ([python.org/downloads](https://www.python.org/downloads/);
on Windows, tick *"Add python.exe to PATH"* in the installer).

Open a terminal in this folder. On Windows, use `py` wherever you see `python` below.

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 1. Set up alerts (Telegram, email, or both)

**Telegram** is the fastest way to get alerts on your phone:
1. In Telegram, open **@BotFather**, send `/newbot`, and pick any name and username.
2. BotFather replies with a **token** like `123456789:AA...`. Copy it.
3. Run the following and paste the token when asked:
   ```bash
   python -m watcher setup-telegram
   ```
   It asks you to open your new bot and tap **Start**. It then saves everything to `.env` and
   sends you a test message.

**Email** goes out from your Gmail account:
1. Turn on [2-Step Verification](https://myaccount.google.com/signinoptions/twosv) for your
   Google account, if it isn't on already.
2. Create an [app password](https://myaccount.google.com/apppasswords) named "visa watcher".
   Google shows a 16-letter password once. Copy it. **This is not your normal Gmail password.**
3. Run:
   ```bash
   python -m watcher setup-email
   ```
   Enter your Gmail address and the app password. Alerts go to yourself by default, or you can
   type another address. It sends a test email (check spam the first time and mark it
   "Not spam").

Tip: in the Gmail app, make sure notifications are on for that inbox so an alert buzzes your phone.

You can run `python -m watcher test-alerts` any time to send a test to every channel you've set up.

### 2. Set your dates

Copy `config.example.toml` to `config.toml` and set `earliest_acceptable_date` and
`latest_acceptable_date`.

### 3. Teach it what to check

```bash
python -m watcher learn
```

A browser window opens:
1. **Log in** (you solve the CAPTCHA).
2. Go to **Schedule / Reschedule Appointment**.
3. Select **each location you'd accept** so its calendar of available dates loads. If you need
   both the OFC (biometrics) and the consular interview, open both calendars.
4. Each calendar shows up in the terminal as `Captured #1 ...`. When you're done, press **Enter**
   in the terminal and give each one a name (e.g. `Chennai interview`). Press Enter without a
   name to skip anything that isn't a calendar of available days.

You don't need to repeat this unless the portal changes.

## Every time: start watching

```bash
python -m watcher watch
```

- Leave the browser window open. Minimizing it is fine. **Don't use it for other browsing**,
  because the watcher reloads it on each check.
- You'll get an alert when it starts. Press **Ctrl+C** in the terminal to stop.
- If an alert says you've been **logged out**, log in again **in the watcher's window**. It picks
  up again on its own within a few minutes.
- Keep the laptop awake and plugged in:
  - **Windows:** Settings → System → Power → Screen and sleep → "Never" when plugged in.
  - **macOS:** run it as `caffeinate -i python -m watcher watch`.

### When an alert arrives
Book quickly in **your normal browser or phone**. Before you confirm, check:
- **Reschedule limits.** The portal limits how many times you can reschedule, so make sure the
  new slot is one you'll actually keep.
- **OFC before interview.** In India the biometrics (OFC) appointment usually has to be at
  least a day before the interview. Make sure the pair still works.
- Logging in elsewhere may end the watcher's session. If it does, you'll get an alert and
  you just log in again in its window.

Once you've booked a date you're happy with, update `latest_acceptable_date` (or stop the
watcher) so it only alerts for something even better.

---

## Troubleshooting

| Problem | What to do |
|---|---|
| `learn` captured nothing | Make sure a calendar with available dates actually loaded. If there are no dates at all for that location, it has nothing to capture; try another location or try again later. |
| Logged-out alerts right after `learn` | Run `learn` again, then `watch`. If it keeps happening immediately after logging in, the portal may have changed how it works. Open an issue with what you see. |
| Logged out every few hours | That's the portal's session timeout. Log in again in the watcher's window. |
| No Telegram messages | Run `python -m watcher test-alerts`. Make sure you tapped **Start** on your bot. |
| No emails | Run `python -m watcher test-alerts` and check spam. "Gmail rejected the login" means you need an app password, not your normal one. |
| Account locked / "too many requests" | Stop, wait a day, then raise `check_interval_minutes` to 20 or more. |

## How it works
`learn` records the request the portal's own page makes when it loads a calendar. `watch`
reloads that page about every 15 minutes, replays the same request from inside your logged-in
browser, reads the dates from the reply, and alerts you about new ones in your window.

## Development
```bash
pip install pytest
python -m pytest
```
The tests include a fake portal on localhost, so they never contact the real site.

# US visa slot watcher (India, B1/B2)

Checks your own account on [usvisascheduling.com](https://www.usvisascheduling.com/) for **earlier
appointment dates** and sends you a **Telegram message** the moment one opens in your date window.
**You book it yourself.**

What it does:
- Checks every ~15 minutes (randomized), at each location you choose (OFC/biometrics and/or interview).
- Sends a Telegram alert only for **new** dates inside your window, so it won't keep repeating itself.
- Sends a Telegram alert if you get logged out, and again when it's working after you log back in.
- Sends one "still running" message a day so you know it's alive.

What it doesn't do: solve CAPTCHAs, book or reschedule anything, or send your password anywhere.
Your login lives only in a browser profile folder on your own computer.

> **Note:** this needs your laptop on and awake. The India portal's login has a CAPTCHA, so a person
> has to log in. It can't run unattended in the cloud (e.g. GitHub Actions).

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

### 1. Create your Telegram bot

1. In Telegram, open **@BotFather**, send `/newbot`, and pick any name and username.
2. BotFather replies with a **token** like `123456789:AA...`. Copy it.
3. Run the following and paste the token when asked:
   ```bash
   python -m watcher setup-telegram
   ```
   It asks you to open your new bot and tap **Start**. It then saves everything to `.env` and
   sends you a test message.

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
- You'll get a Telegram message when it starts. Press **Ctrl+C** in the terminal to stop.
- If Telegram says you've been **logged out**, log in again **in the watcher's window**. It picks
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
- Logging in elsewhere may end the watcher's session. If it does, Telegram will tell you and
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
| No Telegram messages | Run `python -m watcher test-telegram`. Make sure you tapped **Start** on your bot. |
| Account locked / "too many requests" | Stop, wait a day, then raise `check_interval_minutes` to 20 or more. |

## How it works
`learn` records the request the portal's own page makes when it loads a calendar. `watch`
reloads that page about every 15 minutes, replays the same request from inside your logged-in
browser, reads the dates from the reply, and messages you about new ones in your window.

## Development
```bash
pip install pytest
python -m pytest
```
The tests include a fake portal on localhost, so they never contact the real site.

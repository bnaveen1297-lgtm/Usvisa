# Running the watcher on a Google Cloud VM

This runs the watcher 24/7 on a small Linux computer in Google's **Mumbai** data centre. You see
its screen from your phone or laptop with **Chrome Remote Desktop**, so you can log in to the visa
portal (and solve the CAPTCHA) from anywhere.

Takes about 30 minutes the first time. You need a Google account and a payment card.

> **Note:** visa sites sometimes treat logins from cloud servers as suspicious (more CAPTCHAs, or
> blocked). That's why this uses the Mumbai region. If the portal won't let you in from the VM,
> run the watcher on your laptop instead, and stop or delete the VM so you're not charged.

---

## 1. Create a project and turn on billing

1. Go to https://console.cloud.google.com and sign in.
2. Top bar → project picker → **New project** → name it `visa-watcher` → **Create**. Make sure
   it's selected.
3. Menu ☰ → **Billing** → link a billing account. New accounts usually get free trial credit.
4. **Set a budget alert** so there are no surprises: Billing → **Budgets & alerts** → **Create
   budget** → e.g. ₹3,000/month, with email alerts at 50%, 90% and 100%.

## 2. Create the VM

Menu ☰ → **Compute Engine** → **VM instances** (click **Enable** if asked, and wait a minute) →
**Create instance**:

| Setting | Choose |
|---|---|
| Name | `visa-watcher` |
| Region | **asia-south1 (Mumbai)**, any zone |
| Machine type | **E2 → e2-medium** (2 vCPU, 4 GB) |
| Boot disk | **Change** → Operating system **Debian**, version **Debian GNU/Linux 12 (bookworm)**, size **20 GB**, balanced disk → **Select** |
| Firewall | leave HTTP/HTTPS **unticked** (nothing needs to be opened) |

Before clicking **Create**, check the **monthly estimate** shown on the right. An e2-medium in
Mumbai typically costs roughly US$25–35/month while running.

<details><summary>Prefer the command line? (Cloud Shell)</summary>

```bash
gcloud compute instances create visa-watcher \
  --zone=asia-south1-a --machine-type=e2-medium \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=20GB
```
</details>

## 3. Run the setup script

1. In the VM list, click **SSH** next to `visa-watcher`. A terminal window opens in your browser.
2. Your repo is private, so first let the VM sign in to GitHub. Paste these two lines and press
   Enter:
   ```bash
   sudo apt-get update -q && sudo apt-get install -y -q gh
   gh auth login
   ```
   Answer the questions: **GitHub.com** → **HTTPS** → **Yes** (authenticate Git) → **Login with
   a web browser**. It shows an 8-character code. On your phone or computer, open
   https://github.com/login/device, enter the code, and approve.
3. Download the watcher and run the setup:
   ```bash
   gh repo clone bnaveen1297-lgtm/Usvisa ~/Usvisa && bash ~/Usvisa/cloud/setup-vm.sh
   ```
4. Wait 5–10 minutes until it prints **Done**. Keep this window open for the next step.

It installs a lightweight desktop, Chrome Remote Desktop, and the watcher. It also sets the
clock to India time and adds two shortcuts to the desktop.

## 4. Connect Chrome Remote Desktop

1. On your own computer, open https://remotedesktop.google.com/headless (use the same Google
   account).
2. Click **Begin** → **Next** → **Authorize**.
3. Copy the command under **Debian Linux**, paste it into the VM's SSH window, and press Enter.
4. Choose a **6-digit PIN** (twice). Don't use something obvious like 123456.
5. Open https://remotedesktop.google.com/access. `visa-watcher` is listed. Click it and enter
   your PIN. You'll see the VM's desktop.
6. On your phone, install the **Chrome Remote Desktop** app (Android / iPhone) and sign in with
   the same Google account. The VM shows up there too.

You can close the SSH window now.

## 5. Set up the watcher (inside the remote desktop)

1. Double-click **Visa watcher terminal** on the desktop. If Xfce warns about an "untrusted
   launcher", click **Mark executable** or **Launch anyway**.
2. Follow the steps it prints, in order:
   ```bash
   python -m watcher setup-telegram      # and/or: python -m watcher setup-email
   nano config.toml                      # set your dates; save: Ctrl+O, Enter, Ctrl+X
   python -m watcher learn               # log in in the browser that opens, open each calendar
   ```
   These are the same steps as in the main [README](../README.md#one-time-setup-about-15-minutes).
3. Close the terminal and double-click **Start visa watcher**. You should get a "watcher started"
   alert.

From now on it **starts by itself whenever the VM starts**. If it crashes, it restarts after a
minute.

## Day to day

- **"Logged out" alert:** open Chrome Remote Desktop on your phone, log in to the portal in the
  watcher's browser window, then just close the app. The watcher continues on its own within
  a few minutes.
- **Closing Chrome Remote Desktop doesn't stop anything.** Don't click "Log out" on the VM's
  desktop, though, because that ends the session and the watcher with it. If you do, restart
  the VM (Compute Engine → VM instances → ⋮ → **Reset**).
- **Update the watcher:** in the Visa watcher terminal, run `git pull`, then restart the watcher.

## Stopping charges

- **Paused** (e.g. after you've booked): VM instances → ⋮ → **Stop**. You then only pay for the
  disk, usually under US$2/month. **Start** it again later, and the watcher starts by itself.
- **Done for good:** ⋮ → **Delete**. This removes the VM, its disk, and your saved login
  session. Then delete the project if you want: IAM & Admin → Settings → **Shut down**.

## Security

- Chrome Remote Desktop is protected by your Google account **and** your PIN. Turn on 2-Step
  Verification for your Google account.
- The VM holds your logged-in visa session and alert passwords, in the `Usvisa` folder and
  `browser-profile`. Don't give anyone else access to the project.
- No ports are opened to the internet. SSH is only through Google's console.

## Troubleshooting

| Problem | Fix |
|---|---|
| Remote desktop is black or grey | Restart it: in the SSH window run `sudo systemctl restart chrome-remote-desktop@$USER`, or **Reset** the VM. |
| `gh repo clone` says "not found" or asks for a password | Run `gh auth login` again and make sure you approve the code with the GitHub account that owns the repo. |
| VM doesn't appear in remotedesktop.google.com | Redo step 4. The headless command expires after a few minutes, so get a fresh one. |
| Portal blocks you or loops on CAPTCHA from the VM | It's probably blocking cloud IPs. Use your laptop instead, and **Stop** or **Delete** the VM. |
| No "started" alert after a reboot | Connect via remote desktop and look at the "Start visa watcher" window for the error. |

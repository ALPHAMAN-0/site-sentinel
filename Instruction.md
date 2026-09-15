# Instruction: Daily Website Checker with GitHub Actions + Telegram

This is a beginner guide. Follow the steps in order. By the end, GitHub will check your website every day and send a report to your Telegram.

**Contents**

0. [What you need](#0-what-you-need)
1. [Learn the GitHub Actions basics](#1-learn-the-github-actions-basics)
2. [Create a Telegram bot](#2-create-a-telegram-bot)
3. [Get your chat ID](#3-get-your-chat-id)
4. [Choose your website and checks (config.yaml)](#4-choose-your-website-and-checks-configyaml)
5. [Test on your Mac](#5-test-on-your-mac)
6. [Put the project on GitHub](#6-put-the-project-on-github)
7. [Add the secrets](#7-add-the-secrets)
8. [Run the workflow by hand](#8-run-the-workflow-by-hand)
9. [Change the schedule](#9-change-the-schedule)
10. [Troubleshooting](#10-troubleshooting)
11. [What to learn next](#11-what-to-learn-next)

---

## 0. What you need

- A **GitHub account**: https://github.com
- **Telegram** on your phone or computer
- On your Mac: **Python 3**, **git**, and optionally the **GitHub CLI** (`gh`). Check them with:
  ```bash
  python3 --version
  git --version
  gh --version
  ```

---

## 1. Learn the GitHub Actions basics

GitHub Actions is a free computer from GitHub that runs your commands **automatically**, for example on a timer or when you push code.

| Word | Meaning | In this project |
|---|---|---|
| **Workflow** | A `.yml` file in `.github/workflows/`. It describes an automation. | `daily-check.yml` |
| **Event / trigger** (`on:`) | What starts the workflow | `schedule` (daily timer) + `workflow_dispatch` (button) |
| **Job** (`jobs:`) | A group of steps that run on one machine | `check` |
| **Runner** (`runs-on:`) | The virtual machine GitHub gives you. It is new and empty every time. | `ubuntu-latest` |
| **Step** (`steps:`) | One task in the job. Steps run in order. | download code → install Python → install packages → run script |
| **Action** (`uses:`) | A ready-made step someone else wrote | `actions/checkout`, `actions/setup-python` |
| **Command** (`run:`) | A normal terminal command | `pip install ...`, `python check_website.py` |
| **Secret** (`secrets.X`) | A hidden password stored in GitHub, never in your code | Telegram token and chat ID |

What happens every day:

```
03:00 UTC  →  GitHub starts an Ubuntu VM
           →  step 1: downloads your repo (checkout)
           →  step 2: installs Python 3.12
           →  step 3: pip install -r requirements.txt
           →  step 4: python check_website.py  (with secrets as env variables)
                        ├─ visits your website
                        ├─ reads status, title, SSL...
                        └─ sends message to Telegram
           →  VM is deleted
```

Open `.github/workflows/daily-check.yml`. Every line has a comment explaining it.

### Cron time is UTC

`schedule` uses **cron** format and **UTC time**. Bangladesh is **UTC+6**, so subtract 6 hours.

```
┌───────── minute (0 - 59)
│ ┌─────── hour (0 - 23, UTC!)
│ │ ┌───── day of month (1 - 31)
│ │ │ ┌─── month (1 - 12)
│ │ │ │ ┌─ day of week (0 - 6, Sunday = 0)
│ │ │ │ │
0 3 * * *    → every day 03:00 UTC = 09:00 AM Bangladesh
```

---

## 2. Create a Telegram bot

1. Open Telegram and search for **@BotFather** (it has a blue check mark).
2. Tap **Start**, then send: `/newbot`
3. Enter a **name**, for example `My Website Checker`.
4. Enter a **username**. It must end in `bot`, for example `siam_site_checker_bot`.
5. BotFather replies with a **token** like:
   ```
   7412345678:AAHd8xXxXxXxXxXxXxXxXxXxXxXxXxXxXxX
   ```
6. Copy it and keep it private. Anyone with this token can control your bot.

---

## 3. Get your chat ID

The bot needs to know **where** to send messages.

1. In Telegram, open your new bot (search its username) and press **Start**, or send it any message, like `hi`.
   *(A bot can't message you until you message it first.)*
2. In your browser, open this address with your token in place of `<TOKEN>`:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Find the part that looks like this:
   ```json
   "chat": { "id": 123456789, "first_name": "Siam", "type": "private" }
   ```
4. The number (`123456789`) is your **chat ID**.

> If you see `"result": []`, send the bot another message and reload the page.
> **For a group:** add the bot to the group, send a message there, and reload. Group IDs are negative, like `-1001234567890`.

---

## 4. Choose your website and checks (config.yaml)

Open `config.yaml`:

```yaml
sites:
  - name: My Website
    url: https://example.com     # ← your website
    checks:
      status: true               # HTTP status code
      response_time: true        # speed in ms
      title: true                # page <title>
      description: true          # meta description
      ssl_expiry: true           # days until SSL certificate expires
      elements:                  # text from the page
        - label: Main heading
          selector: h1
```

- **Turn a check off:** change `true` to `false`.
- **Up/down is always checked.** A site counts as **DOWN** if it can't be reached or returns an HTTP code of 400 or higher.
- **No custom elements:** write `elements: []`
- **Several websites:** copy the whole `- name:` block and paste it below:
  ```yaml
  sites:
    - name: Site One
      url: https://site-one.com
      checks: { status: true, response_time: true, title: true, description: false, ssl_expiry: true, elements: [] }
    - name: Site Two
      url: https://site-two.com
      checks: { status: true, response_time: false, title: false, description: false, ssl_expiry: true, elements: [] }
  ```

### How to find a CSS selector (to read a specific value)

1. Open the website in Chrome.
2. Right-click the text you want (a price, headline, counter, etc.) and choose **Inspect**.
3. Look at the highlighted HTML, for example `<span class="price">৳ 1,200</span>`.
4. Pick a selector:
   - by class → `.price`
   - by id (`id="total"`) → `#total`
   - by tag → `h1`
   - nested → `.product .price`
5. Tip: in DevTools, right-click the element → **Copy → Copy selector**.

> Note: the script reads the raw HTML from the server. If the page builds its text with JavaScript after it loads, the element may show `(not found)`.

### Settings

| Setting | Meaning |
|---|---|
| `timeout_seconds` | Wait this long before calling the site DOWN |
| `slow_response_ms` | Add a ⚠️ warning if the response is slower than this |
| `ssl_warning_days` | Add a ⚠️ warning if the SSL certificate expires in fewer days than this |
| `notify` | `always` = message every day, `only_on_problem` = message only when there's a ⚠️ or ❌ |

---

## 5. Test on your Mac

Always test locally before pushing. It's much faster than waiting for GitHub.

```bash
cd "/Users/siam/Desktop/Daily Website visitor"

# create an isolated Python environment (one time)
python3 -m venv .venv
source .venv/bin/activate

# install the packages
pip install -r requirements.txt

# run without sending anything to Telegram
python check_website.py --dry-run
```

You should see the report printed in the terminal.

Now test a **real Telegram message** (use your own values):

```bash
export TELEGRAM_BOT_TOKEN="7412345678:AAH...your token"
export TELEGRAM_CHAT_ID="123456789"
python check_website.py
```

Check Telegram. You should have the report. 🎉

> Run `deactivate` to leave the virtual environment. `.venv` is listed in `.gitignore`, so it won't be uploaded.

---

## 6. Put the project on GitHub

Workflows only run on GitHub, so the project has to be in a GitHub repository.

### Option A: with GitHub CLI (fastest)

```bash
cd "/Users/siam/Desktop/Daily Website visitor"
git init
git add .
git commit -m "Daily website checker"
git branch -M main

gh auth login                     # one time; follow the prompts
gh repo create site-sentinel --public --source=. --push
```

### Option B: with the GitHub website

1. Go to https://github.com/new
2. Repository name: `site-sentinel`. Choose **Public** or **Private**. **Don't** add a README, since you already have one.
3. Click **Create repository**, then run:
   ```bash
   cd "/Users/siam/Desktop/Daily Website visitor"
   git init
   git add .
   git commit -m "Daily website checker"
   git branch -M main
   git remote add origin https://github.com/<your-username>/site-sentinel.git
   git push -u origin main
   ```

> **Public or private?** Public repos get unlimited free Actions minutes. Private repos get 2,000 free minutes per month. This workflow uses about 30 seconds per run (~15 minutes per month), so both are fine.
> **Never commit your token** in `config.yaml` or the code. It goes in Secrets (next step).

---

## 7. Add the secrets

1. Open your repo on GitHub.
2. Go to **Settings** → **Secrets and variables** (left menu) → **Actions**.
3. Click **New repository secret**:
   - Name: `TELEGRAM_BOT_TOKEN` → Value: your bot token → **Add secret**
4. Click **New repository secret** again:
   - Name: `TELEGRAM_CHAT_ID` → Value: your chat ID → **Add secret**

The names must match **exactly** (uppercase), because the workflow reads `secrets.TELEGRAM_BOT_TOKEN` and `secrets.TELEGRAM_CHAT_ID`.

Or use the CLI (it asks you to paste the value):

```bash
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
```

---

## 8. Run the workflow by hand

Don't wait until tomorrow. Test it now.

1. Open the **Actions** tab of your repo.
   (If Actions is disabled, click **I understand my workflows, go ahead and enable them**.)
2. Click **Daily Website Check** in the left list.
3. Click **Run workflow** → **Run workflow** (green button).
4. After a few seconds a new run appears. Click it, then click the **check** job.
5. Expand each step to see its log. The **Check websites and send Telegram report** step shows the full report.
6. Check Telegram. ✅

Or use the CLI:

```bash
gh workflow run "Daily Website Check"
gh run watch
```

Run results:
- 🟢 **Green check:** everything worked, all sites up
- 🔴 **Red X:** a site is DOWN, secrets are missing, or Telegram failed. Open the log to see why. GitHub also emails you about failed runs.

**Done!** From now on it runs automatically every day at **9:00 AM Bangladesh time**.

---

## 9. Change the schedule

Edit the `cron` line in `.github/workflows/daily-check.yml`, then commit and push:

```bash
git add .github/workflows/daily-check.yml
git commit -m "Change schedule"
git push
```

| You want (Bangladesh time) | cron (UTC) |
|---|---|
| Every day 6:00 AM | `0 0 * * *` |
| Every day 9:00 AM *(current)* | `0 3 * * *` |
| Every day 12:00 PM | `0 6 * * *` |
| Every day 6:00 PM | `0 12 * * *` |
| Every day 10:00 PM | `0 16 * * *` |
| 9 AM and 9 PM | `0 3,15 * * *` |
| Every 6 hours | `0 */6 * * *` |
| Every hour | `0 * * * *` |
| Sunday–Thursday 9 AM | `0 3 * * 0-4` |

Tip: https://crontab.guru explains any cron expression. Remember it uses UTC.

The same way, **any change** to `config.yaml` (new URL, turning checks on or off) needs `git add`, `git commit`, and `git push` before GitHub uses it.

---

## 10. Troubleshooting

| Problem | Why | Fix |
|---|---|---|
| Log says `TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set` | Secrets missing or misspelled | Step 7: names must match exactly |
| `Telegram error 401: Unauthorized` | Wrong bot token | Copy the token again from @BotFather |
| `Telegram error 400: Bad Request: chat not found` | Wrong chat ID, or you never messaged the bot | Press **Start** in the bot and repeat step 3 |
| No **Run workflow** button | Workflow file isn't on the default branch (`main`) | Make sure `.github/workflows/daily-check.yml` was pushed to `main` |
| Scheduled run didn't happen at exactly 9:00 | GitHub queues scheduled jobs when it's busy | Normal. It can be 5–30 minutes late. |
| Scheduled runs stopped after some weeks | GitHub **disables schedules in public repos after 60 days with no commits** | Actions tab → the workflow → **Enable workflow**, or push any commit |
| Site shows DOWN on GitHub but works in your browser | The site blocks cloud/data-center IPs, or blocks bots | Try another URL. Some sites (e.g. behind Cloudflare) block GitHub runners. |
| Element shows `(not found)` | Wrong selector, or the text is added by JavaScript | Re-check the selector (section 4) |
| `ModuleNotFoundError` locally | Virtual environment not active | `source .venv/bin/activate` then `pip install -r requirements.txt` |

---

## 11. What to learn next

When this works, try these to learn more GitHub Actions features:

1. **Failure notification step:** add a step with `if: failure()` that sends a Telegram message when the workflow itself breaks.
2. **Matrix strategy:** use `strategy: matrix:` to run the check on several Python versions or sites in parallel.
3. **Artifacts:** save a daily result file with `actions/upload-artifact` so you can download a history.
4. **Alert only on change:** store yesterday's result (e.g. commit a `last_result.json` back to the repo using `permissions: contents: write`) and send a message only when something changes.
5. **Variables:** move non-secret settings like the URL into **Settings → Secrets and variables → Actions → Variables** and read them with `${{ vars.NAME }}`.
6. **Push trigger:** add `push:` under `on:` so the check runs every time you change `config.yaml`.

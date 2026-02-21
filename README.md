# 📦 Subscription Manager Telegram Bot

A Telegram bot to track your app subscriptions, monitor spending, and receive payment reminders — ready to deploy on Railway.

---

## Features

- ➕ Add subscriptions (name, price, billing period, next payment date)
- 📋 List all subscriptions
- ✏️ Edit any field of a subscription
- 🗑️ Remove subscriptions
- 💸 View total monthly/yearly spending
- ⏰ Daily reminders 3 days before a payment is due
- 🔒 Data is stored per-user in SQLite

---

## Bot Commands

| Command   | Description                          |
|-----------|--------------------------------------|
| `/start`  | Show welcome message and command list |
| `/add`    | Add a new subscription               |
| `/list`   | List all subscriptions               |
| `/edit`   | Edit an existing subscription        |
| `/remove` | Remove a subscription                |
| `/total`  | Show monthly and yearly spending     |
| `/cancel` | Cancel the current action            |

---

## Local Development

### Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Setup

```bash
git clone https://github.com/youruser/telegram-sub-bot.git
cd telegram-sub-bot

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configure environment

```bash
cp .env.example .env
# Edit .env and fill in BOT_TOKEN (and WEBHOOK_URL if testing webhooks)
```

### Run locally (polling mode for development)

For local development without a public URL, you can use polling instead of webhooks.
Create a file `run_polling.py`:

```python
import os
from bot import build_app

if __name__ == "__main__":
    app = build_app()
    app.run_polling()
```

Then run:
```bash
python run_polling.py
```

---

## Deploy on Railway

### Step 1 – Create a Railway account

Sign up at [railway.app](https://railway.app) and install the Railway CLI (optional):
```bash
npm install -g @railway/cli
railway login
```

### Step 2 – Create a new Railway project

**Via Dashboard:**
1. Go to [railway.app/new](https://railway.app/new)
2. Click **Deploy from GitHub repo** (or **Empty project** for manual deploy)
3. Connect your GitHub repository

**Via CLI:**
```bash
railway init
railway link  # or create a new project
```

### Step 3 – Set environment variables

In the Railway dashboard, go to your service → **Variables** tab and add:

| Variable         | Value                                         |
|------------------|-----------------------------------------------|
| `BOT_TOKEN`      | Your Telegram bot token from @BotFather       |
| `DATABASE_URL`   | `subscriptions.db` (or a volume path — see below) |
| `WEBHOOK_URL`    | Your Railway public URL (set after first deploy) |
| `WEBHOOK_SECRET` | A random secret string for security           |
| `PORT`           | `8000` (Railway auto-sets this)               |

Via CLI:
```bash
railway variables set BOT_TOKEN=your_token_here
railway variables set WEBHOOK_SECRET=your_random_secret
railway variables set DATABASE_URL=subscriptions.db
```

### Step 4 – Add a persistent volume (recommended)

SQLite data is lost on redeploy without a volume.

1. In Railway dashboard → your service → **Volumes** tab
2. Click **Add Volume**
3. Set mount path to `/data`
4. Update `DATABASE_URL` to `/data/subscriptions.db`

### Step 5 – Deploy

**Via GitHub:** Push to your repo — Railway auto-deploys.

**Via CLI:**
```bash
railway up
```

### Step 6 – Get your public URL and set WEBHOOK_URL

1. In Railway dashboard → your service → **Settings** tab
2. Under **Networking**, click **Generate Domain**
3. Copy the URL (e.g. `https://your-app.up.railway.app`)
4. Set it as an environment variable:
   ```bash
   railway variables set WEBHOOK_URL=https://your-app.up.railway.app
   ```
5. Trigger a redeploy:
   ```bash
   railway up
   # or push a commit
   ```

### Step 7 – Verify

- Visit `https://your-app.up.railway.app/` — you should see `{"status":"ok"}`
- Send `/start` to your bot in Telegram

---

## Project Structure

```
telegram-sub-bot/
├── main.py           # FastAPI app + webhook endpoint + scheduler
├── bot.py            # Telegram bot handlers and conversation flows
├── database.py       # SQLite database layer
├── requirements.txt  # Python dependencies
├── railway.toml      # Railway deploy config
├── Procfile          # Process definition
└── .env.example      # Environment variable template
```

---

## Environment Variables Reference

| Variable         | Required | Default              | Description                              |
|------------------|----------|----------------------|------------------------------------------|
| `BOT_TOKEN`      | ✅ Yes   | —                    | Telegram bot token from @BotFather       |
| `DATABASE_URL`   | No       | `subscriptions.db`   | Path to SQLite database file             |
| `WEBHOOK_URL`    | No       | —                    | Public base URL for webhook registration |
| `WEBHOOK_SECRET` | No       | —                    | Secret token to validate webhook calls   |
| `PORT`           | No       | `8000`               | HTTP port to listen on                   |

---

## Architecture

```
Telegram API
    │  (HTTPS webhook)
    ▼
FastAPI (/webhook)
    │
    ├── python-telegram-bot (Update processing)
    │       └── ConversationHandlers (add/edit/remove/list)
    │
    ├── APScheduler (daily 09:00 UTC)
    │       └── Sends payment reminders
    │
    └── SQLite Database
            └── users, subscriptions tables
```

---

## Troubleshooting

**Bot not responding:**
- Check `BOT_TOKEN` is correct
- Ensure `WEBHOOK_URL` is the correct public URL
- Check Railway logs: `railway logs`

**Data lost after redeploy:**
- Add a Railway Volume mounted at `/data`
- Set `DATABASE_URL=/data/subscriptions.db`

**Webhook not registered:**
- Make sure `WEBHOOK_URL` is set before starting the app
- Verify the URL is publicly accessible (not localhost)
- Check Railway logs for webhook registration confirmation

**Reminders not sending:**
- The scheduler runs daily at 09:00 UTC
- Ensure the bot is running continuously (Railway keeps it alive)

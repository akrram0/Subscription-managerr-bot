# Subscription Manager Bot

Personal Telegram bot to track your subscriptions. Only 2 variables needed, data saved in a local JSON file.

---

## Setup

### 1. Get your variables

**`BOT_TOKEN`** — from [@BotFather](https://t.me/BotFather) on Telegram:
- Send `/newbot`, follow the steps, copy the token.

**`MY_CHAT_ID`** — your personal Telegram ID:
- Message [@userinfobot](https://t.me/userinfobot) on Telegram, it replies with your ID instantly.

---

### 2. Deploy on Railway

1. Push this folder to a GitHub repo
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo
4. Go to **Variables** tab and add:
   - `BOT_TOKEN` = your token
   - `MY_CHAT_ID` = your numeric ID
5. Railway auto-deploys — your bot is live!

> **Note:** `data.json` is stored on Railway's ephemeral filesystem.
> It resets if the service restarts. For permanent storage, add a Railway Volume
> and change `DATA_FILE` in `storage.py` to `/data/data.json`.

---

### 3. Run locally (alternative)

```bash
pip install -r requirements.txt

# Set variables
export BOT_TOKEN=your_token
export MY_CHAT_ID=your_id

python bot.py
```

---

## Commands

| Command   | What it does              |
|-----------|---------------------------|
| `/start`  | Show help                 |
| `/add`    | Add a subscription        |
| `/list`   | List all subscriptions    |
| `/edit`   | Edit a subscription       |
| `/remove` | Remove a subscription     |
| `/total`  | Show monthly spending     |
| `/cancel` | Cancel current action     |

---

## Variables Summary

| Variable     | Where to get it                              |
|--------------|----------------------------------------------|
| `BOT_TOKEN`  | @BotFather on Telegram                       |
| `MY_CHAT_ID` | @userinfobot on Telegram (just message it)   |

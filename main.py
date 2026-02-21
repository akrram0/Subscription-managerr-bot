import os
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update

from bot import build_app, send_reminders

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
PORT = int(os.environ.get("PORT", 8000))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # e.g. https://your-app.railway.app

application = build_app()
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await application.initialize()
    if WEBHOOK_URL:
        await application.bot.set_webhook(
            url=f"{WEBHOOK_URL.rstrip('/')}/webhook",
            secret_token=WEBHOOK_SECRET or None
        )
        logger.info(f"Webhook set to {WEBHOOK_URL}/webhook")
    else:
        logger.warning("WEBHOOK_URL not set – webhook not registered with Telegram")

    scheduler.add_job(
        send_reminders,
        "cron",
        hour=9,
        minute=0,
        args=[application],
        id="daily_reminders"
    )
    scheduler.start()
    logger.info("Scheduler started")

    await application.start()
    yield

    scheduler.shutdown(wait=False)
    await application.stop()
    await application.shutdown()


web_app = FastAPI(lifespan=lifespan)


@web_app.get("/")
async def health():
    return {"status": "ok"}


@web_app.post("/webhook")
async def webhook(request: Request):
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != WEBHOOK_SECRET:
            return Response(content="Forbidden", status_code=403)

    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return Response(content="ok")


if __name__ == "__main__":
    uvicorn.run("main:web_app", host="0.0.0.0", port=PORT, log_level="info")

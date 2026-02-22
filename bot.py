import os
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import storage

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
MY_CHAT_ID = int(os.environ["MY_CHAT_ID"])

# Conversation states
ADD_NAME, ADD_PRICE, ADD_PERIOD, ADD_DATE = range(4)
EDIT_SELECT_SUB, EDIT_SELECT_FIELD, EDIT_VALUE = range(4, 7)
REMOVE_PICK = range(7, 8)


# ── Helpers ──────────────────────────────────────────────────────────────────

def only_me(func):
    """Decorator: ignore anyone who isn't you."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != MY_CHAT_ID:
            return
        return await func(update, context)
    return wrapper


def fmt(sub: dict) -> str:
    return (
        f"*{sub['name']}* (#{sub['id']})\n"
        f"  💰 ${sub['price']:.2f} / {sub['period']}\n"
        f"  📅 Next: {sub['date']}"
    )


def validate_price(text: str) -> float | None:
    try:
        v = float(text.replace(",", "."))
        return round(v, 2) if v > 0 else None
    except ValueError:
        return None


def validate_date(text: str) -> str | None:
    for fmt_str in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt_str).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ── /start ───────────────────────────────────────────────────────────────────

@only_me
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Subscription Manager*\n\n"
        "/add – Add subscription\n"
        "/list – List all\n"
        "/edit – Edit one\n"
        "/remove – Remove one\n"
        "/total – Monthly spending\n"
        "/cancel – Cancel action",
        parse_mode="Markdown"
    )


@only_me
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


# ── /add flow ────────────────────────────────────────────────────────────────

@only_me
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and len(args) >= 4:
        name = args[0]
        price = validate_price(args[1])
        period = args[2].lower()
        date = validate_date(args[3])
        if price and period in ("monthly", "yearly") and date:
            sub = storage.add(name, price, period, date)
            await update.message.reply_text("Added!\n\n" + fmt(sub), parse_mode="Markdown")
            return ConversationHandler.END
    await update.message.reply_text("Name of the subscription?")
    return ADD_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name or len(name) > 100:
        await update.message.reply_text("⚠️ Keep it under 100 chars. Try again:")
        return ADD_NAME
    context.user_data["name"] = name
    await update.message.reply_text("💰 Price? (e.g. 9.99)")
    return ADD_PRICE


async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = validate_price(update.message.text.strip())
    if price is None:
        await update.message.reply_text("⚠️ Enter a valid positive number:")
        return ADD_PRICE
    context.user_data["price"] = price
    kb = [[InlineKeyboardButton("Monthly", callback_data="p_monthly"),
           InlineKeyboardButton("Yearly", callback_data="p_yearly")]]
    await update.message.reply_text("🔄 Billing period?", reply_markup=InlineKeyboardMarkup(kb))
    return ADD_PERIOD


async def add_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["period"] = q.data.replace("p_", "")
    await q.edit_message_text("📅 Next payment date? (YYYY-MM-DD or DD/MM/YYYY)")
    return ADD_DATE


async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = validate_date(update.message.text.strip())
    if date is None:
        await update.message.reply_text("⚠️ Invalid date. Use YYYY-MM-DD or DD/MM/YYYY:")
        return ADD_DATE
    sub = storage.add(context.user_data["name"], context.user_data["price"], context.user_data["period"], date)
    context.user_data.clear()
    await update.message.reply_text(f"✅ Added!\n\n{fmt(sub)}", parse_mode="Markdown")
    return ConversationHandler.END


# ── /list ────────────────────────────────────────────────────────────────────

@only_me
async def list_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = storage.get_all()
    if not subs:
        await update.message.reply_text("📭 No subscriptions yet. Use /add.")
        return
    text = "📋 *Your Subscriptions*\n\n" + "\n\n".join(fmt(s) for s in subs)
    await update.message.reply_text(text, parse_mode="Markdown")


# ── /total ───────────────────────────────────────────────────────────────────

@only_me
async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = storage.get_all()
    if not subs:
        await update.message.reply_text("📭 No subscriptions yet.")
        return
    monthly = sum(s["price"] if s["period"] == "monthly" else s["price"] / 12 for s in subs)
    await update.message.reply_text(
        f"💸 *Spending*\n\n"
        f"Monthly: *${monthly:.2f}*\n"
        f"Yearly:  *${monthly * 12:.2f}*\n"
        f"Total subscriptions: {len(subs)}",
        parse_mode="Markdown"
    )


# ── /remove flow ─────────────────────────────────────────────────────────────

@only_me
async def remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = storage.get_all()
    if not subs:
        await update.message.reply_text("📭 Nothing to remove.")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(s["name"], callback_data=f"rm_{s['id']}")] for s in subs]
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="rm_cancel")])
    await update.message.reply_text("🗑 Which one to remove?", reply_markup=InlineKeyboardMarkup(kb))
    return REMOVE_PICK


async def remove_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "rm_cancel":
        await q.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END
    sub_id = int(q.data.replace("rm_", ""))
    sub = storage.get_by_id(sub_id)
    storage.delete(sub_id)
    await q.edit_message_text(f"✅ *{sub['name']}* removed.", parse_mode="Markdown")
    return ConversationHandler.END


# ── /edit flow ───────────────────────────────────────────────────────────────

@only_me
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = storage.get_all()
    if not subs:
        await update.message.reply_text("📭 Nothing to edit.")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(s["name"], callback_data=f"es_{s['id']}")] for s in subs]
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="es_cancel")])
    await update.message.reply_text("✏️ Which subscription to edit?", reply_markup=InlineKeyboardMarkup(kb))
    return EDIT_SELECT_SUB


async def edit_select_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "es_cancel":
        await q.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END
    context.user_data["edit_id"] = int(q.data.replace("es_", ""))
    kb = [
        [InlineKeyboardButton("Name", callback_data="ef_name"),
         InlineKeyboardButton("Price", callback_data="ef_price")],
        [InlineKeyboardButton("Period", callback_data="ef_period"),
         InlineKeyboardButton("Date", callback_data="ef_date")],
        [InlineKeyboardButton("❌ Cancel", callback_data="ef_cancel")],
    ]
    await q.edit_message_text("Which field?", reply_markup=InlineKeyboardMarkup(kb))
    return EDIT_SELECT_FIELD


async def edit_select_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "ef_cancel":
        await q.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END
    field = q.data.replace("ef_", "")
    context.user_data["edit_field"] = field
    if field == "period":
        kb = [[InlineKeyboardButton("Monthly", callback_data="ev_monthly"),
               InlineKeyboardButton("Yearly", callback_data="ev_yearly")]]
        await q.edit_message_text("New period:", reply_markup=InlineKeyboardMarkup(kb))
        return EDIT_VALUE
    prompts = {"name": "New name:", "price": "New price (e.g. 9.99):", "date": "New date (YYYY-MM-DD):"}
    await q.edit_message_text(prompts[field])
    return EDIT_VALUE


async def edit_value_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data["edit_field"]
    sub_id = context.user_data["edit_id"]
    text = update.message.text.strip()

    if field == "name":
        if not text or len(text) > 100:
            await update.message.reply_text("⚠️ Keep it under 100 chars:")
            return EDIT_VALUE
        value = text
    elif field == "price":
        value = validate_price(text)
        if value is None:
            await update.message.reply_text("⚠️ Enter a valid positive number:")
            return EDIT_VALUE
    elif field == "date":
        value = validate_date(text)
        if value is None:
            await update.message.reply_text("⚠️ Use YYYY-MM-DD or DD/MM/YYYY:")
            return EDIT_VALUE

    storage.update(sub_id, field, value)
    context.user_data.clear()
    await update.message.reply_text("✅ Updated!")
    return ConversationHandler.END


async def edit_value_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    storage.update(context.user_data["edit_id"], "period", q.data.replace("ev_", ""))
    context.user_data.clear()
    await q.edit_message_text("✅ Updated!")
    return ConversationHandler.END


# ── Reminders ────────────────────────────────────────────────────────────────

async def send_reminders(app: Application):
    for sub in storage.due_in_days(3):
        await app.bot.send_message(
            chat_id=MY_CHAT_ID,
            text=f"⏰ *Reminder!* {sub['name']} is due in 3 days!\n💰 ${sub['price']:.2f}",
            parse_mode="Markdown"
        )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_subs))
    app.add_handler(CommandHandler("total", total))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_PERIOD: [CallbackQueryHandler(add_period, pattern="^p_")],
            ADD_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("remove", remove_start)],
        states={
            REMOVE_PICK: [CallbackQueryHandler(remove_pick, pattern="^rm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("edit", edit_start)],
        states={
            EDIT_SELECT_SUB:   [CallbackQueryHandler(edit_select_sub, pattern="^es_")],
            EDIT_SELECT_FIELD: [CallbackQueryHandler(edit_select_field, pattern="^ef_")],
            EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_text),
                CallbackQueryHandler(edit_value_callback, pattern="^ev_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, "cron", hour=9, minute=0, args=[app])
    scheduler.start()

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()

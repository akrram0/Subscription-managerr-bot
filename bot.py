import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(
    ADD_NAME, ADD_PRICE, ADD_PERIOD, ADD_DATE,
    EDIT_SELECT, EDIT_FIELD, EDIT_VALUE,
    REMOVE_CONFIRM
) = range(8)

BOT_TOKEN = os.environ["BOT_TOKEN"]


# ─── HELPERS ────────────────────────────────────────────────────────────────

def format_subscription(sub: dict) -> str:
    return (
        f"📦 *{sub['name']}*\n"
        f"💰 Price: ${sub['price']:.2f}\n"
        f"🔄 Period: {sub['billing_period'].capitalize()}\n"
        f"📅 Next payment: {sub['next_payment_date']}\n"
        f"🆔 ID: `{sub['id']}`"
    )


def validate_price(text: str):
    try:
        val = float(text.replace(",", "."))
        if val <= 0:
            raise ValueError
        return round(val, 2)
    except ValueError:
        return None


def validate_date(text: str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ─── COMMANDS ───────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.ensure_user(update.effective_user.id)
    await update.message.reply_text(
        "👋 *Subscription Manager Bot*\n\n"
        "Track all your app subscriptions in one place.\n\n"
        "Commands:\n"
        "/add – Add a subscription\n"
        "/list – List all subscriptions\n"
        "/remove – Remove a subscription\n"
        "/edit – Edit a subscription\n"
        "/total – Monthly spending total\n"
        "/cancel – Cancel current action",
        parse_mode="Markdown"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END


# ─── ADD FLOW ───────────────────────────────────────────────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.ensure_user(update.effective_user.id)
    await update.message.reply_text("📝 Enter the subscription *name* (e.g. Netflix):", parse_mode="Markdown")
    return ADD_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name or len(name) > 100:
        await update.message.reply_text("⚠️ Name must be 1–100 characters. Try again:")
        return ADD_NAME
    context.user_data["add_name"] = name
    await update.message.reply_text("💰 Enter the *price* (e.g. 9.99):", parse_mode="Markdown")
    return ADD_PRICE


async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = validate_price(update.message.text.strip())
    if price is None:
        await update.message.reply_text("⚠️ Invalid price. Enter a positive number (e.g. 9.99):")
        return ADD_PRICE
    context.user_data["add_price"] = price
    keyboard = [
        [InlineKeyboardButton("Monthly", callback_data="period_monthly"),
         InlineKeyboardButton("Yearly", callback_data="period_yearly")]
    ]
    await update.message.reply_text(
        "🔄 Choose *billing period*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ADD_PERIOD


async def add_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.replace("period_", "")
    context.user_data["add_period"] = period
    await query.edit_message_text(
        "📅 Enter *next payment date* (YYYY-MM-DD or DD/MM/YYYY):",
        parse_mode="Markdown"
    )
    return ADD_DATE


async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = validate_date(update.message.text.strip())
    if date_str is None:
        await update.message.reply_text("⚠️ Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY:")
        return ADD_DATE
    user_id = update.effective_user.id
    sub_id = db.add_subscription(
        user_id,
        context.user_data["add_name"],
        context.user_data["add_price"],
        context.user_data["add_period"],
        date_str
    )
    context.user_data.clear()
    await update.message.reply_text(
        f"✅ Subscription added! (ID: `{sub_id}`)",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─── LIST ───────────────────────────────────────────────────────────────────

async def list_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.ensure_user(update.effective_user.id)
    subs = db.get_subscriptions(update.effective_user.id)
    if not subs:
        await update.message.reply_text("📭 You have no subscriptions yet. Use /add to add one.")
        return
    text = "📋 *Your Subscriptions:*\n\n" + "\n\n".join(format_subscription(s) for s in subs)
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── TOTAL ──────────────────────────────────────────────────────────────────

async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.ensure_user(update.effective_user.id)
    subs = db.get_subscriptions(update.effective_user.id)
    if not subs:
        await update.message.reply_text("📭 No subscriptions found.")
        return
    monthly_total = sum(
        s["price"] if s["billing_period"] == "monthly" else s["price"] / 12
        for s in subs
    )
    yearly_total = monthly_total * 12
    await update.message.reply_text(
        f"💸 *Spending Summary*\n\n"
        f"Monthly: *${monthly_total:.2f}*\n"
        f"Yearly: *${yearly_total:.2f}*\n"
        f"Subscriptions: {len(subs)}",
        parse_mode="Markdown"
    )


# ─── REMOVE FLOW ────────────────────────────────────────────────────────────

async def remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.ensure_user(update.effective_user.id)
    subs = db.get_subscriptions(update.effective_user.id)
    if not subs:
        await update.message.reply_text("📭 No subscriptions to remove.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(s["name"], callback_data=f"remove_{s['id']}")] for s in subs]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="remove_cancel")])
    await update.message.reply_text(
        "🗑 Select a subscription to remove:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REMOVE_CONFIRM


async def remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "remove_cancel":
        await query.edit_message_text("❌ Removal cancelled.")
        return ConversationHandler.END
    sub_id = int(query.data.replace("remove_", ""))
    sub = db.get_subscription(sub_id, update.effective_user.id)
    if not sub:
        await query.edit_message_text("⚠️ Subscription not found.")
        return ConversationHandler.END
    db.delete_subscription(sub_id, update.effective_user.id)
    await query.edit_message_text(f"✅ *{sub['name']}* has been removed.", parse_mode="Markdown")
    return ConversationHandler.END


# ─── EDIT FLOW ──────────────────────────────────────────────────────────────

async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.ensure_user(update.effective_user.id)
    subs = db.get_subscriptions(update.effective_user.id)
    if not subs:
        await update.message.reply_text("📭 No subscriptions to edit.")
        return ConversationHandler.END
    keyboard = [[InlineKeyboardButton(s["name"], callback_data=f"editsel_{s['id']}")] for s in subs]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="editsel_cancel")])
    await update.message.reply_text(
        "✏️ Select a subscription to edit:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_SELECT


async def edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "editsel_cancel":
        await query.edit_message_text("❌ Edit cancelled.")
        return ConversationHandler.END
    sub_id = int(query.data.replace("editsel_", ""))
    sub = db.get_subscription(sub_id, update.effective_user.id)
    if not sub:
        await query.edit_message_text("⚠️ Subscription not found.")
        return ConversationHandler.END
    context.user_data["edit_id"] = sub_id
    keyboard = [
        [InlineKeyboardButton("Name", callback_data="field_name"),
         InlineKeyboardButton("Price", callback_data="field_price")],
        [InlineKeyboardButton("Period", callback_data="field_period"),
         InlineKeyboardButton("Next Date", callback_data="field_date")],
        [InlineKeyboardButton("❌ Cancel", callback_data="field_cancel")]
    ]
    await query.edit_message_text(
        f"Which field to edit in *{sub['name']}*?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return EDIT_FIELD


async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "field_cancel":
        await query.edit_message_text("❌ Edit cancelled.")
        return ConversationHandler.END
    field = query.data.replace("field_", "")
    context.user_data["edit_field"] = field

    if field == "period":
        keyboard = [
            [InlineKeyboardButton("Monthly", callback_data="editval_monthly"),
             InlineKeyboardButton("Yearly", callback_data="editval_yearly")]
        ]
        await query.edit_message_text(
            "Choose new billing period:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return EDIT_VALUE

    prompts = {
        "name": "Enter new *name*:",
        "price": "Enter new *price* (e.g. 9.99):",
        "date": "Enter new *next payment date* (YYYY-MM-DD):",
    }
    await query.edit_message_text(prompts[field], parse_mode="Markdown")
    return EDIT_VALUE


async def edit_value_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data["edit_field"]
    sub_id = context.user_data["edit_id"]
    text = update.message.text.strip()

    if field == "name":
        if not text or len(text) > 100:
            await update.message.reply_text("⚠️ Name must be 1–100 characters. Try again:")
            return EDIT_VALUE
        value = text
    elif field == "price":
        value = validate_price(text)
        if value is None:
            await update.message.reply_text("⚠️ Invalid price. Enter a positive number:")
            return EDIT_VALUE
    elif field == "date":
        value = validate_date(text)
        if value is None:
            await update.message.reply_text("⚠️ Invalid date. Use YYYY-MM-DD or DD/MM/YYYY:")
            return EDIT_VALUE

    db.update_subscription(sub_id, update.effective_user.id, field, value)
    context.user_data.clear()
    await update.message.reply_text(f"✅ Subscription updated successfully!")
    return ConversationHandler.END


async def edit_value_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.replace("editval_", "")
    sub_id = context.user_data["edit_id"]
    db.update_subscription(sub_id, update.effective_user.id, "billing_period", period)
    context.user_data.clear()
    await query.edit_message_text(f"✅ Billing period updated to *{period}*.", parse_mode="Markdown")
    return ConversationHandler.END


# ─── REMINDERS ──────────────────────────────────────────────────────────────

async def send_reminders(app):
    target_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    subs = db.get_subscriptions_due_on(target_date)
    for sub in subs:
        try:
            await app.bot.send_message(
                chat_id=sub["user_id"],
                text=(
                    f"⏰ *Payment Reminder!*\n\n"
                    f"📦 {sub['name']} is due in 3 days!\n"
                    f"💰 Amount: ${sub['price']:.2f}\n"
                    f"📅 Date: {sub['next_payment_date']}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send reminder to {sub['user_id']}: {e}")


def build_app():
    db.init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_PERIOD: [CallbackQueryHandler(add_period, pattern="^period_")],
            ADD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    remove_conv = ConversationHandler(
        entry_points=[CommandHandler("remove", remove_start)],
        states={
            REMOVE_CONFIRM: [CallbackQueryHandler(remove_confirm, pattern="^remove_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    edit_conv = ConversationHandler(
        entry_points=[CommandHandler("edit", edit_start)],
        states={
            EDIT_SELECT: [CallbackQueryHandler(edit_select, pattern="^editsel_")],
            EDIT_FIELD: [CallbackQueryHandler(edit_field, pattern="^field_")],
            EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_text),
                CallbackQueryHandler(edit_value_callback, pattern="^editval_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_subs))
    application.add_handler(CommandHandler("total", total))
    application.add_handler(add_conv)
    application.add_handler(remove_conv)
    application.add_handler(edit_conv)

    return application

"""
Subscription Management & Reminders Bot — v2.2 (Menu Button Integrated)
=======================================================================
Updates:
- Added 'Menu Button' support (opens Mini App directly from the text field).
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, WebAppInfo, MenuButtonWebApp  # <--- Added MenuButtonWebApp
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import (
    init_db, get_user_language, set_user_language, ensure_user_exists,
    add_subscription, get_user_subscriptions, delete_subscription,
    get_due_subscriptions, get_past_due_subscriptions, update_next_payment_date
)
from locales import t, TEXTS

# ============================================================
# CONFIGURATION
# ============================================================
BOT_TOKEN = "8304071879:AAHP5ST3SHAoxTGbTJ1yVG58VjbOWvQ343c"
# الرابط الصحيح لأن اسم الملف في GitHub هو index.html
WEB_APP_URL = "https://glistening-gaufre-57bb50.netlify.app/index.html?v=5"


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

CURRENCIES = ["USD", "SAR", "EGP", "AED", "KWD", "QAR", "BHD", "OMR", "JOD", "EUR", "GBP"]

# ============================================================
# KEYBOARD BUILDERS
# ============================================================

def build_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Build the persistent reply keyboard (bottom buttons)."""
    buttons = [
        [KeyboardButton(text=t(lang, "btn_add"), web_app=WebAppInfo(url=WEB_APP_URL)),
         KeyboardButton(text=t(lang, "btn_list"))],
        [KeyboardButton(text=t(lang, "btn_total")),
         KeyboardButton(text=t(lang, "btn_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def build_language_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
         InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_main_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text=t(lang, "btn_add_inline"), web_app=WebAppInfo(url=WEB_APP_URL)),
            InlineKeyboardButton(text=t(lang, "btn_list_inline"), callback_data="action_list")
        ],
        [InlineKeyboardButton(text=t(lang, "btn_total_inline"), callback_data="action_total"),
         InlineKeyboardButton(text=t(lang, "btn_delete_inline"), callback_data="action_delete")],
        [InlineKeyboardButton(text=t(lang, "btn_help_inline"), callback_data="action_help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_currency_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for currency in CURRENCIES:
        row.append(InlineKeyboardButton(text=currency, callback_data=f"currency_{currency}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_billing_cycle_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=t(lang, "cycle_monthly"), callback_data="cycle_monthly"),
         InlineKeyboardButton(text=t(lang, "cycle_yearly"), callback_data="cycle_yearly")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="action_cancel")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_delete_keyboard(subs: list, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for sub in subs:
        text = f"🗑 {sub['service_name']} — {sub['cost']} {sub['currency']}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"del_{sub['id']}")])
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_confirm_delete_keyboard(sub_id: int, lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=t(lang, "delete_yes"), callback_data=f"confirm_del_{sub_id}"),
         InlineKeyboardButton(text=t(lang, "delete_no"), callback_data="action_delete")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ar":
        buttons = [
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
             InlineKeyboardButton(text="🇸🇦 العربية ✓", callback_data="set_lang_ar")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="🇬🇧 English ✓", callback_data="set_lang_en"),
             InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar")]
        ]
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
# HELPER: Get user language
# ============================================================
async def get_lang(user_id: int) -> str:
    return await get_user_language(user_id)

def format_subscription_card(sub: dict, index: int, lang: str) -> str:
    cycle_text = t(lang, sub['billing_cycle'])
    try:
        payment_date = datetime.strptime(sub['next_payment_date'], "%Y-%m-%d")
        days_left = (payment_date - datetime.now()).days
        if days_left < 0: days_text = t(lang, "days_overdue")
        elif days_left == 0: days_text = t(lang, "days_today")
        elif days_left == 1: days_text = t(lang, "days_tomorrow")
        elif days_left <= 3: days_text = t(lang, "days_soon").format(days_left)
        elif days_left <= 7: days_text = t(lang, "days_week").format(days_left)
        else: days_text = t(lang, "days_later").format(days_left)
    except ValueError:
        days_text = "—"

    card = (
        f"┌─────────────────────\n"
        f"│ <b>{index}. {sub['service_name']}</b>\n"
        f"│ {t(lang, 'card_cost')}: <b>{sub['cost']} {sub['currency']}</b>\n"
        f"│ {t(lang, 'card_cycle')}: {cycle_text}\n"
        f"│ {t(lang, 'card_date')}: <code>{sub['next_payment_date']}</code>\n"
        f"│ {t(lang, 'card_remaining')}: {days_text}\n"
        f"└─────────────────────"
    )
    return card

# ============================================================
# ROUTER & HANDLERS
# ============================================================
router = Router()

async def ensure_language(message_or_callback, state: FSMContext = None):
    user_id = message_or_callback.from_user.id
    await ensure_user_exists(user_id)
    lang = await get_lang(user_id)
    return lang

# ── WEB APP DATA HANDLER ──────────────────────────────
@router.message(F.content_type == "web_app_data")
async def web_app_data_handler(message: Message):
    lang = await get_lang(message.from_user.id) or "en"
    try:
        data = json.loads(message.web_app_data.data)
    except Exception as e:
        logger.error(f"Failed to parse web app data: {e}")
        return

    service_name = data.get('service_name', 'Unknown')
    cost = data.get('cost', 0.0)
    currency = data.get('currency', 'USD')
    billing_cycle = data.get('billing_cycle', 'monthly')
    next_payment_date = data.get('next_payment_date')

    try:
        sub_id = await add_subscription(
            user_id=message.from_user.id,
            service_name=service_name,
            cost=float(cost),
            currency=currency,
            billing_cycle=billing_cycle,
            next_payment_date=next_payment_date
        )
    except Exception as e:
        logger.error(f"Failed to add subscription from WebApp: {e}")
        await message.answer(t(lang, "add_error_save"))
        return

    cycle_text = t(lang, billing_cycle)
    success_msg = t(lang, "add_success").format(
        service=service_name, cost=cost, currency=currency,
        cycle=cycle_text, date=next_payment_date, id=sub_id
    )
    
    await message.answer(
        success_msg,
        parse_mode="HTML",
        reply_markup=build_reply_keyboard(lang)
    )

# ── COMMANDS & CALLBACKS ───────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await ensure_language(message)
    if lang is None:
        await message.answer(
            "🌐 <b>Choose your language / اختر اللغة:</b>",
            parse_mode="HTML",
            reply_markup=build_language_keyboard()
        )
    else:
        await message.answer(
            t(lang, "welcome"),
            parse_mode="HTML",
            reply_markup=build_reply_keyboard(lang)
        )

@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("set_lang_", "")
    user_id = callback.from_user.id
    await set_user_language(user_id, lang)
    await state.clear()
    await callback.message.edit_text(t(lang, "language_set"), parse_mode="HTML")
    await callback.message.answer(
        t(lang, "welcome"),
        parse_mode="HTML",
        reply_markup=build_reply_keyboard(lang)
    )
    await callback.answer()

@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await ensure_language(message) or "en"
    await message.answer(t(lang, "help"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = await ensure_language(message) or "en"
    await state.clear()
    await message.answer(t(lang, "cancel_ok"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))

@router.message(Command("language"))
async def cmd_language(message: Message):
    lang = await ensure_language(message) or "en"
    await message.answer(t(lang, "settings_title"), parse_mode="HTML", reply_markup=build_settings_keyboard(lang))

@router.callback_query(F.data == "action_list")
async def cb_list(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    await show_subscriptions(callback.message, callback.from_user.id, lang, edit=True)
    await callback.answer()

@router.callback_query(F.data == "action_total")
async def cb_total(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    await show_total(callback.message, callback.from_user.id, lang, edit=True)
    await callback.answer()

@router.callback_query(F.data == "action_delete")
async def cb_delete(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    await show_delete_menu(callback.message, callback.from_user.id, lang, edit=True)
    await callback.answer()

@router.callback_query(F.data == "action_help")
async def cb_help(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    await callback.message.edit_text(t(lang, "help"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

@router.callback_query(F.data == "action_back")
async def cb_back(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    await state.clear()
    await callback.message.edit_text(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

@router.callback_query(F.data == "action_cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    await state.clear()
    await callback.message.edit_text(t(lang, "cancel_ok"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

@router.message(Command("list"))
async def cmd_list(message: Message):
    lang = await ensure_language(message) or "en"
    await show_subscriptions(message, message.from_user.id, lang, edit=False)

async def show_subscriptions(message: Message, user_id: int, lang: str, edit: bool = False):
    subs = await get_user_subscriptions(user_id)
    if not subs:
        text = t(lang, "list_empty")
        kb = build_main_inline_keyboard(lang)
        if edit: await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else: await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return
    header = t(lang, "list_title").format(count=len(subs))
    cards = [format_subscription_card(sub, i + 1, lang) for i, sub in enumerate(subs)]
    text = header + "\n\n".join(cards)
    kb = build_main_inline_keyboard(lang)
    if edit: await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else: await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("total"))
async def cmd_total(message: Message):
    lang = await ensure_language(message) or "en"
    await show_total(message, message.from_user.id, lang, edit=False)

async def show_total(message: Message, user_id: int, lang: str, edit: bool = False):
    subs = await get_user_subscriptions(user_id)
    if not subs:
        text = t(lang, "total_empty")
        kb = build_main_inline_keyboard(lang)
        if edit: await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else: await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return
    currency_totals = {}
    for sub in subs:
        curr = sub['currency']
        if curr not in currency_totals: currency_totals[curr] = {"monthly": 0.0, "yearly": 0.0}
        if sub['billing_cycle'] == 'monthly':
            currency_totals[curr]["monthly"] += sub['cost']
            currency_totals[curr]["yearly"] += sub['cost'] * 12
        elif sub['billing_cycle'] == 'yearly':
            currency_totals[curr]["monthly"] += sub['cost'] / 12
            currency_totals[curr]["yearly"] += sub['cost']
    text = t(lang, "total_title") + "\n" + t(lang, "total_count").format(len(subs)) + "\n"
    for curr, totals in currency_totals.items():
        text += (f"┌─── <b>{curr}</b> ───\n│ {t(lang, 'total_monthly')}: <b>{totals['monthly']:.2f} {curr}</b>\n"
                 f"│ {t(lang, 'total_yearly')}: <b>{totals['yearly']:.2f} {curr}</b>\n└─────────────────\n\n")
    kb = build_main_inline_keyboard(lang)
    if edit: await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else: await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("delete"))
async def cmd_delete(message: Message):
    lang = await ensure_language(message) or "en"
    await show_delete_menu(message, message.from_user.id, lang, edit=False)

async def show_delete_menu(message: Message, user_id: int, lang: str, edit: bool = False):
    subs = await get_user_subscriptions(user_id)
    if not subs:
        text = t(lang, "delete_empty")
        kb = build_main_inline_keyboard(lang)
        if edit: await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else: await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return
    text = t(lang, "delete_title")
    kb = build_delete_keyboard(subs, lang)
    if edit: await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else: await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("del_"))
async def cb_delete_confirm(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    sub_id = int(callback.data.replace("del_", ""))
    subs = await get_user_subscriptions(callback.from_user.id)
    sub = next((s for s in subs if s['id'] == sub_id), None)
    if not sub:
        await callback.answer(t(lang, "delete_not_found"), show_alert=True)
        return
    text = t(lang, "delete_confirm").format(sub['service_name'], sub['cost'], sub['currency'])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=build_confirm_delete_keyboard(sub_id, lang))
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_del_"))
async def cb_delete_execute(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    sub_id = int(callback.data.replace("confirm_del_", ""))
    success = await delete_subscription(sub_id, callback.from_user.id)
    msg_key = "delete_success" if success else "delete_error"
    await callback.message.edit_text(t(lang, msg_key), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))
    await callback.answer()

# Text-based triggers for persistent menu
@router.message(F.text.in_(["📋 My Subscriptions", "📋 اشتراكاتي"]))
async def reply_btn_list(message: Message):
    lang = await get_lang(message.from_user.id) or "en"
    await show_subscriptions(message, message.from_user.id, lang, edit=False)

@router.message(F.text.in_(["💰 Calculate Total", "💰 حساب التكاليف"]))
async def reply_btn_total(message: Message):
    lang = await get_lang(message.from_user.id) or "en"
    await show_total(message, message.from_user.id, lang, edit=False)

@router.message(F.text.in_(["⚙️ Settings / Language", "⚙️ الإعدادات / اللغة"]))
async def reply_btn_settings(message: Message):
    lang = await get_lang(message.from_user.id) or "en"
    await message.answer(t(lang, "settings_title"), parse_mode="HTML", reply_markup=build_settings_keyboard(lang))

# ============================================================
# AUTOMATED REMINDERS
# ============================================================
async def send_reminders(bot: Bot):
    logger.info("Running scheduled reminder check...")
    reminder_configs = [(1, "reminder_1day", "urgency_1"), (3, "reminder_3days", "urgency_3"), (7, "reminder_7days", "urgency_7")]
    for days, time_key, urgency_key in reminder_configs:
        try:
            subs = await get_due_subscriptions(days)
            for sub in subs:
                try:
                    lang = await get_user_language(sub['user_id']) or "en"
                    time_text, urgency = t(lang, time_key), t(lang, urgency_key)
                    title = t(lang, "reminder_title").format(urgency=urgency)
                    body = t(lang, "reminder_body").format(
                        service=sub['service_name'], cost=sub['cost'], currency=sub['currency'],
                        date=sub['next_payment_date'], time_text=time_text
                    )
                    await bot.send_message(chat_id=sub['user_id'], text=f"{title}\n\n{body}", parse_mode="HTML")
                except Exception as e: logger.error(f"Failed to send reminder to {sub['user_id']}: {e}")
        except Exception as e: logger.error(f"Error checking {days}-day reminders: {e}")
    try:
        past_due = await get_past_due_subscriptions()
        for sub in past_due:
            old_date = datetime.strptime(sub['next_payment_date'], "%Y-%m-%d")
            new_date = old_date + timedelta(days=30 if sub['billing_cycle'] == 'monthly' else 365)
            await update_next_payment_date(sub['id'], new_date.strftime("%Y-%m-%d"))
    except Exception as e: logger.error(f"Error auto-advancing subscriptions: {e}")

# ============================================================
# MENU BUTTON SETUP (THIS IS THE FIX)
# ============================================================

async def set_bot_commands(bot: Bot):
    """Set the bot's command menu AND the main WebApp button."""
    
    # 1. Set the standard slash commands (like /list, /help)
    en_commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="list", description="View all subscriptions"),
        BotCommand(command="total", description="Calculate total costs"),
        BotCommand(command="delete", description="Delete a subscription"),
        BotCommand(command="language", description="Change language"),
        BotCommand(command="help", description="Usage guide"),
    ]
    await bot.set_my_commands(en_commands)

    # 2. SET THE CHAT MENU BUTTON (This makes the WebApp button appear next to input)
    # This overrides the blue "Menu" button with your App button
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="➕ Add Sub",  # النص الذي سيظهر على الزر
            web_app=WebAppInfo(url=WEB_APP_URL)
        )
    )
    
    logger.info("Bot commands and Menu Button set successfully.")


# ============================================================
# MAIN
# ============================================================
async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    
    # Set menu button on startup
    await set_bot_commands(bot)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, 'interval', hours=24, args=[bot], id='daily_reminders', replace_existing=True)
    scheduler.start()

    logger.info("Bot v2.2 is starting...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

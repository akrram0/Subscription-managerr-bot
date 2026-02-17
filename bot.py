"""
Subscription Management Bot — v2.4 (Fixed Reminders & Charts)
=============================================================
Updates:
- Fixed 'NameError: send_reminders' issue.
- Includes Matplotlib Charts.
- Includes Mini App integration.
"""

import asyncio
import logging
import io
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 📊 Matplotlib for Charts
# ---------------------------------------------------------
import matplotlib
matplotlib.use('Agg')  # Essential for servers
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, WebAppInfo, MenuButtonWebApp, BufferedInputFile
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import (
    init_db, get_user_language, set_user_language, ensure_user_exists,
    add_subscription, get_user_subscriptions, delete_subscription,
    get_due_subscriptions, get_past_due_subscriptions, update_next_payment_date
)
from locales import t

# ============================================================
# CONFIGURATION
# ============================================================
BOT_TOKEN = "8304071879:AAHP5ST3SHAoxTGbTJ1yVG58VjbOWvQ343c"

# تأكد أن هذا الرابط صحيح ويشير إلى Netlify الخاص بك
WEB_APP_URL = "https://glistening-gaufre-57bb50.netlify.app/index.html" 

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

CURRENCIES = ["USD", "SAR", "EGP", "AED", "KWD", "QAR", "BHD", "OMR", "JOD", "EUR", "GBP"]

# ============================================================
# CHART GENERATOR 📊
# ============================================================
def generate_pie_chart(subs, lang):
    """Generates a pie chart image buffer from subscriptions."""
    if not subs:
        return None

    labels = []
    sizes = []
    
    for sub in subs:
        cost = sub['cost']
        # Convert yearly to monthly for the chart view
        if sub['billing_cycle'] == 'yearly':
            cost = cost / 12
        
        labels.append(sub['service_name'])
        sizes.append(cost)

    fig, ax = plt.subplots(figsize=(6, 6))
    
    # Colors suitable for dark/light themes
    colors = ['#3390ec', '#e05050', '#7ec87e', '#f0a050', '#8b5cf6', '#d4621e']
    
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct='%1.1f%%',
        startangle=90, colors=colors[:len(labels)],
        textprops={'color': "black", 'weight': 'bold'}
    )
    
    title = "Monthly Expense Distribution" if lang != 'ar' else "توزيع المصاريف الشهرية"
    ax.set_title(title, fontsize=14, pad=20)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', transparent=False)
    buf.seek(0)
    plt.close(fig)
    return buf

# ============================================================
# KEYBOARD BUILDERS
# ============================================================

def build_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
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

def build_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ar":
        buttons = [[InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
                    InlineKeyboardButton(text="🇸🇦 العربية ✓", callback_data="set_lang_ar")]]
    else:
        buttons = [[InlineKeyboardButton(text="🇬🇧 English ✓", callback_data="set_lang_en"),
                    InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar")]]
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_confirm_delete_keyboard(sub_id: int, lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=t(lang, "delete_yes"), callback_data=f"confirm_del_{sub_id}"),
         InlineKeyboardButton(text=t(lang, "delete_no"), callback_data="action_delete")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_delete_keyboard(subs: list, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for sub in subs:
        text = f"🗑 {sub['service_name']} — {sub['cost']} {sub['currency']}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"del_{sub['id']}")])
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
# HELPERS
# ============================================================
async def get_lang(user_id: int) -> str:
    return await get_user_language(user_id)

async def ensure_language(message_or_callback, state: FSMContext = None):
    user_id = message_or_callback.from_user.id
    await ensure_user_exists(user_id)
    lang = await get_lang(user_id)
    return lang

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

    return (
        f"┌─────────────────────\n"
        f"│ <b>{index}. {sub['service_name']}</b>\n"
        f"│ {t(lang, 'card_cost')}: <b>{sub['cost']} {sub['currency']}</b>\n"
        f"│ {t(lang, 'card_cycle')}: {cycle_text}\n"
        f"│ {t(lang, 'card_date')}: <code>{sub['next_payment_date']}</code>\n"
        f"│ {t(lang, 'card_remaining')}: {days_text}\n"
        f"└─────────────────────"
    )

# ============================================================
# ROUTER & HANDLERS
# ============================================================
router = Router()

# ── WEB APP DATA HANDLER ──────────────────────────────
@router.message(F.content_type == "web_app_data")
async def web_app_data_handler(message: Message):
    lang = await get_lang(message.from_user.id) or "en"
    try:
        data = json.loads(message.web_app_data.data)
        sub_id = await add_subscription(
            user_id=message.from_user.id,
            service_name=data['service_name'],
            cost=float(data['cost']),
            currency=data['currency'],
            billing_cycle=data['billing_cycle'],
            next_payment_date=data['next_payment_date']
        )
        
        cycle_text = t(lang, data['billing_cycle'])
        success_msg = t(lang, "add_success").format(
            service=data['service_name'], cost=data['cost'], currency=data['currency'],
            cycle=cycle_text, date=data['next_payment_date'], id=sub_id
        )
        await message.answer(success_msg, parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
    except Exception as e:
        logger.error(f"Failed to add subscription from WebApp: {e}")
        await message.answer(t(lang, "add_error_save"))

# ── COMMANDS & CALLBACKS ───────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await ensure_language(message)
    if lang is None:
        await message.answer("🌐 <b>Choose your language / اختر اللغة:</b>", parse_mode="HTML", reply_markup=build_language_keyboard())
    else:
        await message.answer(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))

@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("set_lang_", "")
    await set_user_language(callback.from_user.id, lang)
    await state.clear()
    await callback.message.edit_text(t(lang, "language_set"), parse_mode="HTML")
    await callback.message.answer(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
    await callback.answer()

@router.message(Command("list"))
@router.callback_query(F.data == "action_list")
@router.message(F.text.in_(["📋 My Subscriptions", "📋 اشتراكاتي"]))
async def list_handler(event):
    msg = event.message if isinstance(event, CallbackQuery) else event
    user_id = event.from_user.id
    lang = await get_lang(user_id) or "en"
    
    subs = await get_user_subscriptions(user_id)
    if not subs:
        text = t(lang, "list_empty")
        kb = build_main_inline_keyboard(lang)
    else:
        header = t(lang, "list_title").format(count=len(subs))
        cards = [format_subscription_card(sub, i + 1, lang) for i, sub in enumerate(subs)]
        text = header + "\n\n".join(cards)
        kb = build_main_inline_keyboard(lang)

    if isinstance(event, CallbackQuery):
        await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await msg.answer(text, parse_mode="HTML", reply_markup=kb)

# ⚠️ TOTAL with CHARTS Handler
@router.message(Command("total"))
@router.callback_query(F.data == "action_total")
@router.message(F.text.in_(["💰 Calculate Total", "💰 حساب التكاليف"]))
async def total_handler(event):
    msg = event.message if isinstance(event, CallbackQuery) else event
    user_id = event.from_user.id
    lang = await get_lang(user_id) or "en"
    
    subs = await get_user_subscriptions(user_id)
    kb = build_main_inline_keyboard(lang)

    if not subs:
        text = t(lang, "total_empty")
        if isinstance(event, CallbackQuery): await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else: await msg.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    # Calculate Totals
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

    # Generate Chart
    chart_buf = generate_pie_chart(subs, lang)
    
    if chart_buf:
        # If updating via callback, we must delete old message to send photo
        if isinstance(event, CallbackQuery): await msg.delete()
        
        await msg.answer_photo(
            photo=BufferedInputFile(chart_buf.read(), filename="chart.png"),
            caption=text,
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        if isinstance(event, CallbackQuery): await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else: await msg.answer(text, parse_mode="HTML", reply_markup=kb)
    
    if isinstance(event, CallbackQuery): await event.answer()

@router.message(Command("delete"))
@router.callback_query(F.data == "action_delete")
async def delete_menu(event):
    msg = event.message if isinstance(event, CallbackQuery) else event
    user_id = event.from_user.id
    lang = await get_lang(user_id) or "en"
    
    subs = await get_user_subscriptions(user_id)
    if not subs:
        if isinstance(event, CallbackQuery): await msg.edit_text(t(lang, "delete_empty"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))
        else: await msg.answer(t(lang, "delete_empty"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))
    else:
        kb = build_delete_keyboard(subs, lang)
        if isinstance(event, CallbackQuery): await msg.edit_text(t(lang, "delete_title"), parse_mode="HTML", reply_markup=kb)
        else: await msg.answer(t(lang, "delete_title"), parse_mode="HTML", reply_markup=kb)
    
    if isinstance(event, CallbackQuery): await event.answer()

@router.callback_query(F.data.startswith("del_"))
async def cb_delete_confirm(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    sub_id = int(callback.data.replace("del_", ""))
    subs = await get_user_subscriptions(callback.from_user.id)
    sub = next((s for s in subs if s['id'] == sub_id), None)
    if sub:
        text = t(lang, "delete_confirm").format(sub['service_name'], sub['cost'], sub['currency'])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=build_confirm_delete_keyboard(sub_id, lang))
    else:
        await callback.answer(t(lang, "delete_not_found"), show_alert=True)

@router.callback_query(F.data.startswith("confirm_del_"))
async def cb_delete_execute(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    sub_id = int(callback.data.replace("confirm_del_", ""))
    success = await delete_subscription(sub_id, callback.from_user.id)
    msg = t(lang, "delete_success") if success else t(lang, "delete_error")
    await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

@router.message(Command("language"))
@router.message(F.text.in_(["⚙️ Settings / Language", "⚙️ الإعدادات / اللغة"]))
async def settings_handler(message: Message):
    lang = await get_lang(message.from_user.id) or "en"
    await message.answer(t(lang, "settings_title"), parse_mode="HTML", reply_markup=build_settings_keyboard(lang))

@router.callback_query(F.data == "action_help")
@router.message(Command("help"))
async def help_handler(event):
    msg = event.message if isinstance(event, CallbackQuery) else event
    lang = await get_lang(event.from_user.id) or "en"
    text = t(lang, "help")
    kb = build_main_inline_keyboard(lang)
    if isinstance(event, CallbackQuery): await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else: await msg.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("cancel"))
@router.callback_query(F.data == "action_cancel")
async def cancel_handler(event, state: FSMContext):
    msg = event.message if isinstance(event, CallbackQuery) else event
    lang = await get_lang(event.from_user.id) or "en"
    await state.clear()
    await msg.answer(t(lang, "cancel_ok"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
    if isinstance(event, CallbackQuery): await event.answer()

@router.callback_query(F.data == "action_back")
async def back_handler(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    await callback.message.edit_text(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

# ============================================================
# AUTOMATED REMINDERS (كانت مفقودة، تمت إعادتها الآن) ✅
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
                    time_text = t(lang, time_key)
                    urgency = t(lang, urgency_key)
                    title = t(lang, "reminder_title").format(urgency=urgency)
                    body = t(lang, "reminder_body").format(
                        service=sub['service_name'], cost=sub['cost'], currency=sub['currency'],
                        date=sub['next_payment_date'], time_text=time_text
                    )
                    await bot.send_message(chat_id=sub['user_id'], text=f"{title}\n\n{body}", parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {sub['user_id']}: {e}")
        except Exception as e:
            logger.error(f"Error checking {days}-day reminders: {e}")

    # Auto-advance past due
    try:
        past_due = await get_past_due_subscriptions()
        for sub in past_due:
            old_date = datetime.strptime(sub['next_payment_date'], "%Y-%m-%d")
            new_date = old_date + timedelta(days=30 if sub['billing_cycle'] == 'monthly' else 365)
            await update_next_payment_date(sub['id'], new_date.strftime("%Y-%m-%d"))
    except Exception as e:
        logger.error(f"Error auto-advancing: {e}")

# ============================================================
# MAIN
# ============================================================
async def set_bot_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Start"),
        BotCommand(command="list", description="List Subs"),
        BotCommand(command="total", description="Expenses & Charts"),
    ])
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="➕ Add Sub", web_app=WebAppInfo(url=WEB_APP_URL))
    )

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    await set_bot_commands(bot)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, 'interval', hours=24, args=[bot], id='daily_reminders', replace_existing=True)
    scheduler.start()

    logger.info("Bot v2.4 (Charts Fixed) is starting...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

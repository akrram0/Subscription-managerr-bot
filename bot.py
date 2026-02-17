"""
Subscription Management Bot — v3.0 (Final Fixes)
================================================
Based on Code Review & Log Analysis:
1. [span_7](start_span)[span_8](start_span)Fixed Reminder System (Sends alerts & Auto-advances dates)[span_7](end_span)[span_8](end_span)
2. [span_9](start_span)Fixed Total Calculation (Groups by Currency/Cycle)[span_9](end_span)
3. [span_10](start_span)Fixed Delete Confirmation (Shows real data)[span_10](end_span)
4. [span_11](start_span)[span_12](start_span)Added Input Validation & Error Handling[span_11](end_span)[span_12](end_span)
5. [span_13](start_span)[span_14](start_span)Added Missing Handlers (/language, /help, Settings Button)[span_13](end_span)[span_14](end_span)
"""

import asyncio
import logging
import io
import os
import sys
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 📊 Matplotlib for Charts
# ---------------------------------------------------------
import matplotlib
matplotlib.use('Agg')
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
from aiogram.fsm.state import State, StatesGroup
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
# [span_15](start_span)CRITICAL FIX: Prefer Environment Variable, fallback to hardcoded (Change this!)[span_15](end_span)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8304071879:AAHP5ST3SHAoxTGbTJ1yVG58VjbOWvQ343c")
# WEB APP URL
WEB_APP_URL = "https://glistening-gaufre-57bb50.netlify.app/index.html"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

CURRENCIES = ["USD", "SAR", "EGP", "AED", "KWD", "QAR", "BHD", "OMR", "JOD", "EUR", "GBP"]

# ============================================================
# FSM STATES
# ============================================================
class AddSubscription(StatesGroup):
    waiting_for_service_name = State()
    waiting_for_cost = State()
    waiting_for_currency = State()
    waiting_for_billing_cycle = State()
    waiting_for_payment_date = State()

# ============================================================
# CHART GENERATOR
# ============================================================
def generate_pie_chart(subs, lang):
    if not subs: return None
    labels = []
    sizes = []
    for sub in subs:
        cost = sub['cost']
        # Normalize yearly to monthly for chart visualization
        if sub['billing_cycle'] == 'yearly': 
            cost = cost / 12
        labels.append(sub['service_name'])
        sizes.append(cost)

    fig, ax = plt.subplots(figsize=(6, 6))
    colors = ['#3390ec', '#e05050', '#7ec87e', '#f0a050', '#8b5cf6', '#d4621e']
    
    try:
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, 
               colors=colors[:len(labels)], textprops={'color': "black", 'weight': 'bold'})
        
        title = "Monthly Distribution (Approx)" if lang != 'ar' else "توزيع المصاريف الشهرية (تقريبي)"
        ax.set_title(title, fontsize=14, pad=20)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', transparent=False)
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.error(f"Chart generation failed: {e}")
        return None

# ============================================================
# KEYBOARDS
# ============================================================
def build_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=t(lang, "btn_add"), web_app=WebAppInfo(url=WEB_APP_URL)),
         KeyboardButton(text=t(lang, "btn_list"))],
        [KeyboardButton(text=t(lang, "btn_total")),
         KeyboardButton(text=t(lang, "btn_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def build_currency_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for currency in CURRENCIES:
        row.append(InlineKeyboardButton(text=currency, callback_data=f"currency_{currency}"))
        if len(row) == 3:
            buttons.append(row); row = []
    if row: buttons.append(row)
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

def build_language_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
                InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_main_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=t(lang, "btn_add_inline"), web_app=WebAppInfo(url=WEB_APP_URL)),
         InlineKeyboardButton(text=t(lang, "btn_list_inline"), callback_data="action_list")],
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

def build_delete_keyboard(subs: list, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for sub in subs:
        text = f"🗑 {sub['service_name']} — {sub['cost']} {sub['currency']}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"del_{sub['id']}")])
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_confirm_delete_keyboard(sub_id: int, lang: str) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=t(lang, "delete_yes"), callback_data=f"confirm_del_{sub_id}"),
                InlineKeyboardButton(text=t(lang, "delete_no"), callback_data="action_delete")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
# HELPERS
# ============================================================
async def get_lang(user_id: int) -> str:
    return await get_user_language(user_id) or "en"

async def ensure_language(message_or_callback, state: FSMContext = None):
    user_id = message_or_callback.from_user.id
    await ensure_user_exists(user_id)
    lang = await get_lang(user_id)
    return lang

def format_subscription_card(sub, index, lang):
    [span_16](start_span)"""Refined subscription card format[span_16](end_span)"""
    cycle_text = t(lang, sub['billing_cycle'])
    try:
        payment_date = datetime.strptime(sub['next_payment_date'], "%Y-%m-%d")
        days_left = (payment_date - datetime.now()).days
        if days_left < 0: days_text = t(lang, "days_overdue")
        elif days_left == 0: days_text = t(lang, "days_today")
        elif days_left == 1: days_text = t(lang, "days_tomorrow")
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
# ROUTER
# ============================================================
router = Router()

# ── 1. WEB APP HANDLER ──
@router.message(F.content_type == "web_app_data")
async def web_app_data_handler(message: Message):
    lang = await get_lang(message.from_user.id)
    try:
        data = json.loads(message.web_app_data.data)
        # [span_17](start_span)Add basic validation[span_17](end_span)
        if float(data['cost']) < 0: raise ValueError("Negative Cost")
        
        sub_id = await add_subscription(
            message.from_user.id, data['service_name'], float(data['cost']),
            data['currency'], data['billing_cycle'], data['next_payment_date']
        )
        
        cycle_text = t(lang, data['billing_cycle'])
        success_msg = t(lang, "add_success").format(
            service=data['service_name'], cost=data['cost'], currency=data['currency'],
            cycle=cycle_text, date=data['next_payment_date'], id=sub_id
        )
        await message.answer(success_msg, parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
        # [span_18](start_span)Log action[span_18](end_span)
        logger.info(f"User {message.from_user.id} added sub via WebApp: {data['service_name']}")
    except Exception as e:
        logger.error(f"WebApp Error: {e}")
        await message.answer(t(lang, "add_error_save"), parse_mode="HTML")

# ── 2. MANUAL ADD (FSM) ──
@router.message(Command("add"))
async def cmd_add_manual(message: Message, state: FSMContext):
    lang = await ensure_language(message)
    await state.set_state(AddSubscription.waiting_for_service_name)
    await message.answer(
        f"{t(lang, 'add_title')}\n\n{t(lang, 'add_step1')}",
        parse_mode="HTML", 
        reply_markup=build_cancel_keyboard(lang)
    )

@router.message(StateFilter(AddSubscription.waiting_for_service_name))
async def process_service_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    [span_19](start_span)if not message.text or len(message.text) > 100: # Added validation[span_19](end_span)
        await message.answer(t(lang, "add_error_name"), parse_mode="HTML")
        return
    await state.update_data(service_name=message.text)
    await state.set_state(AddSubscription.waiting_for_cost)
    await message.answer(t(lang, "add_step2_ok").format(message.text), parse_mode="HTML", reply_markup=build_cancel_keyboard(lang))

@router.message(StateFilter(AddSubscription.waiting_for_cost))
async def process_cost(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    try:
        cost = float(message.text.replace(",", "."))
        [span_20](start_span)if cost <= 0: raise ValueError # Validation[span_20](end_span)
        await state.update_data(cost=cost)
        await state.set_state(AddSubscription.waiting_for_currency)
        await message.answer(t(lang, "add_step3_ok").format(cost), parse_mode="HTML", reply_markup=build_currency_keyboard())
    except ValueError:
        await message.answer(t(lang, "add_error_cost"), parse_mode="HTML")

@router.callback_query(StateFilter(AddSubscription.waiting_for_currency), F.data.startswith("currency_"))
async def process_currency(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    curr = callback.data.split("_")[1]
    await state.update_data(currency=curr)
    await state.set_state(AddSubscription.waiting_for_billing_cycle)
    await callback.message.edit_text(t(lang, "add_step4_ok").format(curr), parse_mode="HTML", reply_markup=build_billing_cycle_keyboard(lang))

@router.callback_query(StateFilter(AddSubscription.waiting_for_billing_cycle), F.data.startswith("cycle_"))
async def process_cycle(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    cycle = callback.data.split("_")[1]
    await state.update_data(billing_cycle=cycle)
    await state.set_state(AddSubscription.waiting_for_payment_date)
    today = datetime.now().strftime("%Y-%m-%d")
    await callback.message.edit_text(t(lang, "add_step5_ok").format(t(lang, cycle), today), parse_mode="HTML")

@router.message(StateFilter(AddSubscription.waiting_for_payment_date))
async def process_date(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    try:
        date_obj = datetime.strptime(message.text.strip(), "%Y-%m-%d")
        # [span_21](start_span)Validation for past dates[span_21](end_span)
        if date_obj.date() < datetime.now().date():
             await message.answer(t(lang, "add_error_date_past"), parse_mode="HTML")
             return
             
        data = await state.get_data()
        sub_id = await add_subscription(
            message.from_user.id, data['service_name'], data['cost'],
            data['currency'], data['billing_cycle'], message.text.strip()
        )
        cycle_text = t(lang, data['billing_cycle'])
        success_msg = t(lang, "add_success").format(
            service=data['service_name'], cost=data['cost'], currency=data['currency'],
            cycle=cycle_text, date=message.text.strip(), id=sub_id
        )
        await state.clear()
        await message.answer(success_msg, parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
    except ValueError:
        await message.answer(t(lang, "add_error_date_format"), parse_mode="HTML")

# ── COMMANDS & MENUS ──

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await ensure_language(message)
    if not lang:
        await message.answer("🌐 <b>Choose Language:</b>", parse_mode="HTML", reply_markup=build_language_keyboard())
    else:
        await message.answer(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))

@router.callback_query(F.data.startswith("set_lang_"))
async def cb_lang(callback: CallbackQuery):
    lang = callback.data.split("_")[2]
    await set_user_language(callback.from_user.id, lang)
    await callback.message.answer(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
    await callback.answer()

# [span_22](start_span)FIX: Added missing /language and /help handlers[span_22](end_span)
@router.message(Command("language"))
[span_23](start_span)@router.message(F.text.in_(["⚙️ Settings / Language", "⚙️ الإعدادات / اللغة"])) # Added Button Handler[span_23](end_span)
async def settings_handler(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(t(lang, "settings_title"), parse_mode="HTML", reply_markup=build_settings_keyboard(lang))

@router.message(Command("help"))
@router.callback_query(F.data == "action_help")
async def help_handler(event):
    msg = event.message if isinstance(event, CallbackQuery) else event
    lang = await get_lang(event.from_user.id)
    text = t(lang, "help")
    kb = build_main_inline_keyboard(lang)
    if isinstance(event, CallbackQuery): await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else: await msg.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("list"))
@router.callback_query(F.data == "action_list")
@router.message(F.text.in_(["📋 My Subscriptions", "📋 اشتراكاتي"]))
async def list_subs(event):
    msg = event.message if isinstance(event, CallbackQuery) else event
    user_id = event.from_user.id
    lang = await get_lang(user_id)
    subs = await get_user_subscriptions(user_id)
    
    kb = build_main_inline_keyboard(lang)
    if not subs:
        text = t(lang, "list_empty")
    else:
        text = t(lang, "list_title").format(count=len(subs)) + "\n\n"
        for i, sub in enumerate(subs):
            text += format_subscription_card(sub, i+1, lang) + "\n"
    
    if isinstance(event, CallbackQuery): await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else: await msg.answer(text, parse_mode="HTML", reply_markup=kb)

# [span_24](start_span)FIX: Total Calculation Grouped by Currency[span_24](end_span)
@router.message(Command("total"))
@router.callback_query(F.data == "action_total")
@router.message(F.text.in_(["💰 Calculate Total", "💰 حساب التكاليف"]))
async def total_subs(event):
    msg = event.message if isinstance(event, CallbackQuery) else event
    user_id = event.from_user.id
    lang = await get_lang(user_id)
    subs = await get_user_subscriptions(user_id)
    kb = build_main_inline_keyboard(lang)

    if not subs:
        await msg.answer(t(lang, "total_empty"), parse_mode="HTML", reply_markup=kb)
        return

    # Proper Grouping
    monthly_totals = {}
    yearly_totals = {}

    for sub in subs:
        curr = sub['currency']
        cost = sub['cost']
        if sub['billing_cycle'] == 'monthly':
            monthly_totals[curr] = monthly_totals.get(curr, 0) + cost
        elif sub['billing_cycle'] == 'yearly':
            yearly_totals[curr] = yearly_totals.get(curr, 0) + cost

    text = t(lang, "total_title") + "\n"
    if monthly_totals:
        text += f"<b>{t(lang, 'total_monthly')}:</b>\n"
        for curr, val in monthly_totals.items():
            text += f"- {val:.2f} {curr}\n"
    
    if yearly_totals:
        text += f"\n<b>{t(lang, 'total_yearly')}:</b>\n"
        for curr, val in yearly_totals.items():
            text += f"- {val:.2f} {curr}\n"

    # Chart
    chart_buf = generate_pie_chart(subs, lang)
    
    if chart_buf:
        if isinstance(event, CallbackQuery): await msg.delete()
        await msg.answer_photo(BufferedInputFile(chart_buf.read(), filename="chart.png"), caption=text, parse_mode="HTML", reply_markup=kb)
    else:
        if isinstance(event, CallbackQuery): await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else: await msg.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("delete"))
@router.callback_query(F.data == "action_delete")
async def delete_menu(event):
    msg = event.message if isinstance(event, CallbackQuery) else event
    user_id = event.from_user.id
    lang = await get_lang(user_id)
    subs = await get_user_subscriptions(user_id)
    
    if not subs:
        await msg.answer(t(lang, "delete_empty"), parse_mode="HTML")
    else:
        await msg.answer(t(lang, "delete_title"), parse_mode="HTML", reply_markup=build_delete_keyboard(subs, lang))

# [span_25](start_span)FIX: Delete shows actual data[span_25](end_span)
@router.callback_query(F.data.startswith("del_"))
async def confirm_del(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    sub_id = int(callback.data.split("_")[1])
    
    # Fetch real details
    subs = await get_user_subscriptions(callback.from_user.id)
    sub = next((s for s in subs if s['id'] == sub_id), None)
    
    if sub:
        text = t(lang, "delete_confirm").format(sub['service_name'], sub['cost'], sub['currency'])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=build_confirm_delete_keyboard(sub_id, lang))
    else:
        await callback.message.edit_text(t(lang, "delete_not_found"), parse_mode="HTML")

@router.callback_query(F.data.startswith("confirm_del_"))
async def exec_del(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    sub_id = int(callback.data.split("del_")[1])
    success = await delete_subscription(sub_id, callback.from_user.id)
    msg = t(lang, "delete_success") if success else t(lang, "delete_error")
    await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

@router.message(Command("cancel"))
@router.callback_query(F.data == "action_cancel")
async def cancel_op(event, state: FSMContext):
    await state.clear()
    msg = event.message if isinstance(event, CallbackQuery) else event
    [span_26](start_span)lang = await get_lang(event.from_user.id) # Fix Language in cancel[span_26](end_span)
    await msg.answer(t(lang, "cancel_ok"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
    if isinstance(event, CallbackQuery): await event.answer()
    
@router.callback_query(F.data == "action_back")
async def back_handler(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await callback.message.edit_text(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

# ============================================================
# [span_27](start_span)[span_28](start_span)AUTOMATED REMINDERS & AUTO-ADVANCE[span_27](end_span)[span_28](end_span)
# ============================================================
async def send_reminders(bot: Bot):
    logger.info("Running scheduled reminder check...")
    
    # 1. Send Reminders
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

    # 2. [span_29](start_span)Auto-Advance Past Due Dates[span_29](end_span)
    try:
        past_due = await get_past_due_subscriptions()
        for sub in past_due:
            old_date = datetime.strptime(sub['next_payment_date'], "%Y-%m-%d")
            # Advance based on cycle
            if sub['billing_cycle'] == 'monthly':
                new_date = old_date + timedelta(days=30)
            elif sub['billing_cycle'] == 'yearly':
                new_date = old_date + timedelta(days=365)
            else:
                new_date = old_date + timedelta(days=30) # Default
            
            await update_next_payment_date(sub['id'], new_date.strftime("%Y-%m-%d"))
            logger.info(f"Auto-advanced sub {sub['id']} to {new_date.strftime('%Y-%m-%d')}")
            
            # Optional: Notify user
            # await bot.send_message(sub['user_id'], f"Renewed {sub['service_name']} to {new_date.date()}")
    except Exception as e:
        logger.error(f"Error auto-advancing: {e}")

# ============================================================
# MAIN
# ============================================================
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Start"),
        BotCommand(command="add", description="Add Subscription"),
        BotCommand(command="list", description="List Subscriptions"),
        BotCommand(command="total", description="Expenses & Charts"),
        [span_30](start_span)BotCommand(command="language", description="Change Language"), # Added[span_30](end_span)
        BotCommand(command="help", description="Help"),
    ]
    await bot.set_my_commands(commands)
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="➕ Add Sub", web_app=WebAppInfo(url=WEB_APP_URL)))

async def main():
    await init_db()
    
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is missing!")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    [span_31](start_span)await set_bot_commands(bot) # Set commands[span_31](end_span)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, 'interval', hours=24, args=[bot], id='reminders_job')
    scheduler.start()

    logger.info("Bot v3.0 (Fixed) is starting...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Polling error: {e}")
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")

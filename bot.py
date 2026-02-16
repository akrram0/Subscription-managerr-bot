import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiohttp import web  # <--- Added for Master Bot communication

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    BotCommand
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import the new function get_global_stats
from database import (
    init_db, get_user_language, set_user_language, ensure_user_exists,
    add_subscription, get_user_subscriptions, delete_subscription,
    get_due_subscriptions, get_past_due_subscriptions, update_next_payment_date,
    get_global_stats 
)
from locales import t, TEXTS

# ============================================================
# CONFIGURATION
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Use Environment Variable for security

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
CURRENCIES = ["USD", "SAR", "EGP", "AED", "KWD", "QAR", "BHD", "OMR", "JOD", "EUR", "GBP"]

# ============================================================
# FSM STATES & HELPERS (Keep your existing code logic)
# ============================================================
class AddSubscription(StatesGroup):
    waiting_for_service_name = State()
    waiting_for_cost = State()
    waiting_for_currency = State()
    waiting_for_billing_cycle = State()
    waiting_for_payment_date = State()

def build_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=t(lang, "btn_add")), KeyboardButton(text=t(lang, "btn_list"))],
        [KeyboardButton(text=t(lang, "btn_total")), KeyboardButton(text=t(lang, "btn_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def build_language_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
                InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_main_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=t(lang, "btn_add_inline"), callback_data="action_add"),
         InlineKeyboardButton(text=t(lang, "btn_list_inline"), callback_data="action_list")],
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
    if row: buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_billing_cycle_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=t(lang, "cycle_monthly"), callback_data="cycle_monthly"),
                InlineKeyboardButton(text=t(lang, "cycle_yearly"), callback_data="cycle_yearly")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="action_cancel")]])

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

def build_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ar":
        buttons = [[InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
                    InlineKeyboardButton(text="🇸🇦 العربية ✓", callback_data="set_lang_ar")]]
    else:
        buttons = [[InlineKeyboardButton(text="🇬🇧 English ✓", callback_data="set_lang_en"),
                    InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar")]]
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
    except ValueError: days_text = "—"

    return (f"┌─────────────────────\n│ <b>{index}. {sub['service_name']}</b>\n"
            f"│ {t(lang, 'card_cost')}: <b>{sub['cost']} {sub['currency']}</b>\n"
            f"│ {t(lang, 'card_cycle')}: {cycle_text}\n"
            f"│ {t(lang, 'card_date')}: <code>{sub['next_payment_date']}</code>\n"
            f"│ {t(lang, 'card_remaining')}: {days_text}\n└─────────────────────")

# ============================================================
# ROUTER & HANDLERS
# ============================================================
router = Router()

async def ensure_language(message_or_callback, state: FSMContext = None):
    user_id = message_or_callback.from_user.id
    await ensure_user_exists(user_id)
    return await get_lang(user_id)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await ensure_language(message)
    if lang is None:
        await message.answer("🌐 <b>Choose your language / اختر اللغة:</b>", parse_mode="HTML", reply_markup=build_language_keyboard())
    else:
        await message.answer(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
        await message.answer("👇", reply_markup=build_main_inline_keyboard(lang))

@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.replace("set_lang_", "")
    await set_user_language(callback.from_user.id, lang)
    await state.clear()
    await callback.message.edit_text(t(lang, "language_set"), parse_mode="HTML")
    await callback.message.answer(t(lang, "welcome"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))
    await callback.message.answer("👇", reply_markup=build_main_inline_keyboard(lang))
    await callback.answer()

@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await ensure_language(message) or "en"
    await message.answer(t(lang, "help"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = await ensure_language(message) or "en"
    if await state.get_state() is None:
        await message.answer(t(lang, "cancel_none"), reply_markup=build_reply_keyboard(lang))
        return
    await state.clear()
    await message.answer(t(lang, "cancel_ok"), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))

@router.message(Command("language"))
async def cmd_language(message: Message):
    lang = await ensure_language(message) or "en"
    await message.answer(t(lang, "settings_title"), parse_mode="HTML", reply_markup=build_settings_keyboard(lang))

# Inline Actions
@router.callback_query(F.data == "action_add")
async def cb_add(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    await state.set_state(AddSubscription.waiting_for_service_name)
    await callback.message.edit_text(f"{t(lang, 'add_title')}\n\n{t(lang, 'add_step1')}", parse_mode="HTML", reply_markup=build_cancel_keyboard(lang))
    await callback.answer()

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
    await callback.answer()

@router.callback_query(F.data == "action_back")
@router.callback_query(F.data == "action_cancel")
async def cb_reset(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    await state.clear()
    msg = t(lang, "welcome") if callback.data == "action_back" else t(lang, "cancel_ok")
    await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))
    await callback.answer()

# FSM ADD FLOW
@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    lang = await ensure_language(message) or "en"
    await state.set_state(AddSubscription.waiting_for_service_name)
    await message.answer(f"{t(lang, 'add_title')}\n\n{t(lang, 'add_step1')}", parse_mode="HTML", reply_markup=build_cancel_keyboard(lang))

@router.message(StateFilter(AddSubscription.waiting_for_service_name))
async def fsm_service_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id) or "en"
    service_name = message.text.strip()
    if not service_name or len(service_name) > 100:
        await message.answer(t(lang, "add_error_name"), reply_markup=build_cancel_keyboard(lang))
        return
    await state.update_data(service_name=service_name)
    await state.set_state(AddSubscription.waiting_for_cost)
    await message.answer(t(lang, "add_step2_ok").format(service_name), parse_mode="HTML", reply_markup=build_cancel_keyboard(lang))

@router.message(StateFilter(AddSubscription.waiting_for_cost))
async def fsm_cost(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id) or "en"
    try:
        cost = float(message.text.strip().replace(",", "."))
        if cost <= 0: raise ValueError
    except (ValueError, TypeError):
        await message.answer(t(lang, "add_error_cost"), reply_markup=build_cancel_keyboard(lang))
        return
    await state.update_data(cost=cost)
    await state.set_state(AddSubscription.waiting_for_currency)
    await message.answer(t(lang, "add_step3_ok").format(cost), parse_mode="HTML", reply_markup=build_currency_keyboard())

@router.callback_query(StateFilter(AddSubscription.waiting_for_currency), F.data.startswith("currency_"))
async def fsm_currency(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    currency = callback.data.replace("currency_", "")
    await state.update_data(currency=currency)
    await state.set_state(AddSubscription.waiting_for_billing_cycle)
    await callback.message.edit_text(t(lang, "add_step4_ok").format(currency), parse_mode="HTML", reply_markup=build_billing_cycle_keyboard(lang))
    await callback.answer()

@router.callback_query(StateFilter(AddSubscription.waiting_for_billing_cycle), F.data.startswith("cycle_"))
async def fsm_billing_cycle(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    cycle = callback.data.replace("cycle_", "")
    await state.update_data(billing_cycle=cycle)
    await state.set_state(AddSubscription.waiting_for_payment_date)
    suggested_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    await callback.message.edit_text(t(lang, "add_step5_ok").format(t(lang, cycle), suggested_date), parse_mode="HTML")
    await callback.answer()

@router.message(StateFilter(AddSubscription.waiting_for_payment_date))
async def fsm_payment_date(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id) or "en"
    try:
        payment_date = datetime.strptime(message.text.strip(), "%Y-%m-%d")
        if payment_date.date() < datetime.now().date():
            await message.answer(t(lang, "add_error_date_past"), reply_markup=build_cancel_keyboard(lang))
            return
    except ValueError:
        await message.answer(t(lang, "add_error_date_format"), parse_mode="HTML", reply_markup=build_cancel_keyboard(lang))
        return

    data = await state.get_data()
    try:
        sub_id = await add_subscription(message.from_user.id, data['service_name'], data['cost'], data['currency'], data['billing_cycle'], message.text.strip())
    except Exception as e:
        logger.error(f"Failed to add: {e}")
        await message.answer(t(lang, "add_error_save"), reply_markup=build_reply_keyboard(lang))
        await state.clear()
        return

    await state.clear()
    await message.answer(t(lang, "add_success").format(service=data['service_name'], cost=data['cost'], currency=data['currency'], cycle=t(lang, data['billing_cycle']), date=message.text.strip(), id=sub_id), parse_mode="HTML", reply_markup=build_reply_keyboard(lang))

# LIST, TOTAL, DELETE Handlers (Simplified for brevity, same logic as before)
@router.message(Command("list"))
async def cmd_list(message: Message):
    lang = await ensure_language(message) or "en"
    await show_subscriptions(message, message.from_user.id, lang, edit=False)

async def show_subscriptions(message: Message, user_id: int, lang: str, edit: bool):
    subs = await get_user_subscriptions(user_id)
    kb = build_main_inline_keyboard(lang)
    if not subs:
        text = t(lang, "list_empty")
    else:
        text = t(lang, "list_title").format(count=len(subs)) + "\n\n".join([format_subscription_card(s, i+1, lang) for i, s in enumerate(subs)])
    
    if edit: await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else: await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("total"))
async def cmd_total(message: Message):
    lang = await ensure_language(message) or "en"
    await show_total(message, message.from_user.id, lang, edit=False)

async def show_total(message: Message, user_id: int, lang: str, edit: bool):
    subs = await get_user_subscriptions(user_id)
    kb = build_main_inline_keyboard(lang)
    if not subs:
        text = t(lang, "total_empty")
    else:
        # Calc logic similar to original file
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
            text += f"┌─── <b>{curr}</b> ───\n│ {t(lang, 'total_monthly')}: <b>{totals['monthly']:.2f} {curr}</b>\n│ {t(lang, 'total_yearly')}: <b>{totals['yearly']:.2f} {curr}</b>\n└─────────────────\n\n"
    
    if edit: await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else: await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(Command("delete"))
async def cmd_delete(message: Message):
    lang = await ensure_language(message) or "en"
    await show_delete_menu(message, message.from_user.id, lang, edit=False)

async def show_delete_menu(message: Message, user_id: int, lang: str, edit: bool):
    subs = await get_user_subscriptions(user_id)
    if not subs:
        text = t(lang, "delete_empty")
        kb = build_main_inline_keyboard(lang)
    else:
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
    if await delete_subscription(sub_id, callback.from_user.id):
        await callback.message.edit_text(t(lang, "delete_success"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))
    else:
        await callback.message.edit_text(t(lang, "delete_error"), parse_mode="HTML", reply_markup=build_main_inline_keyboard(lang))
    await callback.answer()

@router.message(F.text.in_(["➕ Add Subscription", "➕ إضافة اشتراك"]))
async def reply_btn_add(message: Message, state: FSMContext):
    await cmd_add(message, state)

@router.message(F.text.in_(["📋 My Subscriptions", "📋 اشتراكاتي"]))
async def reply_btn_list(message: Message):
    await cmd_list(message)

@router.message(F.text.in_(["💰 Calculate Total", "💰 حساب التكاليف"]))
async def reply_btn_total(message: Message):
    await cmd_total(message)

@router.message(F.text.in_(["⚙️ Settings / Language", "⚙️ الإعداد

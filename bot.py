"""
Subscription Management & Reminders Bot — v2.0
================================================
Upgraded with:
- Bilingual support (Arabic & English)
- Persistent Reply Keyboard (bottom buttons)
- Bot Menu Commands (/menu)
- Refined FSM flow triggered by both commands and buttons
- Settings page for language switching

Tech: aiogram 3.x, aiosqlite, apscheduler
"""
import json
from aiogram.types import WebAppInfo # أضف هذا السطر

import asyncio
import logging
from datetime import datetime, timedelta

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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Currency options
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
# KEYBOARD BUILDERS
# ============================================================

def build_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Build the persistent reply keyboard (bottom buttons)."""
    buttons = [
        [KeyboardButton(text=t(lang, "btn_add")),
         KeyboardButton(text=t(lang, "btn_list"))],
        [KeyboardButton(text=t(lang, "btn_total")),
         KeyboardButton(text=t(lang, "btn_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def build_language_keyboard() -> InlineKeyboardMarkup:
    """Build language selection keyboard for first-time users."""
    buttons = [
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
         InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_main_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard."""
    buttons = [
        [InlineKeyboardButton(text=t(lang, "btn_add_inline"), callback_data="action_add"),
         InlineKeyboardButton(text=t(lang, "btn_list_inline"), callback_data="action_list")],
        [InlineKeyboardButton(text=t(lang, "btn_total_inline"), callback_data="action_total"),
         InlineKeyboardButton(text=t(lang, "btn_delete_inline"), callback_data="action_delete")],
        [InlineKeyboardButton(text=t(lang, "btn_help_inline"), callback_data="action_help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_currency_keyboard() -> InlineKeyboardMarkup:
    """Build currency selection keyboard."""
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
    """Build billing cycle selection keyboard."""
    buttons = [
        [InlineKeyboardButton(text=t(lang, "cycle_monthly"), callback_data="cycle_monthly"),
         InlineKeyboardButton(text=t(lang, "cycle_yearly"), callback_data="cycle_yearly")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Build cancel button."""
    buttons = [[InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="action_cancel")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_delete_keyboard(subs: list, lang: str) -> InlineKeyboardMarkup:
    """Build delete subscription selection keyboard."""
    buttons = []
    for sub in subs:
        text = f"🗑 {sub['service_name']} — {sub['cost']} {sub['currency']}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"del_{sub['id']}")])
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_confirm_delete_keyboard(sub_id: int, lang: str) -> InlineKeyboardMarkup:
    """Build deletion confirmation keyboard."""
    buttons = [
        [InlineKeyboardButton(text=t(lang, "delete_yes"), callback_data=f"confirm_del_{sub_id}"),
         InlineKeyboardButton(text=t(lang, "delete_no"), callback_data="action_delete")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Build settings/language keyboard with current language marked."""
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
# HELPER: Get user language (with fallback)
# ============================================================
async def get_lang(user_id: int) -> str:
    """Get user language, returns None if not set yet."""
    return await get_user_language(user_id)


def format_subscription_card(sub: dict, index: int, lang: str) -> str:
    """Format a single subscription as a neat card."""
    cycle_text = t(lang, sub['billing_cycle'])
    try:
        payment_date = datetime.strptime(sub['next_payment_date'], "%Y-%m-%d")
        days_left = (payment_date - datetime.now()).days
        if days_left < 0:
            days_text = t(lang, "days_overdue")
        elif days_left == 0:
            days_text = t(lang, "days_today")
        elif days_left == 1:
            days_text = t(lang, "days_tomorrow")
        elif days_left <= 3:
            days_text = t(lang, "days_soon").format(days_left)
        elif days_left <= 7:
            days_text = t(lang, "days_week").format(days_left)
        else:
            days_text = t(lang, "days_later").format(days_left)
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


# ── Middleware-like: Check language before processing ─────────

async def ensure_language(message_or_callback, state: FSMContext = None):
    """
    Check if user has set a language. If not, prompt them.
    Returns the language code or None (if language prompt was sent).
    """
    if isinstance(message_or_callback, Message):
        user_id = message_or_callback.from_user.id
    else:
        user_id = message_or_callback.from_user.id

    await ensure_user_exists(user_id)
    lang = await get_lang(user_id)
    return lang


# ── /start Command ───────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start — check language, show welcome or language picker."""
    await state.clear()
    lang = await ensure_language(message)

    if lang is None:
        # First time user — show language selection
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
        await message.answer(
            "👇",
            reply_markup=build_main_inline_keyboard(lang)
        )


# ── Language Selection Callback ──────────────────────────────

@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_language(callback: CallbackQuery, state: FSMContext):
    """Handle language selection."""
    lang = callback.data.replace("set_lang_", "")
    user_id = callback.from_user.id

    await set_user_language(user_id, lang)
    await state.clear()

    # Acknowledge language change
    await callback.message.edit_text(
        t(lang, "language_set"),
        parse_mode="HTML"
    )

    # Send welcome with reply keyboard
    await callback.message.answer(
        t(lang, "welcome"),
        parse_mode="HTML",
        reply_markup=build_reply_keyboard(lang)
    )
    await callback.message.answer(
        "👇",
        reply_markup=build_main_inline_keyboard(lang)
    )
    await callback.answer()


# ── /help Command ────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await ensure_language(message) or "en"
    await message.answer(
        t(lang, "help"),
        parse_mode="HTML",
        reply_markup=build_main_inline_keyboard(lang)
    )


# ── /cancel Command ─────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = await ensure_language(message) or "en"
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(t(lang, "cancel_none"), reply_markup=build_reply_keyboard(lang))
        return
    await state.clear()
    await message.answer(
        t(lang, "cancel_ok"),
        parse_mode="HTML",
        reply_markup=build_reply_keyboard(lang)
    )


# ── /language Command ────────────────────────────────────────

@router.message(Command("language"))
async def cmd_language(message: Message):
    lang = await ensure_language(message) or "en"
    await message.answer(
        t(lang, "settings_title"),
        parse_mode="HTML",
        reply_markup=build_settings_keyboard(lang)
    )


# ── Inline Callback: Main Menu Actions ──────────────────────

@router.callback_query(F.data == "action_add")
async def cb_add(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    await state.set_state(AddSubscription.waiting_for_service_name)
    await callback.message.edit_text(
        f"{t(lang, 'add_title')}\n\n{t(lang, 'add_step1')}",
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(lang)
    )
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
    await callback.message.edit_text(
        t(lang, "help"),
        parse_mode="HTML",
        reply_markup=build_main_inline_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "action_back")
async def cb_back(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    await state.clear()
    await callback.message.edit_text(
        t(lang, "welcome"),
        parse_mode="HTML",
        reply_markup=build_main_inline_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "action_cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    await state.clear()
    await callback.message.edit_text(
        t(lang, "cancel_ok"),
        parse_mode="HTML",
        reply_markup=build_main_inline_keyboard(lang)
    )
    await callback.answer()


# ============================================================
# ADD SUBSCRIPTION FLOW (FSM)
# ============================================================

# ── /add Command ─────────────────────────────────────────────

@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    lang = await ensure_language(message) or "en"
    await state.set_state(AddSubscription.waiting_for_service_name)
    await message.answer(
        f"{t(lang, 'add_title')}\n\n{t(lang, 'add_step1')}",
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(lang)
    )


# Step 1: Service Name
@router.message(StateFilter(AddSubscription.waiting_for_service_name))
async def fsm_service_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id) or "en"
    service_name = message.text.strip()

    if not service_name or len(service_name) > 100:
        await message.answer(
            t(lang, "add_error_name"),
            reply_markup=build_cancel_keyboard(lang)
        )
        return

    await state.update_data(service_name=service_name)
    await state.set_state(AddSubscription.waiting_for_cost)
    await message.answer(
        t(lang, "add_step2_ok").format(service_name),
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(lang)
    )


# Step 2: Cost
@router.message(StateFilter(AddSubscription.waiting_for_cost))
async def fsm_cost(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id) or "en"

    try:
        cost = float(message.text.strip().replace(",", "."))
        if cost <= 0 or cost > 999999:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(
            t(lang, "add_error_cost"),
            reply_markup=build_cancel_keyboard(lang)
        )
        return

    await state.update_data(cost=cost)
    await state.set_state(AddSubscription.waiting_for_currency)
    await message.answer(
        t(lang, "add_step3_ok").format(cost),
        parse_mode="HTML",
        reply_markup=build_currency_keyboard()
    )


# Step 3: Currency
@router.callback_query(StateFilter(AddSubscription.waiting_for_currency), F.data.startswith("currency_"))
async def fsm_currency(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    currency = callback.data.replace("currency_", "")

    await state.update_data(currency=currency)
    await state.set_state(AddSubscription.waiting_for_billing_cycle)
    await callback.message.edit_text(
        t(lang, "add_step4_ok").format(currency),
        parse_mode="HTML",
        reply_markup=build_billing_cycle_keyboard(lang)
    )
    await callback.answer()


# Step 4: Billing Cycle
@router.callback_query(StateFilter(AddSubscription.waiting_for_billing_cycle), F.data.startswith("cycle_"))
async def fsm_billing_cycle(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id) or "en"
    cycle = callback.data.replace("cycle_", "")
    cycle_text = t(lang, cycle)

    await state.update_data(billing_cycle=cycle)
    await state.set_state(AddSubscription.waiting_for_payment_date)

    suggested_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    await callback.message.edit_text(
        t(lang, "add_step5_ok").format(cycle_text, suggested_date),
        parse_mode="HTML"
    )
    await callback.answer()


# Step 5: Payment Date
@router.message(StateFilter(AddSubscription.waiting_for_payment_date))
async def fsm_payment_date(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id) or "en"
    date_text = message.text.strip()

    try:
        payment_date = datetime.strptime(date_text, "%Y-%m-%d")
        if payment_date.date() < datetime.now().date():
            await message.answer(
                t(lang, "add_error_date_past"),
                reply_markup=build_cancel_keyboard(lang)
            )
            return
    except ValueError:
        await message.answer(
            t(lang, "add_error_date_format"),
            parse_mode="HTML",
            reply_markup=build_cancel_keyboard(lang)
        )
        return

    data = await state.get_data()
    service_name = data['service_name']
    cost = data['cost']
    currency = data['currency']
    billing_cycle = data['billing_cycle']
    cycle_text = t(lang, billing_cycle)

    try:
        sub_id = await add_subscription(
            user_id=message.from_user.id,
            service_name=service_name,
            cost=cost,
            currency=currency,
            billing_cycle=billing_cycle,
            next_payment_date=date_text
        )
    except Exception as e:
        logger.error(f"Failed to add subscription: {e}")
        await message.answer(
            t(lang, "add_error_save"),
            reply_markup=build_reply_keyboard(lang)
        )
        await state.clear()
        return

    await state.clear()

    success_msg = t(lang, "add_success").format(
        service=service_name, cost=cost, currency=currency,
        cycle=cycle_text, date=date_text, id=sub_id
    )
    await message.answer(
        success_msg,
        parse_mode="HTML",
        reply_markup=build_reply_keyboard(lang)
    )


# ============================================================
# LIST SUBSCRIPTIONS
# ============================================================

@router.message(Command("list"))
async def cmd_list(message: Message):
    lang = await ensure_language(message) or "en"
    await show_subscriptions(message, message.from_user.id, lang, edit=False)


async def show_subscriptions(message: Message, user_id: int, lang: str, edit: bool = False):
    subs = await get_user_subscriptions(user_id)

    if not subs:
        text = t(lang, "list_empty")
        kb = build_main_inline_keyboard(lang)
        if edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    header = t(lang, "list_title").format(count=len(subs))
    cards = [format_subscription_card(sub, i + 1, lang) for i, sub in enumerate(subs)]
    text = header + "\n\n".join(cards)
    kb = build_main_inline_keyboard(lang)

    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


# ============================================================
# CALCULATE TOTAL
# ============================================================

@router.message(Command("total"))
async def cmd_total(message: Message):
    lang = await ensure_language(message) or "en"
    await show_total(message, message.from_user.id, lang, edit=False)


async def show_total(message: Message, user_id: int, lang: str, edit: bool = False):
    subs = await get_user_subscriptions(user_id)

    if not subs:
        text = t(lang, "total_empty")
        kb = build_main_inline_keyboard(lang)
        if edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    # Group by currency
    currency_totals = {}
    for sub in subs:
        curr = sub['currency']
        if curr not in currency_totals:
            currency_totals[curr] = {"monthly": 0.0, "yearly": 0.0}
        if sub['billing_cycle'] == 'monthly':
            currency_totals[curr]["monthly"] += sub['cost']
            currency_totals[curr]["yearly"] += sub['cost'] * 12
        elif sub['billing_cycle'] == 'yearly':
            currency_totals[curr]["monthly"] += sub['cost'] / 12
            currency_totals[curr]["yearly"] += sub['cost']

    text = t(lang, "total_title") + "\n"
    text += t(lang, "total_count").format(len(subs)) + "\n"

    for curr, totals in currency_totals.items():
        text += (
            f"┌─── <b>{curr}</b> ───\n"
            f"│ {t(lang, 'total_monthly')}: <b>{totals['monthly']:.2f} {curr}</b>\n"
            f"│ {t(lang, 'total_yearly')}: <b>{totals['yearly']:.2f} {curr}</b>\n"
            f"└─────────────────\n\n"
        )

    # Nearest payment
    nearest = min(subs, key=lambda s: s['next_payment_date'])
    try:
        days_to = (datetime.strptime(nearest['next_payment_date'], "%Y-%m-%d") - datetime.now()).days
        text += t(lang, "total_nearest").format(
            nearest['service_name'], nearest['next_payment_date'], max(0, days_to)
        )
    except ValueError:
        pass

    kb = build_main_inline_keyboard(lang)
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


# ============================================================
# DELETE SUBSCRIPTION
# ============================================================

@router.message(Command("delete"))
async def cmd_delete(message: Message):
    lang = await ensure_language(message) or "en"
    await show_delete_menu(message, message.from_user.id, lang, edit=False)


async def show_delete_menu(message: Message, user_id: int, lang: str, edit: bool = False):
    subs = await get_user_subscriptions(user_id)

    if not subs:
        text = t(lang, "delete_empty")
        kb = build_main_inline_keyboard(lang)
        if edit:
            await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    text = t(lang, "delete_title")
    kb = build_delete_keyboard(subs, lang)

    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


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
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=build_confirm_delete_keyboard(sub_id, lang)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_"))
async def cb_delete_execute(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id) or "en"
    sub_id = int(callback.data.replace("confirm_del_", ""))

    success = await delete_subscription(sub_id, callback.from_user.id)
    if success:
        await callback.message.edit_text(
            t(lang, "delete_success"),
            parse_mode="HTML",
            reply_markup=build_main_inline_keyboard(lang)
        )
    else:
        await callback.message.edit_text(
            t(lang, "delete_error"),
            parse_mode="HTML",
            reply_markup=build_main_inline_keyboard(lang)
        )
    await callback.answer()


# ============================================================
# REPLY KEYBOARD BUTTON HANDLERS (Text-based triggers)
# ============================================================

@router.message(F.text.in_([
    "➕ Add Subscription", "➕ إضافة اشتراك"
]))
async def reply_btn_add(message: Message, state: FSMContext):
    """Trigger add flow from reply keyboard button."""
    lang = await get_lang(message.from_user.id) or "en"
    await state.set_state(AddSubscription.waiting_for_service_name)
    await message.answer(
        f"{t(lang, 'add_title')}\n\n{t(lang, 'add_step1')}",
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(lang)
    )


@router.message(F.text.in_([
    "📋 My Subscriptions", "📋 اشتراكاتي"
]))
async def reply_btn_list(message: Message):
    """Trigger list from reply keyboard button."""
    lang = await get_lang(message.from_user.id) or "en"
    await show_subscriptions(message, message.from_user.id, lang, edit=False)


@router.message(F.text.in_([
    "💰 Calculate Total", "💰 حساب التكاليف"
]))
async def reply_btn_total(message: Message):
    """Trigger total from reply keyboard button."""
    lang = await get_lang(message.from_user.id) or "en"
    await show_total(message, message.from_user.id, lang, edit=False)


@router.message(F.text.in_([
    "⚙️ Settings / Language", "⚙️ الإعدادات / اللغة"
]))
async def reply_btn_settings(message: Message):
    """Trigger settings from reply keyboard button."""
    lang = await get_lang(message.from_user.id) or "en"
    await message.answer(
        t(lang, "settings_title"),
        parse_mode="HTML",
        reply_markup=build_settings_keyboard(lang)
    )


# ============================================================
# AUTOMATED REMINDERS
# ============================================================

async def send_reminders(bot: Bot):
    """Background task: check for upcoming payments and send reminders."""
    logger.info("Running scheduled reminder check...")

    reminder_configs = [
        (1, "reminder_1day", "urgency_1"),
        (3, "reminder_3days", "urgency_3"),
        (7, "reminder_7days", "urgency_7"),
    ]

    for days, time_key, urgency_key in reminder_configs:
        try:
            subs = await get_due_subscriptions(days)
            for sub in subs:
                try:
                    # Get user language for the reminder
                    lang = await get_user_language(sub['user_id']) or "en"
                    time_text = t(lang, time_key)
                    urgency = t(lang, urgency_key)

                    title = t(lang, "reminder_title").format(urgency=urgency)
                    body = t(lang, "reminder_body").format(
                        service=sub['service_name'],
                        cost=sub['cost'],
                        currency=sub['currency'],
                        date=sub['next_payment_date'],
                        time_text=time_text
                    )
                    msg = f"{title}\n\n{body}"

                    await bot.send_message(
                        chat_id=sub['user_id'],
                        text=msg,
                        parse_mode="HTML"
                    )
                    logger.info(f"Reminder sent to {sub['user_id']} for {sub['service_name']} ({days}d)")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {sub['user_id']}: {e}")
        except Exception as e:
            logger.error(f"Error checking {days}-day reminders: {e}")

    # Auto-advance past-due subscriptions
    try:
        past_due = await get_past_due_subscriptions()
        for sub in past_due:
            old_date = datetime.strptime(sub['next_payment_date'], "%Y-%m-%d")
            if sub['billing_cycle'] == 'monthly':
                new_date = old_date + timedelta(days=30)
            else:
                new_date = old_date + timedelta(days=365)
            await update_next_payment_date(sub['id'], new_date.strftime("%Y-%m-%d"))
            logger.info(f"Auto-advanced sub {sub['id']} to {new_date.strftime('%Y-%m-%d')}")
    except Exception as e:
        logger.error(f"Error auto-advancing subscriptions: {e}")

    logger.info("Reminder check completed.")


# ============================================================
# BOT COMMANDS MENU SETUP
# ============================================================

async def set_bot_commands(bot: Bot):
    """Set the bot's command menu (visible when user types / or clicks Menu)."""
    # English commands (default)
    en_commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="add", description="Add a new subscription"),
        BotCommand(command="list", description="View all subscriptions"),
        BotCommand(command="total", description="Calculate total costs"),
        BotCommand(command="delete", description="Delete a subscription"),
        BotCommand(command="language", description="Change language"),
        BotCommand(command="help", description="Usage guide"),
        BotCommand(command="cancel", description="Cancel current operation"),
    ]
    await bot.set_my_commands(en_commands)
    logger.info("Bot commands menu set.")


# ============================================================
# MAIN
# ============================================================

async def main():
    """Main entry point."""
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    # Set bot commands menu
    await set_bot_commands(bot)

    # Setup scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_reminders, 'interval', hours=24,
        args=[bot], id='daily_reminders', replace_existing=True
    )
    scheduler.add_job(
        send_reminders, 'date',
        run_date=datetime.now() + timedelta(seconds=30),
        args=[bot], id='startup_reminders'
    )
    scheduler.start()
    logger.info("Scheduler started.")

    logger.info("Bot v2.0 is starting...")
    print("Bot v2.0 is starting...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

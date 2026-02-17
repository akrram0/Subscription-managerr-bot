"""
Subscription Management Bot — v3.1 (Fixed)
===========================================
"""

import asyncio
import logging
import io
import os
import json
from datetime import datetime, timedelta

# ── Matplotlib (must be before any other plt import) ──────────────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, WebAppInfo, MenuButtonWebApp, BufferedInputFile,
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import (
    init_db, get_user_language, set_user_language, ensure_user_exists,
    add_subscription, get_user_subscriptions, get_subscription_by_id,
    delete_subscription, get_due_subscriptions, get_past_due_subscriptions,
    update_next_payment_date,
)
from locales import t

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# FIX: Read Token from Environment Variables (Railway)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    # Fallback for testing ONLY - Replace with your token if not using Env Vars
    # But strictly better to use Railway Variables
    print("WARNING: BOT_TOKEN env var not set.") 

WEB_APP_URL = os.getenv(
    "WEB_APP_URL",
    "https://glistening-gaufre-57bb50.netlify.app/index.html",
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

CURRENCIES = [
    "USD", "SAR", "EGP", "AED", "KWD",
    "QAR", "BHD", "OMR", "JOD", "EUR", "GBP",
]

PIE_COLORS = [
    "#3390ec", "#e05050", "#7ec87e",
    "#f0a050", "#8b5cf6", "#d4621e",
    "#f43f5e", "#06b6d4", "#84cc16",
]

# ═══════════════════════════════════════════════════════════════════════════════
# STATES
# ═══════════════════════════════════════════════════════════════════════════════

class AddSubscription(StatesGroup):
    waiting_for_service_name  = State()
    waiting_for_cost          = State()
    waiting_for_currency      = State()
    waiting_for_billing_cycle = State()
    waiting_for_payment_date  = State()

# ═══════════════════════════════════════════════════════════════════════════════
# CHART GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_pie_chart(subs: list, lang: str) -> io.BytesIO | None:
    if not subs:
        return None

    labels: list[str] = []
    sizes: list[float] = []

    for sub in subs:
        cost = sub["cost"]
        if sub["billing_cycle"] == "yearly":
            cost /= 12  # normalise to monthly for the chart
        labels.append(sub["service_name"])
        sizes.append(cost)

    try:
        fig, ax = plt.subplots(figsize=(6, 6))
        colors = [PIE_COLORS[i % len(PIE_COLORS)] for i in range(len(labels))]
        ax.pie(
            sizes, labels=labels, autopct="%1.1f%%", startangle=90,
            colors=colors, textprops={"color": "black", "weight": "bold"},
        )
        title = (
            "Monthly Expense Distribution"
            if lang != "ar"
            else "توزيع المصاريف الشهرية (تقريبي)"
        )
        ax.set_title(title, fontsize=14, pad=20)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", transparent=False)
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as exc:
        logger.error("Failed to generate chart: %s", exc)
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════════

def build_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn_add"), web_app=WebAppInfo(url=WEB_APP_URL)),
                KeyboardButton(text=t(lang, "btn_list")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_total")),
                KeyboardButton(text=t(lang, "btn_settings")),
            ],
        ],
        resize_keyboard=True,
    )


def build_currency_keyboard() -> InlineKeyboardMarkup:
    rows, row = [], []
    for currency in CURRENCIES:
        row.append(InlineKeyboardButton(text=currency, callback_data=f"currency_{currency}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_billing_cycle_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "cycle_monthly"), callback_data="cycle_monthly"),
        InlineKeyboardButton(text=t(lang, "cycle_yearly"),  callback_data="cycle_yearly"),
    ]])


def build_cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="action_cancel"),
    ]])


def build_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
        InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_lang_ar"),
    ]])


def build_main_inline_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_add_inline"),    web_app=WebAppInfo(url=WEB_APP_URL)),
            InlineKeyboardButton(text=t(lang, "btn_list_inline"),   callback_data="action_list"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_total_inline"),  callback_data="action_total"),
            InlineKeyboardButton(text=t(lang, "btn_delete_inline"), callback_data="action_delete"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_help_inline"),   callback_data="action_help"),
        ],
    ])


def build_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ar":
        lang_row = [
            InlineKeyboardButton(text="🇬🇧 English",       callback_data="set_lang_en"),
            InlineKeyboardButton(text="🇸🇦 العربية ✓",    callback_data="set_lang_ar"),
        ]
    else:
        lang_row = [
            InlineKeyboardButton(text="🇬🇧 English ✓",    callback_data="set_lang_en"),
            InlineKeyboardButton(text="🇸🇦 العربية",       callback_data="set_lang_ar"),
        ]
    return InlineKeyboardMarkup(inline_keyboard=[
        lang_row,
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")],
    ])


def build_delete_keyboard(subs: list, lang: str) -> InlineKeyboardMarkup:
    rows = []
    for sub in subs:
        text = f"🗑 {sub['service_name']} — {sub['cost']} {sub['currency']}"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"del_{sub['id']}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="action_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_confirm_delete_keyboard(sub_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "delete_yes"), callback_data=f"confirm_del_{sub_id}"),
        InlineKeyboardButton(text=t(lang, "delete_no"),  callback_data="action_delete"),
    ]])

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_lang(user_id: int) -> str:
    return (await get_user_language(user_id)) or "en"


def format_subscription_card(sub: dict, index: int, lang: str) -> str:
    cycle_text = t(lang, sub["billing_cycle"])
    try:
        payment_date = datetime.strptime(sub["next_payment_date"], "%Y-%m-%d")
        days_left = (payment_date.date() - datetime.now().date()).days
        if days_left < 0:
            days_text = t(lang, "days_overdue")
        elif days_left == 0:
            days_text = t(lang, "days_today")
        elif days_left == 1:
            days_text = t(lang, "days_tomorrow")
        elif days_left <= 7:
            days_text = t(lang, "days_week").format(days_left)
        else:
            days_text = t(lang, "days_later").format(days_left)
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

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER & HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

router = Router()

# ── WEB APP DATA ───────────────────────────────────────────────────────────────

@router.message(F.web_app_data)
async def web_app_data_handler(message: Message):
    await ensure_user_exists(message.from_user.id)
    lang = await get_lang(message.from_user.id)
    try:
        data = json.loads(message.web_app_data.data)

        service_name      = str(data["service_name"]).strip()
        cost              = float(data["cost"])
        currency          = str(data["currency"]).upper()
        billing_cycle     = str(data["billing_cycle"]).lower()
        next_payment_date = str(data["next_payment_date"])

        if not service_name or len(service_name) > 50:
            raise ValueError("bad service_name")
        if cost <= 0:
            raise ValueError("cost must be positive")
        if billing_cycle not in ("monthly", "yearly"):
            raise ValueError("bad billing_cycle")
        datetime.strptime(next_payment_date, "%Y-%m-%d")  # validate format

        sub_id = await add_subscription(
            message.from_user.id, service_name, cost,
            currency, billing_cycle, next_payment_date,
        )
        success_msg = t(lang, "add_success").format(
            service=service_name, cost=cost, currency=currency,
            cycle=t(lang, billing_cycle), date=next_payment_date, id=sub_id,
        )
        await message.answer(success_msg, parse_mode="HTML",
                             reply_markup=build_reply_keyboard(lang))
        logger.info("User %d added subscription via WebApp (id=%d).", message.from_user.id, sub_id)
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("WebApp bad data from %d: %s", message.from_user.id, exc)
        await message.answer(t(lang, "add_error_save"), parse_mode="HTML")
    except Exception as exc:
        logger.error("WebApp unexpected error: %s", exc, exc_info=True)
        await message.answer(t(lang, "add_error_save"), parse_mode="HTML")


# ── MANUAL ADD (/add) ──────────────────────────────────────────────────────────

@router.message(Command("add"))
async def cmd_add_manual(message: Message, state: FSMContext):
    await ensure_user_exists(message.from_user.id)
    lang = await get_lang(message.from_user.id)
    await state.set_state(AddSubscription.waiting_for_service_name)
    await message.answer(
        f"{t(lang, 'add_title')}\n\n{t(lang, 'add_step1')}",
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(lang),
    )


@router.message(StateFilter(AddSubscription.waiting_for_service_name))
async def process_service_name(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    text = message.text.strip() if message.text else ""
    if not text or len(text) > 50:
        await message.answer(t(lang, "add_error_name"), parse_mode="HTML")
        return
    await state.update_data(service_name=text)
    await state.set_state(AddSubscription.waiting_for_cost)
    await message.answer(
        t(lang, "add_step2_ok").format(text),
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(lang),
    )


@router.message(StateFilter(AddSubscription.waiting_for_cost))
async def process_cost(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    try:
        cost = float((message.text or "").replace(",", "."))
        if cost <= 0:
            raise ValueError("non-positive")
        await state.update_data(cost=cost)
        await state.set_state(AddSubscription.waiting_for_currency)
        await message.answer(
            t(lang, "add_step3_ok").format(cost),
            parse_mode="HTML",
            reply_markup=build_currency_keyboard(),
        )
    except ValueError:
        await message.answer(t(lang, "add_error_cost"), parse_mode="HTML")


@router.callback_query(
    StateFilter(AddSubscription.waiting_for_currency),
    F.data.startswith("currency_"),
)
async def process_currency(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    curr = callback.data.split("_", 1)[1]
    await state.update_data(currency=curr)
    await state.set_state(AddSubscription.waiting_for_billing_cycle)
    await callback.message.edit_text(
        t(lang, "add_step4_ok").format(curr),
        parse_mode="HTML",
        reply_markup=build_billing_cycle_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(
    StateFilter(AddSubscription.waiting_for_billing_cycle),
    F.data.startswith("cycle_"),
)
async def process_cycle(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    cycle = callback.data.split("_", 1)[1]  # "monthly" or "yearly"
    await state.update_data(billing_cycle=cycle)
    await state.set_state(AddSubscription.waiting_for_payment_date)
    today = datetime.now().strftime("%Y-%m-%d")
    await callback.message.edit_text(
        t(lang, "add_step5_ok").format(t(lang, cycle), today),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(StateFilter(AddSubscription.waiting_for_payment_date))
async def process_date(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    try:
        date_str = (message.text or "").strip()
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        if date_obj.date() < datetime.now().date():
            await message.answer(t(lang, "add_error_date_past"), parse_mode="HTML")
            return

        data = await state.get_data()
        sub_id = await add_subscription(
            message.from_user.id,
            data["service_name"], data["cost"],
            data["currency"], data["billing_cycle"], date_str,
        )
        await state.clear()
        success_msg = t(lang, "add_success").format(
            service=data["service_name"], cost=data["cost"],
            currency=data["currency"], cycle=t(lang, data["billing_cycle"]),
            date=date_str, id=sub_id,
        )
        await message.answer(success_msg, parse_mode="HTML",
                             reply_markup=build_reply_keyboard(lang))
    except ValueError:
        await message.answer(t(lang, "add_error_date_format"), parse_mode="HTML")


# ── /start ─────────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await ensure_user_exists(message.from_user.id)
    lang = await get_user_language(message.from_user.id)
    if not lang:
        await message.answer(
            "🌐 <b>Choose Language / اختر اللغة:</b>",
            parse_mode="HTML",
            reply_markup=build_language_keyboard(),
        )
    else:
        await message.answer(
            t(lang, "welcome"), parse_mode="HTML",
            reply_markup=build_reply_keyboard(lang),
        )


# ── Language selection ─────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"set_lang_en", "set_lang_ar"}))
async def cb_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[2]          # "en" or "ar"
    await ensure_user_exists(callback.from_user.id)
    await set_user_language(callback.from_user.id, lang)
    await state.clear()
    await callback.message.answer(
        t(lang, "welcome"), parse_mode="HTML",
        reply_markup=build_reply_keyboard(lang),
    )
    await callback.answer()


# ── Settings / Language ────────────────────────────────────────────────────────

@router.message(Command("language"))
@router.message(F.text.in_({"⚙️ Settings / Language", "⚙️ الإعدادات / اللغة"}))
async def settings_handler(message: Message):
    lang = await get_lang(message.from_user.id)
    await message.answer(
        t(lang, "settings_title"), parse_mode="HTML",
        reply_markup=build_settings_keyboard(lang),
    )


# ── Help ───────────────────────────────────────────────────────────────────────

@router.message(Command("help"))
@router.callback_query(F.data == "action_help")
async def help_handler(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery):
        lang = await get_lang(event.from_user.id)
        await event.message.edit_text(
            t(lang, "help"), parse_mode="HTML",
            reply_markup=build_main_inline_keyboard(lang),
        )
        await event.answer()
    else:
        lang = await get_lang(event.from_user.id)
        await event.answer(
            t(lang, "help"), parse_mode="HTML",
            reply_markup=build_main_inline_keyboard(lang),
        )


# ── Cancel (FSM) ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "action_cancel")
async def action_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_lang(callback.from_user.id)
    await callback.message.edit_text(
        t(lang, "cancelled"), parse_mode="HTML",
        reply_markup=build_main_inline_keyboard(lang),
    )
    await callback.answer()


# ── Back ───────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "action_back")
async def action_back(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    await callback.message.edit_text(
        t(lang, "welcome"), parse_mode="HTML",
        reply_markup=build_main_inline_keyboard(lang),
    )
    await callback.answer()


# ── List ───────────────────────────────────────────────────────────────────────

@router.message(Command("list"))
@router.callback_query(F.data == "action_list")
@router.message(F.text.in_({"📋 My Subscriptions", "📋 اشتراكاتي"}))
async def list_subs(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery):
        user_id, msg = event.from_user.id, event.message
    else:
        user_id, msg = event.from_user.id, event

    lang = await get_lang(user_id)
    subs = await get_user_subscriptions(user_id)
    kb   = build_main_inline_keyboard(lang)

    if not subs:
        text = t(lang, "list_empty")
    else:
        text = t(lang, "list_title").format(count=len(subs)) + "\n\n"
        for i, sub in enumerate(subs, start=1):
            text += format_subscription_card(sub, i, lang) + "\n"

    if isinstance(event, CallbackQuery):
        await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await msg.answer(text, parse_mode="HTML", reply_markup=kb)


# ── Total ──────────────────────────────────────────────────────────────────────

@router.message(Command("total"))
@router.callback_query(F.data == "action_total")
@router.message(F.text.in_({"💰 Calculate Total", "💰 حساب التكاليف"}))
async def total_subs(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery):
        user_id, msg = event.from_user.id, event.message
    else:
        user_id, msg = event.from_user.id, event

    lang = await get_lang(user_id)
    subs = await get_user_subscriptions(user_id)
    kb   = build_main_inline_keyboard(lang)

    if not subs:
        text = t(lang, "total_empty")
        if isinstance(event, CallbackQuery):
            await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
            await event.answer()
        else:
            await msg.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    monthly_totals: dict[str, float] = {}
    yearly_totals:  dict[str, float] = {}
    for sub in subs:
        curr, cost = sub["currency"], sub["cost"]
        if sub["billing_cycle"] == "monthly":
            monthly_totals[curr] = monthly_totals.get(curr, 0) + cost
        else:
            yearly_totals[curr] = yearly_totals.get(curr, 0) + cost

    text = t(lang, "total_title")
    if monthly_totals:
        text += f"<b>{t(lang, 'total_monthly')}:</b>\n"
        for curr, val in monthly_totals.items():
            text += f"  • {val:.2f} {curr}\n"
    if yearly_totals:
        text += f"\n<b>{t(lang, 'total_yearly')}:</b>\n"
        for curr, val in yearly_totals.items():
            text += f"  • {val:.2f} {curr}\n"

    chart_buf = generate_pie_chart(subs, lang)
    if chart_buf:
        if isinstance(event, CallbackQuery):
            try:
                await msg.delete()
            except Exception:
                pass
        await msg.answer_photo(
            BufferedInputFile(chart_buf.read(), filename="chart.png"),
            caption=text, parse_mode="HTML", reply_markup=kb,
        )
        if isinstance(event, CallbackQuery):
            await event.answer()
    else:
        if isinstance(event, CallbackQuery):
            await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
            await event.answer()
        else:
            await msg.answer(text, parse_mode="HTML", reply_markup=kb)


# ── Delete menu ────────────────────────────────────────────────────────────────

@router.message(Command("delete"))
@router.callback_query(F.data == "action_delete")
async def delete_menu(event: Message | CallbackQuery):
    if isinstance(event, CallbackQuery):
        user_id, msg = event.from_user.id, event.message
    else:
        user_id, msg = event.from_user.id, event

    lang = await get_lang(user_id)
    subs = await get_user_subscriptions(user_id)

    if not subs:
        txt = t(lang, "delete_empty")
        if isinstance(event, CallbackQuery):
            await msg.edit_text(txt, parse_mode="HTML",
                                reply_markup=build_main_inline_keyboard(lang))
            await event.answer()
        else:
            await msg.answer(txt, parse_mode="HTML")
        return

    kb  = build_delete_keyboard(subs, lang)
    txt = t(lang, "delete_title")
    if isinstance(event, CallbackQuery):
        await msg.edit_text(txt, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await msg.answer(txt, parse_mode="HTML", reply_markup=kb)


# ── Delete — confirm step ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("del_"))
async def confirm_del(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    try:
        sub_id = int(callback.data.split("_", 1)[1])
    except ValueError:
        await callback.answer("❌ Invalid request.")
        return

    sub = await get_subscription_by_id(sub_id, callback.from_user.id)
    if sub:
        text = t(lang, "delete_confirm").format(
            name=sub["service_name"],
            cost=sub["cost"],
            currency=sub["currency"],
            cycle=t(lang, sub["billing_cycle"]),
            date=sub["next_payment_date"],
        )
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=build_confirm_delete_keyboard(sub_id, lang),
        )
    else:
        await callback.message.edit_text(
            t(lang, "delete_fail"), parse_mode="HTML",
            reply_markup=build_main_inline_keyboard(lang),
        )
    await callback.answer()


# ── Delete — execute ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("confirm_del_"))
async def execute_del(callback: CallbackQuery):
    lang = await get_lang(callback.from_user.id)
    try:
        sub_id = int(callback.data.split("_", 2)[2])
    except ValueError:
        await callback.answer("❌ Invalid request.")
        return

    sub = await get_subscription_by_id(sub_id, callback.from_user.id)
    deleted = await delete_subscription(sub_id, callback.from_user.id)

    if deleted and sub:
        text = t(lang, "delete_success").format(name=sub["service_name"])
    else:
        text = t(lang, "delete_fail")

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=build_main_inline_keyboard(lang),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER JOBS
# ═══════════════════════════════════════════════════════════════════════════════

async def reminder_job(bot: Bot):
    """Send reminders for subscriptions due within 3 days."""
    try:
        due = await get_due_subscriptions(days_ahead=3)
        for sub in due:
            try:
                payment_date = datetime.strptime(sub["next_payment_date"], "%Y-%m-%d").date()
                days_left = (payment_date - datetime.now().date()).days
                lang = await get_lang(sub["user_id"])
                if days_left == 0:
                    text = t(lang, "reminder_today").format(
                        name=sub["service_name"],
                        cost=sub["cost"],
                        currency=sub["currency"],
                    )
                else:
                    text = t(lang, "reminder_due").format(
                        name=sub["service_name"],
                        days=days_left,
                        cost=sub["cost"],
                        currency=sub["currency"],
                    )
                await bot.send_message(sub["user_id"], text, parse_mode="HTML")
            except Exception as exc:
                logger.warning("Reminder failed for sub %d: %s", sub["id"], exc)
    except Exception as exc:
        logger.error("reminder_job error: %s", exc, exc_info=True)


async def auto_advance_job(bot: Bot):
    """Auto-advance overdue subscriptions to the next billing date."""
    try:
        overdue = await get_past_due_subscriptions()
        for sub in overdue:
            try:
                old_date = datetime.strptime(sub["next_payment_date"], "%Y-%m-%d")
                if sub["billing_cycle"] == "monthly":
                    new_date = old_date + timedelta(days=30)
                else:
                    new_date = old_date.replace(year=old_date.year + 1)
                new_date_str = new_date.strftime("%Y-%m-%d")
                await update_next_payment_date(sub["id"], new_date_str)

                lang = await get_lang(sub["user_id"])
                text = t(lang, "reminder_overdue").format(
                    name=sub["service_name"],
                    date=sub["next_payment_date"],
                    cost=sub["cost"],
                    currency=sub["currency"],
                    new_date=new_date_str,
                )
                await bot.send_message(sub["user_id"], text, parse_mode="HTML")
            except Exception as exc:
                logger.warning("Auto-advance failed for sub %d: %s", sub["id"], exc)
    except Exception as exc:
        logger.error("auto_advance_job error: %s", exc, exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP / MAIN
# ═══════════════════════════════════════════════════════════════════════════════

async def on_startup(bot: Bot):
    await init_db()

    await bot.set_my_commands([
        BotCommand(command="start",    description="Main menu"),
        BotCommand(command="add",      description="Add a subscription"),
        BotCommand(command="list",     description="List subscriptions"),
        BotCommand(command="total",    description="Cost summary"),
        BotCommand(command="delete",   description="Delete a subscription"),
        BotCommand(command="language", description="Change language"),
        BotCommand(command="help",     description="Help"),
    ])

    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Open App",
                web_app=WebAppInfo(url=WEB_APP_URL),
            )
        )
    except Exception as exc:
        logger.warning("Could not set menu button: %s", exc)

    logger.info("Bot started successfully.")


async def main():
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is missing! Set it in Variables.")
        return

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(reminder_job,      "cron", hour=9,  minute=0,  args=[bot])
    scheduler.add_job(auto_advance_job,  "cron", hour=0,  minute=5,  args=[bot])
    scheduler.start()

    await on_startup(bot)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())

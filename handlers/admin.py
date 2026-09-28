"""
MedQuiz AI - Admin Panel & Analytics Handlers
Handles navigation, statistics display, question history pagination, and security decorators.
"""

from functools import wraps
from typing import Callable
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import database
from utils.keyboards import get_admin_main_menu, get_history_pagination_keyboard
from utils.logger import logger


def admin_required(func: Callable):
    """Decorator to ensure only verified admins can invoke handler actions."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not await database.is_admin(user.id):
            if update.callback_query:
                await update.callback_query.answer("⛔ Access Denied. Admin privileges required.", show_alert=True)
            elif update.effective_chat:
                await update.effective_chat.send_message("⛔ You are not authorized to perform this admin action.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


@admin_required
async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles returning to the main admin menu."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    from handlers.start import ADMIN_PANEL_HEADER
    await query.edit_message_text(
        text=ADMIN_PANEL_HEADER,
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )


@admin_required
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays comprehensive bot statistics and AI generation metrics."""
    stats = await database.get_dashboard_stats()

    stats_text = (
        "📊 <b>MEDQUIZ AI - STATISTICS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>Total Questions:</b> {stats.get('total_questions', 0):,}\n"
        f"  ├ 🧠 <b>NEET:</b> {stats.get('neet_questions', 0):,}\n"
        f"  └ 🩺 <b>MBBS:</b> {stats.get('mbbs_questions', 0):,}\n\n"
        f"📅 <b>Today's Posts:</b> {stats.get('today_posts', 0):,}\n"
        f"✅ <b>Successful Broadcasts:</b> {stats.get('successful_posts', 0):,}\n\n"
        f"🤖 <b>AI Generations:</b> {stats.get('ai_generations', 0):,}\n"
        f"⚠️ <b>Failed AI Generations:</b> {stats.get('failed_generations', 0):,}\n\n"
        f"📢 <b>Active Destinations:</b> {stats.get('active_destinations', 0)}\n"
        f"⏰ <b>Active Schedules:</b> {stats.get('active_schedules', 0)}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin:stats")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="admin:back_main")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=stats_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    elif update.effective_chat:
        await update.effective_chat.send_message(
            text=stats_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )


@admin_required
async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Renders paginated list of generated questions."""
    page = 1
    if update.callback_query and update.callback_query.data:
        parts = update.callback_query.data.split("_")
        if len(parts) > 1 and parts[1].isdigit():
            page = int(parts[1])
        await update.callback_query.answer()

    page_size = 3
    questions, total = await database.get_question_history(page=page, page_size=page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)

    if not questions:
        history_text = "📝 <b>Question History:</b>\n\nNo questions generated yet."
    else:
        history_text = f"📝 <b>QUESTION HISTORY (Page {page}/{total_pages})</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        for q in questions:
            status_emoji = "✅" if q["status"] == "published" else ("⏳" if q["status"] == "generated" else "❌")
            dest = q.get("destination_title") or "Manual/Unassigned"
            history_text += (
                f"<b>#{q['id']} [{q['category']} - {q['subject']}]</b>\n"
                f"Status: {status_emoji} {q['status'].capitalize()} | Dest: {dest}\n"
                f"Q: <i>{q['question'][:90]}...</i>\n"
                f"Date: {q['created_at']}\n"
                "─────────────────────\n"
            )

    keyboard = get_history_pagination_keyboard(page, total_pages)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=history_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    elif update.effective_chat:
        await update.effective_chat.send_message(
            text=history_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )


@admin_required
async def subjects_overview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays subjects categorized under NEET and MBBS."""
    from config import NEET_SUBJECTS, MBBS_SUBJECTS

    neet_list = ", ".join(NEET_SUBJECTS.keys())
    mbbs_list = "\n• " + "\n• ".join(MBBS_SUBJECTS.keys())

    custom = await database.get_custom_subjects()
    custom_str = "None yet."
    if custom:
        custom_str = ", ".join([f"{c['name']} ({c['category']})" for c in custom])

    text = (
        "📚 <b>CURRICULUM SUBJECTS</b>\n\n"
        f"🧠 <b>NEET Subjects:</b>\n{neet_list}\n\n"
        f"🩺 <b>MBBS Subjects:</b>\n{mbbs_list}\n\n"
        f"➕ <b>Custom Added Subjects:</b>\n{custom_str}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="admin:back_main")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

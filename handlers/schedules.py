"""
MedQuiz AI - Schedule Management Handlers
Configures auto-posting schedules, posting times, recurring days, pause/resume, and deletions.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
from telegram.constants import ParseMode
import database
from handlers.admin import admin_required
from utils.keyboards import (
    get_schedules_menu, get_category_keyboard, get_subjects_keyboard,
    get_difficulty_keyboard, get_language_keyboard, get_admin_main_menu
)
from utils.logger import logger

(
    SCHED_DEST,
    SCHED_CAT,
    SCHED_SUB,
    SCHED_DIFF,
    SCHED_LANG,
    SCHED_TIME
) = range(6)


@admin_required
async def schedules_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Renders the active automated posting schedules list."""
    schedules = await database.get_schedules()
    text = (
        "⏰ <b>AUTOMATED POSTING SCHEDULES</b>\n\n"
        "Configure automated daily quiz generation and broadcasting.\n"
        "The bot will automatically generate fresh, validated questions and publish them on schedule."
    )

    keyboard = get_schedules_menu(schedules)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


@admin_required
async def start_add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: Select Destination for new schedule."""
    query = update.callback_query
    if query:
        await query.answer()

    destinations = await database.get_destinations(only_enabled=True)
    if not destinations:
        msg = "⚠️ You must connect at least one Channel or Group before creating a schedule."
        if query:
            await query.edit_message_text(msg, reply_markup=get_admin_main_menu())
        else:
            await update.effective_chat.send_message(msg, reply_markup=get_admin_main_menu())
        return ConversationHandler.END

    context.user_data["new_schedule"] = {}

    keyboard = []
    for d in destinations:
        keyboard.append([InlineKeyboardButton(f"📢 {d['title']}", callback_data=f"sc_dest:{d['id']}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="sc_cancel")])

    text = "⏰ <b>ADD SCHEDULE - Step 1/6</b>\n\nSelect the target destination for this schedule:"
    if query:
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

    return SCHED_DEST


async def schedule_destination_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Choose Category."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END

    if query.data == "sc_cancel":
        await query.answer()
        await query.edit_message_text("❌ Schedule setup cancelled.", reply_markup=get_admin_main_menu())
        return ConversationHandler.END

    await query.answer()
    dest_id = int(query.data.split(":")[1])
    context.user_data["new_schedule"]["destination_id"] = dest_id

    await query.edit_message_text(
        text="⏰ <b>ADD SCHEDULE - Step 2/6</b>\n\nSelect Category for this recurring post:",
        reply_markup=get_category_keyboard(prefix="sc_cat"),
        parse_mode=ParseMode.HTML
    )
    return SCHED_CAT


async def schedule_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 3: Choose Subject."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()

    category = query.data.split(":")[1]
    context.user_data["new_schedule"]["category"] = category

    await query.edit_message_text(
        text=f"⏰ <b>ADD SCHEDULE - Step 3/6</b>\n\nChoose Subject ({category}):",
        reply_markup=get_subjects_keyboard(category, prefix="sc_sub", include_random=True),
        parse_mode=ParseMode.HTML
    )
    return SCHED_SUB


async def schedule_subject_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 4: Choose Difficulty."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()

    subject = query.data.split(":")[1]
    context.user_data["new_schedule"]["subject"] = subject

    await query.edit_message_text(
        text="⏰ <b>ADD SCHEDULE - Step 4/6</b>\n\nSelect Difficulty Level:",
        reply_markup=get_difficulty_keyboard(prefix="sc_diff"),
        parse_mode=ParseMode.HTML
    )
    return SCHED_DIFF


async def schedule_difficulty_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 5: Choose Language."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()

    diff = query.data.split(":")[1]
    context.user_data["new_schedule"]["difficulty"] = diff

    await query.edit_message_text(
        text="⏰ <b>ADD SCHEDULE - Step 5/6</b>\n\nSelect Language:",
        reply_markup=get_language_keyboard(prefix="sc_lang"),
        parse_mode=ParseMode.HTML
    )
    return SCHED_LANG


async def schedule_language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 6: Prompt for Posting Time (HH:MM)."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()

    lang = query.data.split(":")[1]
    context.user_data["new_schedule"]["language"] = lang

    text = (
        "⏰ <b>ADD SCHEDULE - Final Step (6/6)</b>\n\n"
        "Please enter the daily posting time in 24-hour format (<b>HH:MM</b>, IST).\n\n"
        "<i>Examples:</i>\n"
        "• <code>09:00</code> (9:00 AM)\n"
        "• <code>13:30</code> (1:30 PM)\n"
        "• <code>18:00</code> (6:00 PM)\n"
        "• <code>21:00</code> (9:00 PM)"
    )
    await query.edit_message_text(text=text, parse_mode=ParseMode.HTML)
    return SCHED_TIME


async def schedule_time_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validates time format and commits schedule to database and APScheduler."""
    raw_time = (update.message.text or "").strip()

    # Simple validation HH:MM
    parts = raw_time.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await update.message.reply_text("⚠️ Invalid time format. Please enter as HH:MM (e.g. 09:00 or 18:30):")
        return SCHED_TIME

    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        await update.message.reply_text("⚠️ Hours must be 0-23 and minutes 0-59. Please re-enter:")
        return SCHED_TIME

    formatted_time = f"{hour:02d}:{minute:02d}"
    sched_data = context.user_data.get("new_schedule", {})

    sched_id = await database.add_schedule(
        destination_id=sched_data["destination_id"],
        category=sched_data["category"],
        subject=sched_data["subject"],
        topic="Random",
        difficulty=sched_data["difficulty"],
        language=sched_data["language"],
        post_time=formatted_time,
        post_days="all"
    )

    if not sched_id:
        await update.message.reply_text("❌ Database error while creating schedule.", reply_markup=get_admin_main_menu())
        return ConversationHandler.END

    # Register into running APScheduler instance
    scheduler_instance = context.bot_data.get("scheduler")
    if scheduler_instance:
        scheduler_instance.register_schedule_job(sched_id, formatted_time, "all")

    dest = await database.get_destination_by_id(sched_data["destination_id"])
    dest_name = dest["title"] if dest else "Selected Channel"

    await update.message.reply_text(
        text=(
            f"✅ <b>Schedule #{sched_id} Created Successfully!</b>\n\n"
            f"• <b>Destination:</b> {dest_name}\n"
            f"• <b>Category:</b> {sched_data['category']}\n"
            f"• <b>Subject:</b> {sched_data['subject']}\n"
            f"• <b>Difficulty:</b> {sched_data['difficulty']}\n"
            f"• <b>Language:</b> {sched_data['language']}\n"
            f"• <b>Time:</b> {formatted_time} IST (Daily)\n\n"
            "The bot will automatically post daily quizzes at this time."
        ),
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


async def schedule_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels schedule creation."""
    if update.effective_chat:
        await update.effective_chat.send_message("❌ Schedule creation cancelled.", reply_markup=get_admin_main_menu())
    return ConversationHandler.END


@admin_required
async def schedule_actions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles toggle pause/resume and deletion of schedules."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    data = query.data
    scheduler_instance = context.bot_data.get("scheduler")

    if data.startswith("sched:toggle:"):
        sched_id = int(data.split(":")[2])
        new_state = await database.toggle_schedule(sched_id)

        if scheduler_instance:
            if new_state:
                scheduler_instance.resume_schedule_job(sched_id)
            else:
                scheduler_instance.pause_schedule_job(sched_id)

        schedules = await database.get_schedules()
        await query.edit_message_text(
            text="🔄 Schedule status updated.\n\n⏰ <b>AUTOMATED POSTING SCHEDULES</b>",
            reply_markup=get_schedules_menu(schedules),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("sched:del:"):
        sched_id = int(data.split(":")[2])
        await database.delete_schedule(sched_id)

        if scheduler_instance:
            scheduler_instance.remove_schedule_job(sched_id)

        schedules = await database.get_schedules()
        await query.edit_message_text(
            text=f"🗑 Schedule #{sched_id} deleted.\n\n⏰ <b>AUTOMATED POSTING SCHEDULES</b>",
            reply_markup=get_schedules_menu(schedules),
            parse_mode=ParseMode.HTML
        )
        return


def get_schedule_conversation_handler() -> ConversationHandler:
    """ConversationHandler for adding schedules."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_schedule, pattern="^sched:add$"),
            CommandHandler("addschedule", start_add_schedule)
        ],
        states={
            SCHED_DEST: [CallbackQueryHandler(schedule_destination_selected, pattern="^sc_dest:")],
            SCHED_CAT: [CallbackQueryHandler(schedule_category_selected, pattern="^sc_cat:")],
            SCHED_SUB: [CallbackQueryHandler(schedule_subject_selected, pattern="^sc_sub:")],
            SCHED_DIFF: [CallbackQueryHandler(schedule_difficulty_selected, pattern="^sc_diff:")],
            SCHED_LANG: [CallbackQueryHandler(schedule_language_selected, pattern="^sc_lang:")],
            SCHED_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_time_received)]
        },
        fallbacks=[
            CommandHandler("cancel", schedule_cancel),
            CallbackQueryHandler(schedule_cancel, pattern="^sc_cancel$")
        ],
        per_chat=True
    )

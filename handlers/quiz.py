"""
MedQuiz AI - Interactive Quiz Generation Wizard
Guides admin through Category -> Subject -> Topic -> Difficulty -> Language -> Preview -> Publish.
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import database
from handlers.admin import admin_required
from utils.keyboards import (
    get_category_keyboard, get_subjects_keyboard, get_topics_keyboard,
    get_difficulty_keyboard, get_language_keyboard, get_quiz_preview_keyboard,
    get_destination_select_keyboard
)
from utils.helpers import format_preview_message
from services.telegram_publisher import TelegramPublisher
from utils.logger import logger


@admin_required
async def start_quiz_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Begins the quiz generation sequence by asking for Category."""
    context.user_data["quiz_wizard"] = {}
    text = "🧠 <b>NEW QUIZ WIZARD - Step 1/5</b>\n\nSelect the target curriculum category:"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=get_category_keyboard("gen_cat"),
            parse_mode=ParseMode.HTML
        )
    elif update.effective_chat:
        await update.effective_chat.send_message(
            text=text,
            reply_markup=get_category_keyboard("gen_cat"),
            parse_mode=ParseMode.HTML
        )


@admin_required
async def quiz_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles category selection and prompts for subject."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    category = query.data.split(":")[1]
    context.user_data["quiz_wizard"]["category"] = category

    text = f"📚 <b>Step 2/5: Select Subject ({category})</b>\n\nChoose a subject to generate questions for:"
    await query.edit_message_text(
        text=text,
        reply_markup=get_subjects_keyboard(category, prefix="gen_sub"),
        parse_mode=ParseMode.HTML
    )


@admin_required
async def quiz_subject_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles subject selection and prompts for topic."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    subject = query.data.split(":")[1]
    if subject == "_back":
        await start_quiz_wizard(update, context)
        return

    category = context.user_data.get("quiz_wizard", {}).get("category", "NEET")
    context.user_data["quiz_wizard"]["subject"] = subject

    text = f"📌 <b>Step 3/5: Select Topic</b>\n\nSubject: <b>{subject}</b>\nChoose a specific topic or Random:"
    await query.edit_message_text(
        text=text,
        reply_markup=get_topics_keyboard(category, subject, prefix="gen_top"),
        parse_mode=ParseMode.HTML
    )


@admin_required
async def quiz_topic_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles topic selection and prompts for difficulty."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    topic = query.data.split(":")[1]
    if topic == "_back":
        category = context.user_data.get("quiz_wizard", {}).get("category", "NEET")
        await query.edit_message_text(
            text=f"📚 <b>Step 2/5: Select Subject ({category})</b>",
            reply_markup=get_subjects_keyboard(category, prefix="gen_sub"),
            parse_mode=ParseMode.HTML
        )
        return

    context.user_data["quiz_wizard"]["topic"] = topic

    text = "🎯 <b>Step 4/5: Select Difficulty Level</b>\n\nChoose question complexity:"
    await query.edit_message_text(
        text=text,
        reply_markup=get_difficulty_keyboard(prefix="gen_diff"),
        parse_mode=ParseMode.HTML
    )


@admin_required
async def quiz_difficulty_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles difficulty selection and prompts for language."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    diff = query.data.split(":")[1]
    if diff == "_back":
        category = context.user_data.get("quiz_wizard", {}).get("category", "NEET")
        subject = context.user_data.get("quiz_wizard", {}).get("subject", "Biology")
        await query.edit_message_text(
            text=f"📌 <b>Step 3/5: Select Topic ({subject})</b>",
            reply_markup=get_topics_keyboard(category, subject, prefix="gen_top"),
            parse_mode=ParseMode.HTML
        )
        return

    context.user_data["quiz_wizard"]["difficulty"] = diff

    text = "🌐 <b>Step 5/5: Select Language</b>\n\nChoose language for question and options:"
    await query.edit_message_text(
        text=text,
        reply_markup=get_language_keyboard(prefix="gen_lang"),
        parse_mode=ParseMode.HTML
    )


@admin_required
async def quiz_language_and_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggers question generation pipeline and presents interactive preview."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    lang = query.data.split(":")[1]
    if lang == "_back":
        await query.edit_message_text(
            text="🎯 <b>Step 4/5: Select Difficulty Level</b>",
            reply_markup=get_difficulty_keyboard(prefix="gen_diff"),
            parse_mode=ParseMode.HTML
        )
        return

    wizard_data = context.user_data.get("quiz_wizard", {})
    wizard_data["language"] = lang

    category = wizard_data.get("category", "NEET")
    subject = wizard_data.get("subject", "Biology")
    topic = wizard_data.get("topic", "Random")
    difficulty = wizard_data.get("difficulty", "Medium")

    await query.edit_message_text(
        text=(
            "⏳ <b>Generating High-Yield Medical MCQ...</b>\n\n"
            f"• Category: {category}\n"
            f"• Subject: {subject}\n"
            f"• Topic: {topic}\n"
            f"• Difficulty: {difficulty}\n"
            f"• Language: {lang}\n\n"
            "<i>Contacting AI provider, auditing medical facts, and checking duplicate database...</i>"
        ),
        parse_mode=ParseMode.HTML
    )

    # Fetch Generator from bot_data
    generator = context.bot_data.get("question_generator")
    if not generator:
        await query.edit_message_text("❌ System error: Question generator service unavailable.")
        return

    success, q_id, q_obj, err_msg = await generator.generate_and_save(
        category=category,
        subject=subject,
        topic=topic,
        difficulty=difficulty,
        language=lang,
        max_attempts=3
    )

    if not success or not q_id or not q_obj:
        await query.edit_message_text(
            text=(
                f"❌ <b>Generation Failed</b>\n\n"
                f"Reason: <i>{err_msg}</i>\n\n"
                "Please check your AI API key, model settings, or try another subject/topic."
            ),
            reply_markup=get_category_keyboard("gen_cat"),
            parse_mode=ParseMode.HTML
        )
        return

    # Store current question id in user_data for quick actions
    context.user_data["current_question_id"] = q_id

    preview_text = format_preview_message(
        category=q_obj.category,
        subject=q_obj.subject,
        topic=q_obj.topic,
        difficulty=q_obj.difficulty,
        language=lang,
        question=q_obj.question,
        options=q_obj.options,
        correct_option=q_obj.correct_option,
        explanation=q_obj.explanation
    )

    await query.edit_message_text(
        text=preview_text,
        reply_markup=get_quiz_preview_keyboard(q_id),
        parse_mode=ParseMode.HTML
    )


@admin_required
async def quiz_preview_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles actions on the preview screen (Publish, Regenerate, Discard)."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    action, q_id_str = query.data.split(":")
    q_id = int(q_id_str)

    if action == "discard":
        await database.update_question_post_status(q_id, status="rejected")
        from handlers.start import ADMIN_PANEL_HEADER
        from utils.keyboards import get_admin_main_menu
        await query.edit_message_text(
            text=f"🗑 Question #{q_id} discarded.\n\n" + ADMIN_PANEL_HEADER,
            reply_markup=get_admin_main_menu(),
            parse_mode=ParseMode.HTML
        )
        return

    if action == "regen":
        wizard_data = context.user_data.get("quiz_wizard", {})
        generator = context.bot_data.get("question_generator")
        if not generator:
            await query.edit_message_text("❌ Question generator unavailable.")
            return

        await query.edit_message_text("🔄 <b>Regenerating question... Please wait.</b>", parse_mode=ParseMode.HTML)
        success, new_qid, q_obj, err = await generator.generate_and_save(
            category=wizard_data.get("category", "NEET"),
            subject=wizard_data.get("subject", "Biology"),
            topic=wizard_data.get("topic", "Random"),
            difficulty=wizard_data.get("difficulty", "Medium"),
            language=wizard_data.get("language", "English")
        )

        if not success or not new_qid or not q_obj:
            await query.edit_message_text(f"❌ Regeneration failed: {err}")
            return

        preview_text = format_preview_message(
            category=q_obj.category,
            subject=q_obj.subject,
            topic=q_obj.topic,
            difficulty=q_obj.difficulty,
            language=wizard_data.get("language", "English"),
            question=q_obj.question,
            options=q_obj.options,
            correct_option=q_obj.correct_option,
            explanation=q_obj.explanation
        )
        await query.edit_message_text(
            text=preview_text,
            reply_markup=get_quiz_preview_keyboard(new_qid),
            parse_mode=ParseMode.HTML
        )
        return

    if action == "publish_sel":
        destinations = await database.get_destinations(only_enabled=True)
        if not destinations:
            await query.edit_message_text(
                text=(
                    "⚠️ <b>No Active Destinations Found!</b>\n\n"
                    "You need to connect at least one Telegram Channel or Group before broadcasting.\n"
                    "Go to <b>Channels</b> in the Admin Panel to add one."
                ),
                reply_markup=get_quiz_preview_keyboard(q_id),
                parse_mode=ParseMode.HTML
            )
            return

        await query.edit_message_text(
            text=f"📢 <b>Select Destination for Quiz #{q_id}</b>\n\nWhere would you like to publish this Quiz Poll?",
            reply_markup=get_destination_select_keyboard(destinations, q_id),
            parse_mode=ParseMode.HTML
        )


@admin_required
async def quiz_broadcast_execution(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executes the broadcast to selected channels/groups."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    # Callback format: send_to:<dest_id_or_all>:<question_id>
    parts = query.data.split(":")
    dest_target = parts[1]
    q_id = int(parts[2])

    # Fetch question data from SQLite
    q_data = await database.get_question_by_id(q_id)
    if not q_data:
        await query.edit_message_text("❌ Question not found.")
        return

    await query.edit_message_text("🚀 <b>Publishing Quiz Poll to Telegram...</b>", parse_mode=ParseMode.HTML)

    destinations_to_post = []
    if dest_target == "all":
        destinations_to_post = await database.get_destinations(only_enabled=True)
    else:
        d = await database.get_destination_by_id(int(dest_target))
        if d:
            destinations_to_post = [d]

    if not destinations_to_post:
        await query.edit_message_text("❌ No target destination found.")
        return

    results = []
    for dest in destinations_to_post:
        ok, msg_id, poll_id, err = await TelegramPublisher.publish_quiz_to_destination(
            bot=context.bot,
            chat_id=dest["chat_id"],
            question_data=q_data,
            destination_id=dest["id"]
        )
        if ok:
            results.append(f"✅ <b>{dest['title']}:</b> Published successfully (Msg #{msg_id})")
        else:
            results.append(f"❌ <b>{dest['title']}:</b> Failed - {err}")

    summary = "\n".join(results)
    from utils.keyboards import get_admin_main_menu
    await query.edit_message_text(
        text=f"📢 <b>Broadcast Results:</b>\n\n{summary}",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )

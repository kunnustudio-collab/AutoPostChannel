"""
MedQuiz AI - Manual Quiz Creation Handler
Allows admin to author and broadcast questions directly without AI assistance.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
from telegram.constants import ParseMode
import database
from handlers.admin import admin_required
from utils.helpers import generate_question_hash, format_preview_message
from utils.keyboards import get_quiz_preview_keyboard, get_admin_main_menu
from utils.logger import logger

(
    MANUAL_CAT,
    MANUAL_QUESTION,
    MANUAL_OPT_A,
    MANUAL_OPT_B,
    MANUAL_OPT_C,
    MANUAL_OPT_D,
    MANUAL_CORRECT,
    MANUAL_EXPLANATION
) = range(8)


@admin_required
async def start_manual_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Begins the manual question creation flow."""
    context.user_data["manual_quiz"] = {}

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧠 NEET", callback_data="manual_cat:NEET"),
            InlineKeyboardButton("🩺 MBBS", callback_data="manual_cat:MBBS")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="manual_cancel")]
    ])

    text = "✍️ <b>MANUAL QUIZ BUILDER</b>\n\nStep 1: Choose the category for your question:"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return MANUAL_CAT


async def manual_category_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores category and prompts for question text."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END

    if query.data == "manual_cancel":
        await query.answer()
        await query.edit_message_text("❌ Manual quiz creation cancelled.", reply_markup=get_admin_main_menu())
        return ConversationHandler.END

    await query.answer()
    category = query.data.split(":")[1]
    context.user_data["manual_quiz"]["category"] = category
    context.user_data["manual_quiz"]["subject"] = "General"

    await query.edit_message_text(
        "✍️ <b>Step 2/7: Enter Question Statement</b>\n\n"
        "Please send the question text (Max 300 characters for Telegram polls):",
        parse_mode=ParseMode.HTML
    )
    return MANUAL_QUESTION


async def manual_question_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores question text and prompts for Option A."""
    text = (update.message.text or "").strip()
    if len(text) < 5 or len(text) > 300:
        await update.message.reply_text("⚠️ Question must be between 5 and 300 characters. Please re-enter:")
        return MANUAL_QUESTION

    context.user_data["manual_quiz"]["question"] = text
    await update.message.reply_text("✍️ <b>Step 3/7: Enter Option A</b> (Max 100 characters):", parse_mode=ParseMode.HTML)
    return MANUAL_OPT_A


async def manual_opt_a_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores Option A and prompts for Option B."""
    text = (update.message.text or "").strip()
    if not text or len(text) > 100:
        await update.message.reply_text("⚠️ Option must be between 1 and 100 characters. Re-enter Option A:")
        return MANUAL_OPT_A

    context.user_data["manual_quiz"]["option_a"] = text
    await update.message.reply_text("✍️ <b>Step 4/7: Enter Option B</b> (Max 100 characters):", parse_mode=ParseMode.HTML)
    return MANUAL_OPT_B


async def manual_opt_b_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores Option B and prompts for Option C."""
    text = (update.message.text or "").strip()
    if not text or len(text) > 100:
        await update.message.reply_text("⚠️ Option must be between 1 and 100 characters. Re-enter Option B:")
        return MANUAL_OPT_B

    context.user_data["manual_quiz"]["option_b"] = text
    await update.message.reply_text("✍️ <b>Step 5/7: Enter Option C</b> (Max 100 characters):", parse_mode=ParseMode.HTML)
    return MANUAL_OPT_C


async def manual_opt_c_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores Option C and prompts for Option D."""
    text = (update.message.text or "").strip()
    if not text or len(text) > 100:
        await update.message.reply_text("⚠️ Option must be between 1 and 100 characters. Re-enter Option C:")
        return MANUAL_OPT_C

    context.user_data["manual_quiz"]["option_c"] = text
    await update.message.reply_text("✍️ <b>Step 6/7: Enter Option D</b> (Max 100 characters):", parse_mode=ParseMode.HTML)
    return MANUAL_OPT_D


async def manual_opt_d_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores Option D and prompts for Correct Answer."""
    text = (update.message.text or "").strip()
    if not text or len(text) > 100:
        await update.message.reply_text("⚠️ Option must be between 1 and 100 characters. Re-enter Option D:")
        return MANUAL_OPT_D

    context.user_data["manual_quiz"]["option_d"] = text

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("A", callback_data="manual_ans:0"),
            InlineKeyboardButton("B", callback_data="manual_ans:1"),
            InlineKeyboardButton("C", callback_data="manual_ans:2"),
            InlineKeyboardButton("D", callback_data="manual_ans:3")
        ]
    ])

    await update.message.reply_text(
        "🎯 <b>Step 7/8: Select the Correct Answer:</b>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    return MANUAL_CORRECT


async def manual_correct_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores correct answer and prompts for Explanation."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END

    await query.answer()
    correct_idx = int(query.data.split(":")[1])
    context.user_data["manual_quiz"]["correct_option"] = correct_idx

    letters = ["A", "B", "C", "D"]
    await query.edit_message_text(
        f"✅ Correct Option selected: <b>Option {letters[correct_idx]}</b>\n\n"
        "📖 <b>Final Step: Enter Educational Explanation</b>\n"
        "Send the explanation for the answer (or send 'skip' to use brief text):",
        parse_mode=ParseMode.HTML
    )
    return MANUAL_EXPLANATION


async def manual_explanation_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the completed manual question to database and shows preview."""
    expl_text = (update.message.text or "").strip()
    if expl_text.lower() == "skip":
        expl_text = "Standard textbook clinical explanation."

    data = context.user_data.get("manual_quiz", {})
    options = [
        data.get("option_a", "Option A"),
        data.get("option_b", "Option B"),
        data.get("option_c", "Option C"),
        data.get("option_d", "Option D")
    ]
    correct_opt = data.get("correct_option", 0)
    category = data.get("category", "NEET")
    question_text = data.get("question", "")

    # Calculate Hash
    q_hash = generate_question_hash(question_text, options)

    # Save to SQLite
    q_id = await database.save_question(
        category=category,
        subject="General",
        topic="Manual Quiz",
        difficulty="Medium",
        language="English",
        question=question_text,
        options=options,
        correct_option=correct_opt,
        explanation=expl_text,
        question_hash=q_hash,
        status="generated"
    )

    if not q_id:
        await update.message.reply_text(
            "⚠️ A question with this exact wording already exists in the database.",
            reply_markup=get_admin_main_menu()
        )
        return ConversationHandler.END

    preview = format_preview_message(
        category=category,
        subject="General",
        topic="Manual Entry",
        difficulty="Medium",
        language="English",
        question=question_text,
        options=options,
        correct_option=correct_opt,
        explanation=expl_text
    )

    await update.message.reply_text(
        text=f"✅ <b>Question #{q_id} Created Successfully!</b>\n\n{preview}",
        reply_markup=get_quiz_preview_keyboard(q_id),
        parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


async def manual_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the manual quiz flow."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Cancelled.", reply_markup=get_admin_main_menu())
    elif update.effective_chat:
        await update.effective_chat.send_message("❌ Cancelled.", reply_markup=get_admin_main_menu())
    return ConversationHandler.END


def get_manual_quiz_conversation_handler() -> ConversationHandler:
    """Builds the ConversationHandler for manual quiz drafting."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_manual_quiz, pattern="^admin:manual_quiz$"),
            CommandHandler("manual", start_manual_quiz)
        ],
        states={
            MANUAL_CAT: [CallbackQueryHandler(manual_category_received, pattern="^manual_cat:")],
            MANUAL_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_question_received)],
            MANUAL_OPT_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_opt_a_received)],
            MANUAL_OPT_B: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_opt_b_received)],
            MANUAL_OPT_C: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_opt_c_received)],
            MANUAL_OPT_D: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_opt_d_received)],
            MANUAL_CORRECT: [CallbackQueryHandler(manual_correct_received, pattern="^manual_ans:")],
            MANUAL_EXPLANATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_explanation_received)]
        },
        fallbacks=[
            CommandHandler("cancel", manual_cancel),
            CallbackQueryHandler(manual_cancel, pattern="^manual_cancel$")
        ],
        per_chat=True
    )

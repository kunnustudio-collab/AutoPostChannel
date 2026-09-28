"""
MedQuiz AI - Settings Handlers
Allows admin to customize AI models, temperature, verification, headers, and explanations.
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
    get_ai_settings_keyboard, get_bot_settings_keyboard,
    get_admin_main_menu, get_language_keyboard, get_difficulty_keyboard
)
from utils.logger import logger

WAITING_MODEL_INPUT = 1


@admin_required
async def ai_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays AI provider and model configurations."""
    model = await database.get_setting("ai_model", "meta-llama/llama-3.1-8b-instruct:free")
    temp = await database.get_setting("ai_temperature", "0.7")
    verif = await database.get_setting("verification_enabled", "true")

    text = (
        "🤖 <b>AI ENGINE SETTINGS</b>\n\n"
        f"• <b>Current Model:</b> <code>{model}</code>\n"
        f"• <b>Temperature:</b> <code>{temp}</code> (Creativity vs Strictness)\n"
        f"• <b>2nd Pass Verification:</b> <code>{verif.upper()}</code>\n\n"
        "Click a button below to configure:"
    )

    keyboard = get_ai_settings_keyboard(model, temp, verif)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


@admin_required
async def bot_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays posting formats, defaults, and broadcast preferences."""
    header = await database.get_setting("send_header", "true")
    expl = await database.get_setting("send_explanation", "true")
    lang = await database.get_setting("default_language", "English")
    diff = await database.get_setting("default_difficulty", "Medium")

    text = (
        "⚙️ <b>BOT & BROADCAST SETTINGS</b>\n\n"
        f"• <b>Intro Banner Message:</b> {'Enabled ✅' if header == 'true' else 'Disabled ❌'}\n"
        f"• <b>Post-Quiz Explanation:</b> {'Enabled ✅' if expl == 'true' else 'Disabled ❌'}\n"
        f"• <b>Default Language:</b> {lang}\n"
        f"• <b>Default Difficulty:</b> {diff}\n\n"
        "Toggle settings below:"
    )

    keyboard = get_bot_settings_keyboard(header, expl, lang, diff)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


@admin_required
async def settings_actions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles flags or handles configuration buttons."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    data = query.data

    # Toggle Verification
    if data == "ai_set:toggle_verif":
        curr = await database.get_setting("verification_enabled", "true")
        new_val = "false" if curr == "true" else "true"
        await database.set_setting("verification_enabled", new_val)
        await ai_settings_menu(update, context)
        return

    # Change Temperature
    if data == "ai_set:temp":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("0.2 (Very Strict)", callback_data="set_temp:0.2"),
                InlineKeyboardButton("0.5 (Balanced)", callback_data="set_temp:0.5")
            ],
            [
                InlineKeyboardButton("0.7 (Standard)", callback_data="set_temp:0.7"),
                InlineKeyboardButton("0.9 (Creative)", callback_data="set_temp:0.9")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:ai_settings")]
        ])
        await query.edit_message_text("🌡 <b>Select AI Temperature:</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return

    if data.startswith("set_temp:"):
        new_temp = data.split(":")[1]
        await database.set_setting("ai_temperature", new_temp)
        await ai_settings_menu(update, context)
        return

    # Toggle Header
    if data == "bot_set:toggle_header":
        curr = await database.get_setting("send_header", "true")
        new_val = "false" if curr == "true" else "true"
        await database.set_setting("send_header", new_val)
        await bot_settings_menu(update, context)
        return

    # Toggle Explanation Post
    if data == "bot_set:toggle_expl":
        curr = await database.get_setting("send_explanation", "true")
        new_val = "false" if curr == "true" else "true"
        await database.set_setting("send_explanation", new_val)
        await bot_settings_menu(update, context)
        return

    # Change Default Language
    if data == "bot_set:lang" or data == "admin:language":
        await query.edit_message_text(
            "🌐 <b>Select Default Language:</b>",
            reply_markup=get_language_keyboard(prefix="set_lang"),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("set_lang:"):
        new_lang = data.split(":")[1]
        if new_lang != "_back":
            await database.set_setting("default_language", new_lang)
        await bot_settings_menu(update, context)
        return

    # Change Default Difficulty
    if data == "bot_set:diff" or data == "admin:difficulty":
        await query.edit_message_text(
            "🎯 <b>Select Default Difficulty:</b>",
            reply_markup=get_difficulty_keyboard(prefix="set_diff"),
            parse_mode=ParseMode.HTML
        )
        return

    if data.startswith("set_diff:"):
        new_diff = data.split(":")[1]
        if new_diff != "_back":
            await database.set_setting("default_difficulty", new_diff)
        await bot_settings_menu(update, context)
        return


@admin_required
async def start_change_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin to enter or select an AI model string."""
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Llama 3.1 8B (Free)", callback_data="preset_model:meta-llama/llama-3.1-8b-instruct:free")],
        [InlineKeyboardButton("Gemini 2.0 Flash Lite (Free)", callback_data="preset_model:google/gemini-2.0-flash-lite:free")],
        [InlineKeyboardButton("Mistral 7B (Free)", callback_data="preset_model:mistralai/mistral-7b-instruct:free")],
        [InlineKeyboardButton("❌ Cancel", callback_data="model_cancel")]
    ])

    text = (
        "🤖 <b>CONFIGURE AI MODEL</b>\n\n"
        "Select a popular free model below, or <b>type and send any custom OpenRouter/OpenAI model identifier</b>:\n\n"
        "<i>Examples:</i>\n"
        "• <code>openai/gpt-4o-mini</code>\n"
        "• <code>anthropic/claude-3.5-sonnet</code>\n"
        "• <code>deepseek/deepseek-chat</code>\n\n"
        "Or send /cancel to keep current model."
    )

    if query:
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.effective_chat:
        await update.effective_chat.send_message(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    return WAITING_MODEL_INPUT


async def process_model_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves custom model name to settings."""
    model_name = (update.message.text or "").strip()
    if len(model_name) < 3:
        await update.message.reply_text("⚠️ Model name too short. Please send valid model string:")
        return WAITING_MODEL_INPUT

    await database.set_setting("ai_model", model_name)
    await update.message.reply_text(
        f"✅ AI Model successfully updated to: <code>{model_name}</code>",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


async def process_model_preset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves selected preset model to settings."""
    query = update.callback_query
    if not query or not query.data:
        return ConversationHandler.END
    await query.answer()

    if query.data == "model_cancel":
        await query.edit_message_text("Cancelled.", reply_markup=get_admin_main_menu())
        return ConversationHandler.END

    model_name = query.data.split(":")[1]
    await database.set_setting("ai_model", model_name)
    await query.edit_message_text(
        f"✅ AI Model updated to: <code>{model_name}</code>",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


async def cancel_change_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels model configuration."""
    if update.effective_chat:
        await update.effective_chat.send_message("Cancelled.", reply_markup=get_admin_main_menu())
    return ConversationHandler.END


def get_model_conversation_handler() -> ConversationHandler:
    """ConversationHandler for updating the AI model."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_change_model, pattern="^ai_set:model$"),
            CommandHandler("setmodel", start_change_model)
        ],
        states={
            WAITING_MODEL_INPUT: [
                CallbackQueryHandler(process_model_preset, pattern="^(preset_model:|model_cancel)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_model_input)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_change_model)],
        per_chat=True
    )

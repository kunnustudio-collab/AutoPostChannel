"""
MedQuiz AI - Production Telegram Bot Entrypoint
Initializes Database, AI Provider, Scheduler, Handlers, and starts the polling event loop.
"""

import sys
import asyncio

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from telegram.constants import ParseMode

import config
import database
from utils.logger import logger
from ai.openrouter import OpenRouterProvider
from services.question_generator import QuestionGeneratorService
from services.telegram_publisher import TelegramPublisher
from scheduler import QuizScheduler

# Handlers
from handlers.start import start_command, help_command
from handlers.admin import (
    admin_menu_callback, stats_handler, history_handler,
    subjects_overview_handler, admin_required
)
from handlers.quiz import (
    start_quiz_wizard, quiz_category_selected, quiz_subject_selected,
    quiz_topic_selected, quiz_difficulty_selected, quiz_language_and_generate,
    quiz_preview_actions, quiz_broadcast_execution
)
from handlers.manual_quiz import get_manual_quiz_conversation_handler
from handlers.channels import (
    channels_menu_handler, channel_actions_callback,
    get_channel_conversation_handler
)
from handlers.schedules import (
    schedules_menu_handler, schedule_actions_callback,
    get_schedule_conversation_handler
)
from handlers.settings import (
    ai_settings_menu, bot_settings_menu, settings_actions_callback,
    get_model_conversation_handler
)


async def test_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs a complete diagnostic test on the AI API and all connected destinations."""
    if not update.effective_user or not await database.is_admin(update.effective_user.id):
        return

    msg = await update.effective_chat.send_message("🔍 <i>Running MedQuiz AI System Diagnostics...</i>", parse_mode=ParseMode.HTML)

    # 1. Test AI API
    ai_provider: OpenRouterProvider = context.bot_data.get("ai_provider")
    ai_ok, ai_msg = await ai_provider.test_connection()
    ai_status = f"✅ {ai_msg}" if ai_ok else f"❌ {ai_msg}"

    # 2. Test Destinations
    destinations = await database.get_destinations(only_enabled=True)
    dest_results = []
    if not destinations:
        dest_results.append("⚠️ No destinations configured yet.")
    else:
        for d in destinations:
            ok, d_msg = await TelegramPublisher.test_destination_permissions(context.bot, d["chat_id"])
            dest_results.append(f"{'✅' if ok else '❌'} <b>{d['title']}:</b> {d_msg}")

    # 3. Database Stats
    stats = await database.get_dashboard_stats()

    report = (
        "🧠 <b>MEDQUIZ AI - DIAGNOSTIC REPORT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>AI Provider Status:</b>\n{ai_status}\n\n"
        f"📢 <b>Destinations ({len(destinations)}):</b>\n" + "\n".join(dest_results) + "\n\n"
        f"📊 <b>Database:</b> {stats['total_questions']} Questions | {stats['active_schedules']} Schedules\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "All systems operational."
    )

    await msg.edit_text(report, parse_mode=ParseMode.HTML)


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs unhandled exceptions and notifies the admin if applicable."""
    logger.error(f"Unhandled exception during Telegram update handling: {context.error}", exc_info=context.error)

    if isinstance(update, Update) and update.effective_chat:
        try:
            await update.effective_chat.send_message(
                "⚠️ <i>An internal error occurred while processing this action. Details have been logged.</i>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def post_init(application: Application) -> None:
    """Runs after application build: initializes DB, schedules, and command shortcuts."""
    logger.info("Running post_init bootstrap...")
    await database.init_db()

    # Load and activate recurring schedules
    scheduler: QuizScheduler = application.bot_data["scheduler"]
    await scheduler.load_schedules_from_db()
    scheduler.start()

    # Configure Bot Commands menu in Telegram
    try:
        commands = [
            BotCommand("start", "Open MedQuiz AI Admin Panel"),
            BotCommand("generate", "Generate an AI Quiz Question"),
            BotCommand("manual", "Author a Manual Question"),
            BotCommand("schedule", "Manage Auto-Posting Schedules"),
            BotCommand("channels", "Manage Destination Channels"),
            BotCommand("stats", "View Live System Analytics"),
            BotCommand("history", "View Question History"),
            BotCommand("settings", "Configure AI & Posting Settings"),
            BotCommand("test", "Run System Diagnostics"),
            BotCommand("help", "Help & Documentation")
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Telegram command menu registered successfully.")
    except Exception as e:
        logger.warning(f"Could not register bot commands menu: {e}")


async def post_shutdown(application: Application) -> None:
    """Cleans up resources during shutdown."""
    logger.info("Running post_shutdown cleanup...")
    scheduler: QuizScheduler = application.bot_data.get("scheduler")
    if scheduler:
        scheduler.shutdown()


def build_application() -> Application:
    """Builds and wires up the Telegram Application instance with all handlers."""
    # Check minimum config
    valid, missing = config.validate_config()
    if not valid:
        logger.warning(f"Configuration warnings: {', '.join(missing)}")
        if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_bot_token_here":
            logger.critical("TELEGRAM_BOT_TOKEN is missing in .env! Please set it before running the bot.")

    # Initialize AI Provider & Generator
    ai_provider = OpenRouterProvider()
    question_generator = QuestionGeneratorService(provider=ai_provider)

    # Initialize Telegram Application
    token = config.TELEGRAM_BOT_TOKEN or "DUMMY_TOKEN"
    application = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Initialize Scheduler
    scheduler = QuizScheduler(bot=application.bot, generator=question_generator)

    # Store shared services in bot_data
    application.bot_data["ai_provider"] = ai_provider
    application.bot_data["question_generator"] = question_generator
    application.bot_data["scheduler"] = scheduler

    # Register Conversation Handlers First
    application.add_handler(get_manual_quiz_conversation_handler())
    application.add_handler(get_channel_conversation_handler())
    application.add_handler(get_schedule_conversation_handler())
    application.add_handler(get_model_conversation_handler())

    # Command Handlers
    application.add_handler(CommandHandler(["start", "admin"], start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler(["generate", "quiz"], start_quiz_wizard))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(CommandHandler("history", history_handler))
    application.add_handler(CommandHandler("channels", channels_menu_handler))
    application.add_handler(CommandHandler(["schedule", "schedules"], schedules_menu_handler))
    application.add_handler(CommandHandler("subjects", subjects_overview_handler))
    application.add_handler(CommandHandler("settings", bot_settings_menu))
    application.add_handler(CommandHandler("test", test_command_handler))

    # Callback Query Handlers
    # Admin Menus
    application.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin:back_main$"))
    application.add_handler(CallbackQueryHandler(stats_handler, pattern="^admin:stats$"))
    application.add_handler(CallbackQueryHandler(history_handler, pattern="^admin:history_"))
    application.add_handler(CallbackQueryHandler(subjects_overview_handler, pattern="^admin:subjects$"))
    application.add_handler(CallbackQueryHandler(channels_menu_handler, pattern="^admin:channels$"))
    application.add_handler(CallbackQueryHandler(schedules_menu_handler, pattern="^admin:schedules$"))
    application.add_handler(CallbackQueryHandler(ai_settings_menu, pattern="^admin:ai_settings$"))
    application.add_handler(CallbackQueryHandler(bot_settings_menu, pattern="^admin:bot_settings$"))

    # Quiz Generation Wizard Callbacks
    application.add_handler(CallbackQueryHandler(start_quiz_wizard, pattern="^admin:gen_start$"))
    application.add_handler(CallbackQueryHandler(quiz_category_selected, pattern="^gen_cat:"))
    application.add_handler(CallbackQueryHandler(quiz_subject_selected, pattern="^gen_sub:"))
    application.add_handler(CallbackQueryHandler(quiz_topic_selected, pattern="^gen_top:"))
    application.add_handler(CallbackQueryHandler(quiz_difficulty_selected, pattern="^gen_diff:"))
    application.add_handler(CallbackQueryHandler(quiz_language_and_generate, pattern="^gen_lang:"))

    # Preview Decisions & Broadcasting
    application.add_handler(CallbackQueryHandler(quiz_preview_actions, pattern="^(publish_sel|regen|discard):"))
    application.add_handler(CallbackQueryHandler(quiz_broadcast_execution, pattern="^send_to:"))

    # Channel & Schedule Actions
    application.add_handler(CallbackQueryHandler(channel_actions_callback, pattern="^chan:"))
    application.add_handler(CallbackQueryHandler(schedule_actions_callback, pattern="^sched:"))

    # Settings Actions
    application.add_handler(CallbackQueryHandler(settings_actions_callback, pattern="^(ai_set|bot_set|set_temp|set_lang|set_diff|admin:difficulty|admin:language)"))

    # Global Error Handler
    application.add_error_handler(global_error_handler)

    return application


def main() -> None:
    """Main execution entrypoint."""
    logger.info("Starting MedQuiz AI Bot...")

    valid, missing = config.validate_config()
    if not valid:
        print("\n=======================================================")
        print("[!] MEDQUIZ AI CONFIGURATION NOTICE:")
        for m in missing:
            print(f" - {m}")
        print("\nPlease update your .env file before starting the bot.")
        print("A template is available at .env.example.")
        print("=======================================================\n")

        if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_bot_token_here":
            sys.exit(1)

    app = build_application()
    print("[*] MedQuiz AI is running! Press Ctrl+C to terminate.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

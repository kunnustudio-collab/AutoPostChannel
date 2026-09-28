"""
MedQuiz AI - Asynchronous Posting Scheduler
Coordinates recurring quiz generation and automated publishing using APScheduler.
"""

from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
import database
from services.question_generator import QuestionGeneratorService
from services.telegram_publisher import TelegramPublisher
from utils.logger import logger


class QuizScheduler:
    """Manages scheduled background jobs for automated quiz posting."""

    def __init__(self, bot: Bot, generator: QuestionGeneratorService):
        self.bot = bot
        self.generator = generator
        self.scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    def start(self) -> None:
        """Starts the background scheduler thread loop."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Quiz scheduler engine started.")

    def shutdown(self) -> None:
        """Gracefully halts the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Quiz scheduler engine stopped.")

    def _parse_trigger(self, post_time: str, post_days: str) -> CronTrigger:
        """Parses 'HH:MM' and post_days into an APScheduler CronTrigger."""
        try:
            parts = post_time.strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            hour, minute = 9, 0

        day_of_week = "*"
        if post_days and post_days.lower() != "all":
            day_of_week = post_days.lower()

        return CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week, timezone="Asia/Kolkata")

    def register_schedule_job(self, schedule_id: int, post_time: str, post_days: str) -> None:
        """Schedules a new recurring job or replaces an existing one."""
        job_id = f"quiz_sched_{schedule_id}"
        trigger = self._parse_trigger(post_time, post_days)

        self.scheduler.add_job(
            func=self.execute_scheduled_job,
            trigger=trigger,
            id=job_id,
            args=[schedule_id],
            replace_existing=True,
            misfire_grace_time=300
        )
        logger.info(f"Registered schedule job #{job_id} at {post_time} (Days: {post_days})")

    def pause_schedule_job(self, schedule_id: int) -> None:
        """Pauses a schedule job."""
        job_id = f"quiz_sched_{schedule_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused scheduler job {job_id}")

    def resume_schedule_job(self, schedule_id: int) -> None:
        """Resumes a paused schedule job."""
        job_id = f"quiz_sched_{schedule_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed scheduler job {job_id}")

    def remove_schedule_job(self, schedule_id: int) -> None:
        """Removes a schedule job permanently from the scheduler."""
        job_id = f"quiz_sched_{schedule_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scheduler job {job_id}")

    async def load_schedules_from_db(self) -> None:
        """Loads and syncs all active schedules from SQLite."""
        schedules = await database.get_schedules(only_enabled=False)
        for s in schedules:
            if s["enabled"]:
                self.register_schedule_job(
                    schedule_id=s["id"],
                    post_time=s["post_time"],
                    post_days=s.get("post_days", "all")
                )
            else:
                self.register_schedule_job(
                    schedule_id=s["id"],
                    post_time=s["post_time"],
                    post_days=s.get("post_days", "all")
                )
                self.pause_schedule_job(s["id"])
        logger.info(f"Loaded {len(schedules)} schedules into background scheduler.")

    async def execute_scheduled_job(self, schedule_id: int) -> None:
        """Core execution logic triggered when a schedule alarm fires."""
        logger.info(f"Executing scheduled quiz job for schedule #{schedule_id}...")

        schedule = await database.get_schedule_by_id(schedule_id)
        if not schedule:
            logger.warning(f"Schedule #{schedule_id} not found in database. Removing job.")
            self.remove_schedule_job(schedule_id)
            return

        if not schedule["enabled"]:
            logger.info(f"Schedule #{schedule_id} is disabled. Skipping.")
            return

        destination = await database.get_destination_by_id(schedule["destination_id"])
        if not destination or not destination["enabled"]:
            logger.warning(f"Destination #{schedule['destination_id']} disabled or missing. Skipping schedule #{schedule_id}.")
            return

        category = schedule["category"]
        subject = schedule["subject"]
        topic = schedule.get("topic", "Random")
        difficulty = schedule.get("difficulty", "Medium")
        language = schedule.get("language", "English")
        chat_id = destination["chat_id"]

        try:
            # 1. Generate & Validate Question
            success, q_id, q_obj, err = await self.generator.generate_and_save(
                category=category,
                subject=subject,
                topic=topic,
                difficulty=difficulty,
                language=language,
                destination_id=destination["id"],
                max_attempts=3
            )

            if not success or not q_id or not q_obj:
                logger.error(f"Scheduled generation failed for #{schedule_id}: {err}")
                return

            # 2. Publish to Telegram Destination
            question_data = {
                "id": q_id,
                "category": q_obj.category,
                "subject": q_obj.subject,
                "topic": q_obj.topic,
                "difficulty": q_obj.difficulty,
                "question": q_obj.question,
                "option_a": q_obj.options[0],
                "option_b": q_obj.options[1],
                "option_c": q_obj.options[2],
                "option_d": q_obj.options[3],
                "correct_option": q_obj.correct_option,
                "explanation": q_obj.explanation
            }

            pub_ok, msg_id, poll_id, pub_err = await TelegramPublisher.publish_quiz_to_destination(
                bot=self.bot,
                chat_id=chat_id,
                question_data=question_data,
                destination_id=destination["id"]
            )

            if pub_ok:
                await database.update_schedule_last_run(schedule_id)
                logger.info(f"Scheduled quiz successfully posted to {destination['title']} (Msg #{msg_id})")
            else:
                logger.error(f"Scheduled quiz publication failed for #{schedule_id}: {pub_err}")

        except Exception as e:
            logger.error(f"Fatal error during scheduled job #{schedule_id} execution: {e}")

"""
MedQuiz AI - Telegram Quiz Poll Publisher
Handles broadcasting native Telegram quiz polls, headers, explanations, and error backoff.
"""

import asyncio
from typing import Tuple, Optional, Any
from telegram import Bot
from telegram.constants import PollType, ParseMode
from telegram.error import TelegramError, RetryAfter, TimedOut, Forbidden
import database
from utils.helpers import (
    format_header_message, format_explanation_message,
    truncate_text, OPTION_LETTERS
)
from utils.logger import logger


class TelegramPublisher:
    """Publishes validated quizzes to Telegram channels and groups."""

    @staticmethod
    async def test_destination_permissions(bot: Bot, chat_id: str) -> Tuple[bool, str]:
        """
        Verifies that the bot is an admin with rights to post messages and polls in the destination.
        """
        try:
            # First check if bot can access the chat
            chat = await bot.get_chat(chat_id=chat_id)

            # Send a silent test verification message
            test_msg = await bot.send_message(
                chat_id=chat_id,
                text="🧪 <i>MedQuiz AI permission test: Success! The bot can broadcast here.</i>",
                parse_mode=ParseMode.HTML,
                disable_notification=True
            )

            # Clean up the test message after 2 seconds
            await asyncio.sleep(2.0)
            try:
                await bot.delete_message(chat_id=chat_id, message_id=test_msg.message_id)
            except Exception:
                pass  # Ignore delete permission absence

            title = chat.title or chat.username or str(chat_id)
            chat_type = chat.type or "channel"
            return True, f"Verified access to {chat_type}: '{title}'"

        except Forbidden:
            return False, "Bot does not have permission to post in this chat. Make sure the bot is added as an Administrator with 'Post Messages' rights."
        except Exception as e:
            return False, f"Could not access chat ({chat_id}): {e}"

    @classmethod
    async def publish_quiz_to_destination(
        cls,
        bot: Bot,
        chat_id: str,
        question_data: dict[str, Any],
        destination_id: Optional[int] = None
    ) -> Tuple[bool, Optional[int], Optional[str], str]:
        """
        Publishes a single quiz poll to a destination with retries.
        Returns: (success: bool, message_id: Optional[int], poll_id: Optional[str], error_message: str)
        """
        q_id = question_data.get("id", 1)
        category = question_data.get("category", "NEET")
        subject = question_data.get("subject", "Medical")
        topic = question_data.get("topic", "")
        difficulty = question_data.get("difficulty", "Medium")
        question_text = question_data["question"]
        options = [
            question_data["option_a"],
            question_data["option_b"],
            question_data["option_c"],
            question_data["option_d"]
        ]
        correct_option = int(question_data["correct_option"])
        explanation = question_data.get("explanation", "")

        # Settings
        send_header = (await database.get_setting("send_header", "true")).lower() in ("true", "1", "yes")
        send_explanation = (await database.get_setting("send_explanation", "true")).lower() in ("true", "1", "yes")

        # Telegram Poll Constraints
        poll_q = truncate_text(question_text, 300)
        poll_options = [truncate_text(opt, 100) for opt in options]
        poll_expl = truncate_text(explanation, 200)

        max_retries = 3
        backoff = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                # 1. Optional Header Announcement
                if send_header:
                    header_text = format_header_message(category, subject, topic, difficulty, q_id)
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=header_text,
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as he:
                        logger.warning(f"Header post non-critical error: {he}")

                # 2. Native Quiz Poll
                poll_message = await bot.send_poll(
                    chat_id=chat_id,
                    question=poll_q,
                    options=poll_options,
                    type=PollType.QUIZ,
                    correct_option_id=correct_option,
                    is_anonymous=True,
                    explanation=poll_expl,
                    explanation_parse_mode=ParseMode.HTML
                )

                # 3. Optional Detailed Post-Quiz Explanation
                if send_explanation and explanation:
                    corr_letter = OPTION_LETTERS[correct_option] if 0 <= correct_option < 4 else ""
                    corr_text = options[correct_option] if 0 <= correct_option < 4 else ""
                    expl_msg = format_explanation_message(explanation, corr_letter, corr_text)
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=expl_msg,
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as ee:
                        logger.warning(f"Explanation post non-critical error: {ee}")

                # Update database record
                poll_id = poll_message.poll.id if poll_message.poll else str(poll_message.message_id)
                msg_id = poll_message.message_id

                await database.update_question_post_status(
                    question_id=q_id,
                    status="published",
                    telegram_message_id=msg_id,
                    telegram_poll_id=poll_id,
                    destination_id=destination_id
                )

                logger.info(f"Quiz #{q_id} successfully published to {chat_id} (Message ID: {msg_id})")
                return True, msg_id, poll_id, ""

            except RetryAfter as ra:
                logger.warning(f"Telegram Flood control: sleeping {ra.retry_after}s...")
                await asyncio.sleep(ra.retry_after + 1)
            except (TimedOut, TelegramError) as te:
                logger.warning(f"Telegram API error on attempt {attempt}/{max_retries}: {te}")
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    err_msg = f"Failed after {max_retries} retries: {te}"
                    await database.update_question_post_status(question_id=q_id, status="failed")
                    return False, None, None, err_msg
            except Exception as e:
                err_msg = f"Unexpected error broadcasting to {chat_id}: {e}"
                logger.error(err_msg)
                await database.update_question_post_status(question_id=q_id, status="failed")
                return False, None, None, err_msg

        return False, None, None, "Max retries exceeded."

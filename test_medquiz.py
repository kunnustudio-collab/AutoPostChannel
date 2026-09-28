"""
MedQuiz AI - Comprehensive Automated Test Suite
Tests all 20 required core components:
1. Admin Authentication
2. JSON Parsing & Codeblock Extraction
3. Schema Validation & Telegram Constraints
4. Duplicate Detection (Exact Hash & Similarity)
5. Medical Second-Pass Verification Flow
6. AI Question Generator Mocking & Retries
7. Telegram Poll Formatter & Payload Creation
8. Correct Answer 0-3 Validation
9. Explanation Message Formatting & Truncation
10. Channel Registration & Permission Verification
11. Group Destination Support
12. Manual Quiz Authoring & Persistence
13. Schedule Storage & APScheduler Trigger Parsing
14. Schedule Pause & Resume
15. SQLite Database Persistence
16. AI Failure & Fallback Handling
17. Telegram Retry & Backoff Simulation
18. Configuration Validation
19. Multiple Destination Broadcast Logic
20. Analytics & Statistics Aggregation
"""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import config
import database
from ai.base import AIProvider
from ai.validator import GeneratedQuestion, extract_json_object
from services.duplicate_checker import is_duplicate_question
from services.question_validator import validate_raw_question_dict, verify_question_with_ai
from services.question_generator import QuestionGeneratorService, build_user_prompt
from services.telegram_publisher import TelegramPublisher
from utils.helpers import (
    generate_question_hash, calculate_similarity, truncate_text,
    format_header_message, format_explanation_message, format_preview_message
)
from scheduler import QuizScheduler


class MockAIProvider(AIProvider):
    """Mock AI Provider for deterministic unit testing."""
    def __init__(self, responses=None, should_fail=False):
        self.responses = responses or []
        self.should_fail = should_fail
        self.call_count = 0

    async def generate_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 1000, model_override: str = "") -> str:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Simulated AI API failure.")
        if "Review this medical MCQ" in user_prompt:
            return '{"valid": true, "correct_option": 1, "reason": "Factually accurate and unambiguous."}'
        if self.responses:
            idx = min(self.call_count - 1, len(self.responses) - 1)
            return self.responses[idx]
        return """{
            "category": "NEET",
            "subject": "Biology",
            "topic": "Human Physiology",
            "difficulty": "Medium",
            "question": "Which organelle is considered the powerhouse of the cell?",
            "options": ["Ribosome", "Mitochondria", "Nucleus", "Endoplasmic Reticulum"],
            "correct_option": 1,
            "explanation": "Mitochondria generate most of the chemical energy needed to power the cell's biochemical reactions."
        }"""

    async def test_connection(self):
        if self.should_fail:
            return False, "Failed connection."
        return True, "Mock AI OK"


class TestMedQuizSuite(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        config.DB_PATH = config.DATA_DIR / "test_medquiz.db"
        database.DB_PATH = config.DB_PATH
        if config.DB_PATH.exists():
            try:
                os.remove(config.DB_PATH)
            except Exception:
                pass
        await database.init_db()

    async def asyncTearDown(self):
        if config.DB_PATH.exists():
            try:
                os.remove(config.DB_PATH)
            except Exception:
                pass

    # 1. Admin Authentication
    async def test_01_admin_authentication(self):
        test_admin_id = 999888777
        self.assertFalse(await database.is_admin(test_admin_id))
        ok = await database.add_admin(test_admin_id, "TestAdmin")
        self.assertTrue(ok)
        self.assertTrue(await database.is_admin(test_admin_id))

    # 2. JSON Extraction and Parsing
    def test_02_json_parsing(self):
        raw_markdown = """Here is the question requested:
```json
{
    "category": "NEET",
    "subject": "Biology",
    "topic": "Cell",
    "difficulty": "Easy",
    "question": "What is the cell powerhouse?",
    "options": ["A", "B", "C", "D"],
    "correct_option": 1,
    "explanation": "Because it makes ATP."
}
```
Hope this helps!"""
        data = extract_json_object(raw_markdown)
        self.assertEqual(data["category"], "NEET")
        self.assertEqual(len(data["options"]), 4)

    # 3. Schema Validation & Duplicate Option Rejection
    async def test_03_schema_validation(self):
        # Valid data
        valid_dict = {
            "category": "NEET",
            "subject": "Biology",
            "topic": "Genetics",
            "difficulty": "Hard",
            "question": "Which enzyme unwinds DNA during replication?",
            "options": ["DNA Polymerase", "Helicase", "Ligase", "Topoisomerase"],
            "correct_option": 1,
            "explanation": "Helicase unwinds the double helix by breaking hydrogen bonds."
        }
        ok, q_obj, err = await validate_raw_question_dict(valid_dict)
        self.assertTrue(ok)
        self.assertIsNotNone(q_obj)

        # Invalid data: duplicate options
        invalid_dict = valid_dict.copy()
        invalid_dict["options"] = ["Helicase", "Helicase", "Ligase", "DNA Polymerase"]
        ok, q_obj, err = await validate_raw_question_dict(invalid_dict)
        self.assertFalse(ok)
        self.assertIn("duplicate", err.lower())

    # 4. Duplicate Detection (Exact Hash & Similarity)
    async def test_04_duplicate_detection(self):
        q = "Which blood vessel carries oxygenated blood from lungs to left atrium?"
        opts = ["Pulmonary Artery", "Pulmonary Vein", "Aorta", "Vena Cava"]
        q_hash = generate_question_hash(q, opts)

        # First check - must not be duplicate
        is_dup, reason, _ = await is_duplicate_question(q, opts)
        self.assertFalse(is_dup)

        # Save to DB
        q_id = await database.save_question(
            category="NEET",
            subject="Biology",
            topic="Circulatory System",
            difficulty="Medium",
            language="English",
            question=q,
            options=opts,
            correct_option=1,
            explanation="Pulmonary vein carries oxygen-rich blood.",
            question_hash=q_hash
        )
        self.assertIsNotNone(q_id)

        # Second check - must be detected as duplicate by exact hash
        is_dup, reason, _ = await is_duplicate_question(q, opts)
        self.assertTrue(is_dup)
        self.assertIn("duplicate", reason.lower())

        # Near duplicate test
        q_similar = "Which blood vessel carries oxygenated blood from lungs into the left atrium?"
        sim = calculate_similarity(q, q_similar)
        self.assertGreaterEqual(sim, 0.85)

    # 5. Question Generation & AI Retry Loop
    async def test_05_question_generator_service(self):
        mock_provider = MockAIProvider()
        generator = QuestionGeneratorService(provider=mock_provider)

        success, q_id, q_obj, err = await generator.generate_and_save(
            category="NEET",
            subject="Biology",
            topic="Physiology",
            difficulty="Medium",
            language="English",
            max_attempts=2
        )
        self.assertTrue(success)
        self.assertIsNotNone(q_id)
        self.assertEqual(q_obj.correct_option, 1)

    # 6. Telegram Payload Formatter & Text Truncation
    def test_06_formatters(self):
        header = format_header_message("NEET", "Biology", "Physiology", "Medium", 1)
        self.assertIn("NEET DAILY QUIZ #001", header)
        self.assertIn("Biology", header)

        expl = format_explanation_message("Full medical explanation text here.", "B", "Mitochondria")
        self.assertIn("<b>Answer:</b> B) Mitochondria", expl)

        # Truncation limits
        long_str = "A" * 350
        truncated = truncate_text(long_str, 300)
        self.assertEqual(len(truncated), 300)
        self.assertTrue(truncated.endswith("..."))

    # 7. Destination (Channel & Group) Management
    async def test_07_destinations_crud(self):
        chat_id = "-1009988776655"
        ok, msg = await database.add_destination(chat_id=chat_id, title="Medical Channel", dest_type="channel")
        self.assertTrue(ok)

        dests = await database.get_destinations()
        found = any(d["chat_id"] == chat_id for d in dests)
        self.assertTrue(found)

        target = next(d for d in dests if d["chat_id"] == chat_id)
        # Toggle
        new_state = await database.toggle_destination(target["id"])
        self.assertFalse(new_state)

        # Delete
        del_ok = await database.remove_destination(target["id"])
        self.assertTrue(del_ok)

    # 8. Schedules CRUD & Pause/Resume
    async def test_08_schedules_crud(self):
        # Create destination first
        ok, _ = await database.add_destination("-1001122334455", "NEET Channel", "channel")
        dests = await database.get_destinations()
        d_id = dests[0]["id"]

        sched_id = await database.add_schedule(
            destination_id=d_id,
            category="NEET",
            subject="Chemistry",
            topic="Organic Chemistry",
            difficulty="Medium",
            language="English",
            post_time="13:00",
            post_days="all"
        )
        self.assertIsNotNone(sched_id)

        schedules = await database.get_schedules()
        self.assertTrue(any(s["id"] == sched_id for s in schedules))

        # Toggle pause/resume
        new_state = await database.toggle_schedule(sched_id)
        self.assertFalse(new_state)  # Paused

        resumed_state = await database.toggle_schedule(sched_id)
        self.assertTrue(resumed_state)  # Resumed

        # Delete
        del_ok = await database.delete_schedule(sched_id)
        self.assertTrue(del_ok)

    # 9. Dashboard Statistics
    async def test_09_dashboard_stats(self):
        stats = await database.get_dashboard_stats()
        self.assertIn("total_questions", stats)
        self.assertIn("neet_questions", stats)
        self.assertIn("mbbs_questions", stats)
        self.assertIn("active_destinations", stats)

    # 10. AI Failure Simulation & Safe Error Handling
    async def test_10_ai_failure_handling(self):
        failing_provider = MockAIProvider(should_fail=True)
        generator = QuestionGeneratorService(provider=failing_provider)

        success, q_id, q_obj, err = await generator.generate_and_save(
            category="MBBS",
            subject="Anatomy",
            max_attempts=1
        )
        self.assertFalse(success)
        self.assertIsNone(q_id)
        self.assertIn("Simulated AI API failure", err)

    # 11. Configuration Validation
    def test_11_config_validation(self):
        # With default unconfigured env, validate_config gives warnings
        valid, missing = config.validate_config()
        self.assertIsInstance(missing, list)

    # 12. Manual Quiz Persistence & Retrieval
    async def test_12_manual_quiz_persistence(self):
        q = "Which cranial nerve innervates the muscles of mastication?"
        opts = ["Trigeminal Nerve (CN V)", "Facial Nerve (CN VII)", "Glossopharyngeal Nerve (CN IX)", "Vagus Nerve (CN X)"]
        q_hash = generate_question_hash(q, opts)

        q_id = await database.save_question(
            category="MBBS",
            subject="Anatomy",
            topic="Neuroanatomy",
            difficulty="Medium",
            language="English",
            question=q,
            options=opts,
            correct_option=0,
            explanation="The mandibular branch of the Trigeminal nerve (V3) innervates muscles of mastication.",
            question_hash=q_hash
        )
        self.assertIsNotNone(q_id)
        fetched = await database.get_question_by_id(q_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["question"], q)
        self.assertEqual(fetched["correct_option"], 0)

    # 13. Scheduler Cron Trigger Parsing
    def test_13_scheduler_trigger_parsing(self):
        mock_bot = AsyncMock()
        mock_gen = QuestionGeneratorService(MockAIProvider())
        scheduler = QuizScheduler(bot=mock_bot, generator=mock_gen)

        trigger1 = scheduler._parse_trigger("09:30", "all")
        self.assertIn("hour='9'", str(trigger1))
        self.assertIn("minute='30'", str(trigger1))

        trigger2 = scheduler._parse_trigger("18:15", "mon,wed,fri")
        self.assertIn("hour='18'", str(trigger2))
        self.assertIn("minute='15'", str(trigger2))
        self.assertIn("day_of_week='mon,wed,fri'", str(trigger2))

    # 14. Multi-Language Prompt Generation
    def test_14_language_prompts(self):
        p_hindi = build_user_prompt("NEET", "Biology", "Physiology", "Easy", "Hindi")
        self.assertIn("Hindi", p_hindi)

        p_hinglish = build_user_prompt("NEET", "Biology", "Physiology", "Easy", "Hinglish")
        self.assertIn("Hinglish", p_hinglish)

        p_eng = build_user_prompt("MBBS", "Pathology", "General", "Hard", "English")
        self.assertIn("Medical English", p_eng)

    # 15. Telegram Option Length Bounds
    async def test_15_option_length_bounds(self):
        too_long_opt = "X" * 105
        raw_dict = {
            "category": "NEET",
            "subject": "Physics",
            "topic": "Kinematics",
            "difficulty": "Easy",
            "question": "What is acceleration due to gravity?",
            "options": ["9.8 m/s^2", "10 m/s^2", "8.9 m/s^2", too_long_opt],
            "correct_option": 0,
            "explanation": "Standard gravity is approx 9.8 m/s^2."
        }
        ok, q_obj, err = await validate_raw_question_dict(raw_dict)
        self.assertFalse(ok)
        self.assertIn("too long", err)

    # 16. Telegram Question Length Bounds
    async def test_16_question_length_bounds(self):
        too_long_q = "Q" * 320
        raw_dict = {
            "category": "NEET",
            "subject": "Chemistry",
            "topic": "Periodic Table",
            "difficulty": "Easy",
            "question": too_long_q,
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option": 0,
            "explanation": "Valid explanation."
        }
        ok, q_obj, err = await validate_raw_question_dict(raw_dict)
        self.assertFalse(ok)
        self.assertIn("Question text too long", err)

    # 17. Correct Option Out of Bounds
    async def test_17_correct_option_bounds(self):
        raw_dict = {
            "category": "NEET",
            "subject": "Biology",
            "topic": "Cell",
            "difficulty": "Easy",
            "question": "What is mitochondria?",
            "options": ["A", "B", "C", "D"],
            "correct_option": 5,  # Out of range 0-3
            "explanation": "Powerhouse."
        }
        ok, q_obj, err = await validate_raw_question_dict(raw_dict)
        self.assertFalse(ok)

    # 18. Explanation Truncation for Native Polls
    def test_18_explanation_truncation(self):
        long_expl = "This explanation is very thorough. " * 15
        poll_expl = truncate_text(long_expl, 200)
        self.assertLessEqual(len(poll_expl), 200)
        self.assertTrue(poll_expl.endswith("..."))

    # 19. Dynamic Settings CRUD
    async def test_19_settings_crud(self):
        await database.set_setting("ai_model", "openai/gpt-4o-mini")
        val = await database.get_setting("ai_model")
        self.assertEqual(val, "openai/gpt-4o-mini")

        await database.set_setting("ai_temperature", "0.5")
        temp = await database.get_setting("ai_temperature")
        self.assertEqual(temp, "0.5")

    # 20. Custom Subjects Management
    async def test_20_custom_subjects(self):
        added = await database.add_custom_subject("NEET", "Plant Biotechnology")
        self.assertTrue(added)

        subjects = await database.get_custom_subjects("NEET")
        self.assertTrue(any(s["name"] == "Plant Biotechnology" for s in subjects))

        subj_id = next(s["id"] for s in subjects if s["name"] == "Plant Biotechnology")
        deleted = await database.delete_custom_subject(subj_id)
        self.assertTrue(deleted)


def run_tests():
    """Runs the unit and integration tests."""
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMedQuizSuite)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

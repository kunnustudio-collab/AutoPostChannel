"""
MedQuiz AI - Question Generator Service
Constructs tailored prompts, communicates with AI provider, validates, checks duplicates, and saves to database.
"""

import random
from typing import Tuple, Optional
from ai.base import AIProvider
from ai.validator import GeneratedQuestion, extract_json_object
from services.question_validator import validate_raw_question_dict, verify_question_with_ai
from services.duplicate_checker import is_duplicate_question
import database
from utils.logger import logger
from config import NEET_SUBJECTS, MBBS_SUBJECTS

SYSTEM_PROMPT = """You are a premier medical professor, curriculum designer, and question writer for NEET UG and MBBS exams.
Your task is to produce rigorous, factually unimpeachable multiple-choice questions (MCQs) for medical aspirants and students.

RULES:
1. Output MUST be STRICT JSON only, matching the exact requested format.
2. Exactly 4 distinct options (no duplicate options).
3. Exactly ONE unambiguous correct option.
4. For NEET: adhere to standard NCERT syllabus (Biology, Physics, Chemistry).
5. For MBBS: focus on high-yield clinical vignettes, mechanisms, pathology, and therapeutics.
6. The question text MUST NOT exceed 280 characters to adhere to Telegram Poll character limits.
7. Each option MUST NOT exceed 95 characters.
8. The explanation should be concise, educational, and clinically or conceptually clear (150-200 words).
9. Never put the answer or answer letter inside the question text."""


def build_user_prompt(
    category: str,
    subject: str,
    topic: str,
    difficulty: str,
    language: str
) -> str:
    """Builds a customized instruction prompt for the LLM."""
    # Resolve Random selections
    if difficulty.lower() in ("random", "🎲 random"):
        difficulty = random.choice(["Easy", "Medium", "Hard"])

    if subject.lower() in ("random", "🎲 any / random subject"):
        if category == "NEET":
            subject = random.choice(list(NEET_SUBJECTS.keys()))
        else:
            subject = random.choice(list(MBBS_SUBJECTS.keys()))

    if topic.lower() in ("random", "🎲 any / random topic", ""):
        if category == "NEET" and subject in NEET_SUBJECTS:
            topic = random.choice(NEET_SUBJECTS[subject])
        elif category == "MBBS" and subject in MBBS_SUBJECTS:
            topic = random.choice(MBBS_SUBJECTS[subject])
        else:
            topic = "Core High-Yield Concepts"

    lang_instruction = ""
    if language.lower() in ("hindi", "🇮🇳 hindi"):
        lang_instruction = (
            "LANGUAGE: Write the question, options, and explanation in clean Hindi (Devanagari script). "
            "Technical anatomical and medical terms can remain in English or transliterated."
        )
    elif language.lower() in ("hinglish", "🇮🇳 hinglish"):
        lang_instruction = (
            "LANGUAGE: Write the question, options, and explanation in conversational Hinglish (Hindi written in Latin script), "
            "keeping standard medical and scientific terminology in English as widely spoken by Indian medical students."
        )
    else:
        lang_instruction = "LANGUAGE: Professional Medical English."

    return f"""Create ONE high-yield {category} MCQ.

Target Exam: {category}
Subject: {subject}
Topic: {topic}
Difficulty: {difficulty}
{lang_instruction}

JSON FORMAT REQUIRED:
{{
  "category": "{category}",
  "subject": "{subject}",
  "topic": "{topic}",
  "difficulty": "{difficulty}",
  "question": "Clear, precise question statement (max 280 chars)",
  "options": [
    "Option A",
    "Option B",
    "Option C",
    "Option D"
  ],
  "correct_option": 0,
  "explanation": "Clear educational explanation."
}}

Note: correct_option must be an integer (0 for first option, 1 for second, 2 for third, 3 for fourth)."""


class QuestionGeneratorService:
    """Orchestrates question generation, validation, verification, and persistence."""

    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def generate_and_save(
        self,
        category: str,
        subject: str,
        topic: str = "Random",
        difficulty: str = "Medium",
        language: str = "English",
        destination_id: Optional[int] = None,
        max_attempts: int = 3
    ) -> Tuple[bool, Optional[int], Optional[GeneratedQuestion], str]:
        """
        Generates a validated, non-duplicate medical question with up to `max_attempts`.
        Returns: (success: bool, question_id: Optional[int], question_obj: Optional[GeneratedQuestion], error_msg: str)
        """
        last_error = ""

        # Fetch configured AI parameters
        db_temp_str = await database.get_setting("ai_temperature", "0.7")
        try:
            temperature = float(db_temp_str)
        except ValueError:
            temperature = 0.7

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Question generation attempt {attempt}/{max_attempts} for {category} - {subject}...")
            user_prompt = build_user_prompt(category, subject, topic, difficulty, language)

            try:
                # 1. AI API Completion
                raw_response = await self.provider.generate_completion(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=2000
                )

                # 2. Extract and Parse JSON
                data = extract_json_object(raw_response)

                # 3. Pydantic and Telegram Bounds Validation
                is_valid, q_obj, val_err = await validate_raw_question_dict(data)
                if not is_valid or not q_obj:
                    last_error = f"Validation failed: {val_err}"
                    logger.warning(f"Attempt {attempt} invalid: {last_error}")
                    continue

                # 4. Duplicate Check (Hash and Similarity)
                is_dup, dup_reason, q_hash = await is_duplicate_question(q_obj.question, q_obj.options)
                if is_dup:
                    last_error = f"Duplicate detected: {dup_reason}"
                    logger.warning(f"Attempt {attempt} duplicate: {last_error}")
                    continue

                # 5. Optional Medical Second-Pass Verification
                verified, verif_msg, verified_key = await verify_question_with_ai(self.provider, q_obj)
                if not verified:
                    last_error = f"Verification rejected: {verif_msg}"
                    logger.warning(f"Attempt {attempt} rejected by verifier: {last_error}")
                    continue

                if verified_key is not None and verified_key != q_obj.correct_option:
                    q_obj.correct_option = verified_key

                # 6. Save in SQLite Database
                q_id = await database.save_question(
                    category=q_obj.category,
                    subject=q_obj.subject,
                    topic=q_obj.topic,
                    difficulty=q_obj.difficulty,
                    language=language,
                    question=q_obj.question,
                    options=q_obj.options,
                    correct_option=q_obj.correct_option,
                    explanation=q_obj.explanation,
                    question_hash=q_hash,
                    destination_id=destination_id,
                    status="generated"
                )

                if q_id:
                    logger.info(f"Successfully generated and saved question #{q_id} for {category} {subject}")
                    return True, q_id, q_obj, ""
                else:
                    last_error = "Database integrity check prevented saving duplicate hash."

            except Exception as e:
                last_error = f"Generation error: {e}"
                logger.error(f"Attempt {attempt} exception: {e}")

        logger.error(f"Failed to generate valid question after {max_attempts} attempts. Last error: {last_error}")
        return False, None, None, last_error

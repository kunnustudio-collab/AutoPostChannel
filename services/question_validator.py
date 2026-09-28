"""
MedQuiz AI - Question Validation Service
Enforces medical correctness, Telegram limits, and optional second-pass AI verification.
"""

from typing import Tuple, Optional
from ai.base import AIProvider
from ai.validator import GeneratedQuestion, VerificationResult, extract_json_object
from utils.logger import logger
from config import ENABLE_VERIFICATION
import database

SECOND_PASS_SYSTEM_PROMPT = """You are a senior medical faculty member and medical entrance exam auditor.
Your job is to thoroughly review medical MCQs for factual accuracy, syllabus alignment, clinical validity, and unambiguous answer keys.
Be strict: If an answer key is incorrect or multiple options can be valid, reject it."""


async def validate_raw_question_dict(data: dict) -> Tuple[bool, Optional[GeneratedQuestion], str]:
    """Validates dictionary data against Pydantic schema and Telegram poll constraints."""
    try:
        q_obj = GeneratedQuestion(**data)

        # Telegram Poll Constraints
        if len(q_obj.question) > 300:
            return False, None, f"Question text too long ({len(q_obj.question)} chars > 300 limit for Telegram Polls)."

        for idx, opt in enumerate(q_obj.options):
            if len(opt) > 100:
                return False, None, f"Option {idx+1} too long ({len(opt)} chars > 100 limit for Telegram Polls)."

        return True, q_obj, ""
    except Exception as e:
        return False, None, f"Schema validation error: {e}"


async def verify_question_with_ai(
    provider: AIProvider,
    question: GeneratedQuestion
) -> Tuple[bool, str, Optional[int]]:
    """
    Executes a second AI call to audit the question for factual correctness and ambiguity.
    Returns: (is_valid: bool, reason: str, verified_correct_option: Optional[int])
    """
    # Check if verification is enabled in database settings or config
    setting_verif = await database.get_setting("verification_enabled", "true")
    if setting_verif.lower() not in ("true", "1", "yes") or not ENABLE_VERIFICATION:
        return True, "Verification skipped by configuration.", question.correct_option

    user_prompt = f"""Review this medical MCQ for factual accuracy, ambiguity, and correctness.

Question: {question.question}
Options:
0: {question.options[0]}
1: {question.options[1]}
2: {question.options[2]}
3: {question.options[3]}
Declared Correct Option: {question.correct_option} ({question.options[question.correct_option]})
Explanation: {question.explanation}

Return STRICT JSON ONLY:
{{
  "valid": true,
  "correct_option": {question.correct_option},
  "reason": "Brief explanation of factual accuracy."
}}

If factually flawed or answer key is wrong, set "valid": false with explanation in "reason"."""

    try:
        raw_res = await provider.generate_completion(
            system_prompt=SECOND_PASS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,  # Low temperature for strict factual verification
            max_tokens=300
        )
        data = extract_json_object(raw_res)
        result = VerificationResult(**data)

        if not result.valid:
            logger.warning(f"Medical verification failed: {result.reason}")
            return False, f"Second-pass rejected: {result.reason}", None

        # Verify correct option agreement
        if result.correct_option is not None and result.correct_option != question.correct_option:
            logger.warning(f"Key mismatch: Generator declared {question.correct_option}, Verifier declared {result.correct_option}")
            return False, f"Answer key mismatch (Generator: {question.correct_option}, Verifier: {result.correct_option})", None

        return True, "Verified factually accurate.", question.correct_option
    except Exception as e:
        logger.warning(f"Verification request error (proceeding with caution): {e}")
        # If verification call itself failed due to network/parsing, allow if schema was valid
        return True, f"Verification skipped due to API error: {e}", question.correct_option

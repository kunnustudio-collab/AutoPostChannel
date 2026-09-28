"""
MedQuiz AI - AI Output Validator & JSON Parser
Performs strict schema validation, option uniqueness checks, and robust JSON sanitization.
"""

import json
import re
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class GeneratedQuestion(BaseModel):
    """Pydantic schema representing a validated medical question."""
    category: str = Field(..., description="NEET or MBBS")
    subject: str = Field(..., description="Subject name")
    topic: str = Field(default="General", description="Topic within subject")
    difficulty: str = Field(default="Medium", description="Easy, Medium, or Hard")
    question: str = Field(..., min_length=10, description="The MCQ question statement")
    options: List[str] = Field(..., min_length=4, max_length=4, description="Exactly 4 options")
    correct_option: int = Field(..., ge=0, le=3, description="Index of correct option (0-3)")
    explanation: str = Field(..., min_length=10, description="Educational explanation of correct answer")

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: List[str]) -> List[str]:
        if len(v) != 4:
            raise ValueError(f"Expected exactly 4 options, got {len(v)}")

        cleaned = [opt.strip() for opt in v]
        for idx, opt in enumerate(cleaned):
            if not opt:
                raise ValueError(f"Option {idx + 1} cannot be empty")

        # Check for duplicate options (case-insensitive)
        lowered = [opt.lower() for opt in cleaned]
        if len(set(lowered)) != 4:
            raise ValueError("All 4 options must be distinctly different (duplicate options found)")

        return cleaned

    @field_validator("correct_option")
    @classmethod
    def validate_correct_option(cls, v: int) -> int:
        if v not in (0, 1, 2, 3):
            raise ValueError(f"correct_option must be 0, 1, 2, or 3. Got {v}")
        return v


class VerificationResult(BaseModel):
    """Schema for second-pass AI factual verification."""
    valid: bool
    correct_option: Optional[int] = None
    reason: str = ""
    corrected_question: Optional[str] = None
    corrected_options: Optional[List[str]] = None


def extract_json_object(raw_text: str) -> dict:
    """
    Extracts a JSON object from raw LLM output, handling reasoning tokens,
    fenced code blocks, and extraneous conversational prelude.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("AI response was empty.")

    text = raw_text.strip()

    # Priority 1: Check for fenced code block ```json ... ``` or ``` ... ```
    matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    for block in reversed(matches):
        block = block.strip()
        start = block.find("{")
        end = block.rfind("}")
        if start != -1 and end != -1 and end > start:
            cand = block[start : end + 1]
            cand = re.sub(r",\s*([\]}])", r"\1", cand)
            try:
                d = json.loads(cand)
                if isinstance(d, dict) and "question" in d:
                    return d
            except Exception:
                continue

    # Priority 2: Search backwards for the last valid JSON block
    last_brace = text.rfind("}")
    if last_brace != -1:
        start_indices = [i for i, ch in enumerate(text[:last_brace]) if ch == "{"]
        for start_pos in reversed(start_indices):
            cand = text[start_pos : last_brace + 1]
            cand = re.sub(r",\s*([\]}])", r"\1", cand)
            try:
                d = json.loads(cand)
                if isinstance(d, dict) and ("question" in d or "valid" in d):
                    return d
            except Exception:
                continue

    # Priority 3: Standard slice
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        cand = text[start : end + 1]
        cand = re.sub(r",\s*([\]}])", r"\1", cand)
        return json.loads(cand)

    raise ValueError("No valid JSON object found in AI response.")

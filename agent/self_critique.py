"""Self-Critique Module - LLM-based reflection for patch candidates.

This module provides the `LLMCritique` class, which uses an LLM to evaluate
candidate patches against the task description before they are submitted to the
deterministic gate. This "think before you commit" step reduces gate rejections
and improves alignment with the task.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

try:
    from rfsn_controller.llm.deepseek import call_model as call_deepseek
    HAS_DEEPSEEK = True
except ImportError:
    HAS_DEEPSEEK = False

try:
    from rfsn_controller.llm.gemini import call_model as call_gemini
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logger = logging.getLogger(__name__)


@dataclass
class Critique:
    """Structured critique of a patch candidate."""
    approved: bool
    score: float  # 0.0 to 1.0
    reasoning: str
    suggestions: list[str]


class LLMCritique:
    """LLM-based critic for patch candidates."""

    def __init__(self, model_name: str = "deepseek"):
        self.model_name = model_name

    def critique(self, task: dict[str, Any], patch_text: str) -> Critique:
        """
        Critique a patch candidate against the task description.

        Args:
            task: The task dictionary (must contain 'problem_statement').
            patch_text: The unified diff patch text.

        Returns:
            Critique object with approval status, score, and feedback.
        """
        prompt = self._build_prompt(task, patch_text)
        
        response_text = ""
        try:
            if self.model_name == "deepseek" and HAS_DEEPSEEK:
                resp = call_deepseek(prompt, temperature=0.7)
                response_text = resp if isinstance(resp, str) else json.dumps(resp)
            elif self.model_name == "gemini" and HAS_GEMINI:
                resp = call_gemini(prompt)
                response_text = resp if isinstance(resp, str) else json.dumps(resp)
            else:
                # Fallback / Mock
                logger.warning(f"Model {self.model_name} not available. Using dummy critique.")
                return Critique(
                    approved=True,
                    score=0.5,
                    reasoning="Mock critique: Model not available.",
                    suggestions=[]
                )
        except Exception as e:
            logger.error(f"Critique LLM call failed: {e}")
            # Fail safe: approve if critic breaks, but with low score
            return Critique(
                approved=True,
                score=0.5,
                reasoning=f"Critique failed: {e}",
                suggestions=[]
            )

        return self._parse_response(response_text)

    def _build_prompt(self, task: dict[str, Any], patch_text: str) -> str:
        """Build the critique prompt."""
        problem = task.get("problem_statement", "No problem statement provided.")
        
        return f"""# SYSTEM: You are a Senior Code Reviewer.
Your goal is to critique a proposed patch for a software bug.
Be strict but constructive. Focus on:
1. Does the patch actually address the described issue?
2. Are there obvious bugs or regressions?
3. Is the code style consistent?
4. Is the patch minimal and safe?

# ISSUE DESCRIPTION
{problem[:2000]}... (truncated)

# PROPOSED PATCH
```diff
{patch_text[:2000]}... (truncated if too long)
```

# INSTRUCTIONS
Analyze the patch.
Output strictly in JSON format:
```json
{{
  "approved": boolean,
  "score": float, // 0.0 to 1.0 (1.0 is perfect)
  "reasoning": "string explanation",
  "suggestions": ["suggestion 1", "suggestion 2"]
}}
```
"""

    def _parse_response(self, text: str) -> Critique:
        """Parse LLM JSON response."""
        try:
            # simple fuzzy cleaner for code blocks
            clean_text = text
            if "```json" in text:
                clean_text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                clean_text = text.split("```")[0]
            
            data = json.loads(clean_text.strip())
            return Critique(
                approved=bool(data.get("approved", False)),
                score=float(data.get("score", 0.0)),
                reasoning=data.get("reasoning", "No reasoning provided."),
                suggestions=data.get("suggestions", [])
            )
        except Exception as e:
            logger.warning(f"Failed to parse critique response: {e}. Raw: {text[:100]}...")
            return Critique(
                approved=False,
                score=0.0,
                reasoning="Failed to parse critique JSON.",
                suggestions=[]
            )

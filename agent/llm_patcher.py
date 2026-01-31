"""LLM Patcher - Connects Upstream Intelligence to DeepSeek/Gemini.

This module provides the `llm_patch_fn` required by the unified eval harness.
It builds rich prompts using:
- Repair taxonomy hypotheses
- Retrieved failure patterns
- Repo-specific skill instructions
"""
from __future__ import annotations

import json
import logging
import re
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


def get_llm_patch_fn(model_name: str = "deepseek") -> Any:
    """Get the patch generation function for the specified model."""
    
    def llm_patch_fn(plan: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Generate patch candidates.
        
        Args:
            plan: The repair plan (has .bug_summary, .metadata)
            context: Dict with keys:
                - hypotheses: List[RepairHypothesis]
                - retrieval: Dict with 'similar_failures'
                - skill_heads: List[SkillHead]
                - planner_name: str
                
        Returns:
            List of dicts with 'patch_text', 'summary'
        """
        # 1. Build Prompt
        prompt = _build_prompt(plan, context)
        
        # 2. Call LLM
        response_text = ""
        try:
            if model_name == "deepseek" and HAS_DEEPSEEK:
                # DeepSeek uses a specific format usually
                # Assuming call_deepseek returns a dict or str
                resp = call_deepseek(prompt, temperature=0.7)
                response_text = resp if isinstance(resp, str) else json.dumps(resp)
            elif model_name == "gemini" and HAS_GEMINI:
                resp = call_gemini(prompt)
                response_text = resp if isinstance(resp, str) else json.dumps(resp)
            else:
                # Fallback / Mock
                logger.warning(f"Model {model_name} not available. Using dummy.")
                return []
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return []
            
        # 3. Parse Response
        return _parse_response(response_text)

    return llm_patch_fn


def _build_prompt(plan: Any, context: dict[str, Any]) -> str:
    """Build a context-rich prompt for repair."""
    parts = []
    
    # --- TASK IDENTITY ---
    parts.append(f"# BUG REPORT\n{plan.bug_summary}\n")
    
    # --- REPAIR HYPOTHESES (from Classifier) ---
    hypotheses = context.get("hypotheses", [])
    if hypotheses:
        parts.append("# REPAIR ANALYSIS")
        parts.append("Our analysis suggests the following bug types:")
        for h in hypotheses:
            parts.append(f"- [{h.confidence:.2f}] {h.kind.upper()}: {h.reasoning}")
        parts.append("")
        
    # --- SKILL INSTRUCTIONS (from Router) ---
    skills = context.get("skill_heads", [])
    if skills:
        parts.append("# REPO-SPECIFIC GUIDANCE")
        for skill in skills:
            parts.append(f"## {skill.name}")
            parts.append(skill.prompt_suffix)
            # Patch style constraints
            style = skill.patch_style
            if style:
                constraints = []
                if "max_files" in style:
                    constraints.append(f"Max files: {style['max_files']}")
                if "max_lines" in style:
                    constraints.append(f"Max lines: {style['max_lines']}")
                if constraints:
                    parts.append("Size Limits: " + ", ".join(constraints))
        parts.append("")

    # --- RETRIEVAL (from Failure Index) ---
    retrieval = context.get("retrieval", {})
    similar = retrieval.get("similar_failures", [])
    if similar:
        parts.append("# LEARNED MEMORY (Similar Past Fixes)")
        for item in similar[:2]:
            parts.append(f"## Previous Fix ({item.get('score', 0.0):.2f} match)")
            parts.append(f"Context: {item.get('signature', '')[:200]}...")
            parts.append(f"Fix Strategy: {item.get('patch_summary', '')}")
            parts.append("")

    # --- INSTRUCTIONS ---
    parts.append("# INSTRUCTIONS")
    parts.append("Generate a valid Unified Diff patch to fix this bug.")
    parts.append("You must follow the guidance above.")
    parts.append("Output strictly in JSON format:")
    parts.append("""
```json
[
  {
    "summary": "Fix off-by-one error in ...",
    "patch_text": "--- a/file.py\\n+++ b/file.py\\n..."
  }
]
```
""")
    
    return "\n".join(parts)


def _parse_response(text: str) -> list[dict[str, Any]]:
    """Parse JSON response from LLM."""
    # Attempt to find JSON block
    try:
        match = re.search(r"```json\s*(.*)\s*```", text, re.DOTALL)
        content = match.group(1) if match else text
            
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []
    except Exception:
        # Fallback simple parser for raw diffs if model ignores JSON
        if "diff --git" in text or "--- a/" in text:
            return [{
                "patch_text": text,
                "summary": "Raw patch generated by LLM"
            }]
        return []

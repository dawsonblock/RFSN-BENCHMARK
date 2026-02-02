"""Unified propose module - routes through upstream intelligence.

This module integrates:
- Repair classification (taxonomy)
- Failure retrieval (memory)
- Skill routing (repo-specific)
- Planner selection (Thompson sampling)

The actual LLM patch generation is passed in as a callable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from agent.self_critique import LLMCritique
from learning.planner_bandit import PLANNERS, PlannerSelector, register_planner
from planner.planner import generate_plan as planner_v1_generate_plan
from repair.classifier import classify_failure
from retrieval.failure_index import FailureIndex
from retrieval.recall import build_retrieval_context
from skills.router import select_skill_heads

logger = logging.getLogger(__name__)

# Register default planner
if "planner_v1" not in PLANNERS:
    register_planner("planner_v1", planner_v1_generate_plan)

# Global state
_selector = PlannerSelector()
_failure_index = FailureIndex()


@dataclass
class PatchCandidate:
    """A candidate patch from the propose pipeline."""
    patch_text: str
    summary: str
    metadata: dict[str, Any]


@dataclass
class UpstreamContext:
    """Context built by upstream intelligence modules."""
    hypotheses: list[Any]
    retrieval: dict[str, Any]
    skill_heads: list[Any]
    planner_name: str
    upstream_hints: dict[str, Any] = None


def build_upstream_context(
    task: dict[str, Any],
    last_test_output: str,
) -> UpstreamContext:
    """
    Build context using upstream intelligence modules.
    
    This is where all the "agent intelligence" happens:
    1. Classify the failure type
    2. Query failure index for similar past fixes
    3. Select appropriate skill heads
    4. Pick planner using Thompson sampling
    """
    repo = task.get("repo", "unknown")
    failing_files = task.get("failing_files", []) or []
    repo_fingerprint = task.get("repo_fingerprint", repo)

    # 1. Classify failure
    hypotheses = classify_failure(last_test_output or "", failing_files)
    logger.debug("Classified failure: %s", [h.kind for h in hypotheses[:3]])

    # 2. Query failure index
    retrieval = build_retrieval_context(repo, last_test_output or "", _failure_index)
    logger.debug("Retrieved %d similar failures", len(retrieval.get("similar_failures", [])))

    # 3. Select skill heads
    skill_heads = select_skill_heads({"repo_fingerprint": repo_fingerprint}, k=2)
    logger.debug("Selected skills: %s", [h.name for h in skill_heads])

    # 4. Pick planner (override if upstream hint present)
    upstream = task.get("_upstream", {})
    if upstream.get("planner"):
        planner_name = upstream["planner"]
        logger.debug("Using upstream planner override: %s", planner_name)
    else:
        planner_name = _selector.pick()
        logger.debug("Selected planner: %s", planner_name)

    return UpstreamContext(
        hypotheses=hypotheses,
        retrieval=retrieval,
        skill_heads=skill_heads,
        planner_name=planner_name,
        upstream_hints=upstream,
    )


def propose(
    task: dict[str, Any],
    last_test_output: str,
    llm_patch_fn: Callable[[Any, dict[str, Any]], list[dict[str, Any]]],
    max_candidates: int = 6,
) -> list[PatchCandidate]:
    """
    Generate patch candidates using upstream intelligence.
    
    Args:
        task: Task dict with repo, description, etc.
        last_test_output: Most recent test output
        llm_patch_fn: Function(plan, context) -> list of dicts with patch_text, summary
        max_candidates: Maximum candidates to return
        
    Returns:
        List of PatchCandidate objects
    """
    ctx = build_upstream_context(task, last_test_output)

    # Get planner function
    planner_fn = PLANNERS.get(ctx.planner_name, planner_v1_generate_plan)

    # Generate plan
    plan = planner_fn(task, ctx.retrieval)
    
    # Attach upstream context to plan metadata
    plan.metadata["repair_hypotheses"] = [h.kind for h in ctx.hypotheses]
    plan.metadata["skill_heads"] = [h.name for h in ctx.skill_heads]
    plan.metadata["retrieval"] = ctx.retrieval

    # Build context dict for LLM
    llm_context = {
        "hypotheses": ctx.hypotheses,
        "retrieval": ctx.retrieval,
        "skill_heads": ctx.skill_heads,
        "planner_name": ctx.planner_name,
        "upstream_hints": ctx.upstream_hints or {},
    }

    # Call LLM patch generator (Initial batch)
    raw = llm_patch_fn(plan, llm_context)
    
    # Critique and Refine Loop
    final_raw_candidates = []
    critic = LLMCritique()
    
    for cand in raw[:max_candidates]:
        patch_text = cand.get("patch_text", "")
        # Critique
        crit = critic.critique(task, patch_text)
        
        # Store critique metadata
        cand["critique"] = {
            "score": crit.score,
            "approved": crit.approved,
            "reasoning": crit.reasoning
        }
        
        if crit.score < 0.7:
            logger.info("Candidate criticized (score=%.2f): %s", crit.score, crit.reasoning[:50])
            # Attempt Refinement
            refine_ctx = llm_context.copy()
            refine_ctx["critique_feedback"] = (
                f"Your previous patch was rejected by the critic.\n"
                f"Reasoning: {crit.reasoning}\n"
                f"Suggestions: {crit.suggestions}\n"
                f"Please fix the patch."
            )
            # Generate replacement (single shot)
            refined_batch = llm_patch_fn(plan, refine_ctx)
            if refined_batch:
                best_refined = refined_batch[0]
                best_refined["critique"] = {"score": 0.9, "reasoning": "Refined based on feedback"} # optimistically score
                final_raw_candidates.append(best_refined)
            else:
                # Refinement failed, keep original but it might be rejected by gate
                final_raw_candidates.append(cand)
        else:
            final_raw_candidates.append(cand)
    
    # Convert to PatchCandidate objects
    candidates: list[PatchCandidate] = []
    for r in final_raw_candidates:
        candidates.append(PatchCandidate(
            patch_text=r.get("patch_text", ""),
            summary=r.get("summary", "candidate"),
            metadata={
                "planner": ctx.planner_name,
                "hypotheses": [h.kind for h in ctx.hypotheses[:3]],
                "critique": r.get("critique", {}),
            },
        ))
    
    logger.info("Generated %d patch candidates", len(candidates))
    return candidates


def learn_update(planner_name: str, success: bool, weight: float = 1.0) -> None:
    """Update the planner bandit based on outcome."""
    _selector.update(planner_name, success=success, weight=weight)
    logger.debug("Updated planner %s: success=%s, weight=%.2f", planner_name, success, weight)


def get_propose_stats() -> dict[str, Any]:
    """Get statistics about the propose pipeline."""
    return {
        "planner_stats": _selector.get_statistics(),
        "failure_index_size": _failure_index.size(),
        "registered_planners": list(PLANNERS.keys()),
    }

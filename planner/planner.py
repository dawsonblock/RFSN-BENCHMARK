"""Core planner implementation."""
from __future__ import annotations
from .spec import Plan, RepairStep
from typing import Dict, Any
import uuid


def generate_plan(task: Dict[str, Any], retrieved_memory: Dict[str, Any]) -> Plan:
    """
    Deterministic plan generator wrapper.
    
    LLM is allowed ONLY to fill content, not structure.
    The structure is defined by the spec and enforced by the gate.
    """
    failing_files = task.get("failing_files", [])
    if not failing_files:
        failing_files = task.get("files", ["unknown.py"])

    steps = [
        RepairStep(
            intent="identify failing logic",
            files=failing_files,
            hypothesis="logic mismatch with test expectations"
        ),
        RepairStep(
            intent="apply minimal fix",
            files=failing_files,
            hypothesis="boundary condition error"
        )
    ]

    # Use retrieval context to inform plan if available
    retrieval_hints = retrieved_memory.get("retrieval_hits", [])
    if retrieval_hints:
        # Add a step based on prior successful fixes
        steps.insert(1, RepairStep(
            intent="apply pattern from similar past fix",
            files=failing_files,
            hypothesis=f"similar to: {retrieval_hints[0].get('patch_summary', 'prior fix')[:100]}"
        ))

    return Plan(
        task_id=str(uuid.uuid4()),
        bug_summary=task.get("description", task.get("problem_statement", "unknown bug")),
        steps=steps,
        confidence=0.35,
        metadata={"source": "planner_v1", "retrieval_used": bool(retrieval_hints)}
    )

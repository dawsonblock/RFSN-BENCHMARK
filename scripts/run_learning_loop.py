from __future__ import annotations

import argparse
import json
import os
from typing import Any

# =============================================================================
# PERFORMANCE: Enable LLM response caching for repeated/similar prompts
# =============================================================================
os.environ.setdefault("RFSN_LLM_CACHE", "1")

from agent.llm_patcher import get_llm_patch_fn
from eval.swebench import load_tasks
from learning.outcomes import Outcome
from learning.swebench_learner import SWEBenchLearner, classify_bucket
from orchestrator.episode_runner import run_one_task


def write_report(path: str, summary: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    md_path = os.path.splitext(path)[0] + ".md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# RFSN Learning Summary\n\n")
        f.write("## Bucket rank\n\n")
        for row in summary.get("bucket_rank", []):
            f.write(f"- {row['bucket']}: mean={row['mean_reward']:.3f}, success={row['success']}/{row['n']}\n")
        f.write("\n## Template rank\n\n")
        for row in summary.get("template_rank", []):
            f.write(f"- {row['template']}: mean={row['mean_reward']:.3f}, success={row['success']}/{row['n']}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dataset", default="swebench_lite",
        choices=["swebench_lite", "swebench_verified", "swebench_full"]
    )
    ap.add_argument("--max_tasks", type=int, default=25)
    ap.add_argument("--model", default="deepseek", help="Model to use for patching")
    ap.add_argument("--workers", type=int, default=1)  # Serial by default
    ap.add_argument("--state_dir", default=".rfsn_state")
    args = ap.parse_args()

    learner = SWEBenchLearner(state_dir=args.state_dir)
    # failure_index is used by run_one_task internally, but we can verify it exists
    os.makedirs(args.state_dir, exist_ok=True)

    print(f"Loading tasks from {args.dataset}...")
    tasks = load_tasks(args.dataset, max_tasks=args.max_tasks)
    
    llm_patch_fn = get_llm_patch_fn(args.model)

    solved = 0
    attempted = 0

    for t in tasks:
        attempted += 1
        
        # Extract task details (handling SWEBenchTask object or dict)
        task_dict = t.to_dict() if hasattr(t, "to_dict") else t
        
        task_id = str(task_dict.get("task_id") or task_dict.get("instance_id") or f"task_{attempted}")
        repo = str(task_dict.get("repo") or task_dict.get("repo_name") or "unknown")
        _unused_test_output = str(task_dict.get("problem_statement") or "")
        initial_log = str(task_dict.get("fail_log") or "")
        bucket = classify_bucket(initial_log)

        # Pick strategy/template (upstream guidance)
        strategy = learner.choose_strategy()
        template = learner.strategy_to_template(strategy)

        # Pick planner
        planner_options = ["planner_v1"] 
        planner_name = learner.choose_planner(planner_options)

        # Inject upstream hints
        task_dict["_upstream"] = {
            "bucket": bucket,
            "strategy": strategy,
            "template": template,
            "planner": planner_name,
        }
        
        print(f"[{attempted}/{len(tasks)}] Task {task_id}: {bucket} -> {strategy} ({planner_name})")

        # Run episode
        # Construct repo URL
        repo_url = f"https://github.com/{repo}.git" if "github.com" not in repo else repo
        
        def make_record_callback(
            _task_id: str, _repo: str, _bucket: str, _planner_name: str, _strategy: str, _template: str
        ):
            def record_attempt(res):
                critique_score = 0.0
                if hasattr(res, "metadata") and "critique" in res.metadata:
                    critique_score = res.metadata["critique"].get("score", 0.0)

                outcome = Outcome(
                    passed=res.passed,
                    test_delta=getattr(res, "test_delta", 0),
                    runtime=getattr(res, "runtime", 0.0),
                    error_message=res.reason or "",
                    critique_score=critique_score
                )
                learner.record_episode(
                    task_id=_task_id,
                    repo=_repo,
                    bucket=_bucket,
                    planner=_planner_name,
                    strategy=_strategy,
                    template=_template,
                    outcome=outcome,
                    patch_size=getattr(res, "patch_size", 0),
                    files_touched=getattr(res, "files_touched", 0),
                    extra={"dataset": args.dataset, "gate_rejections": res.gate_rejections},
                )
            return record_attempt
        
        record_callback = make_record_callback(
            task_id, repo, bucket, planner_name, strategy, template
        )

        run_res = run_one_task(
            task=task_dict,
            repo_url=repo_url,
            llm_patch_fn=llm_patch_fn,
            max_attempts=6,
            record_callback=record_callback
        )
        
        status = "SOLVED" if run_res.passed else "FAILED"
        print(f"  Result: {status}")

        if run_res.passed:
            solved += 1

    summary = learner.summarize()
    summary["attempted"] = attempted
    summary["solved"] = solved
    summary["solve_rate"] = (solved / attempted) if attempted else 0.0

    report_path = os.path.join(args.state_dir, "reports", "learning_summary.json")
    write_report(report_path, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

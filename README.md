# RFSN Benchmark

[![Safety Kernel](https://img.shields.io/badge/Safety-RFSN%20Gate-green)](/)
[![SWE-bench](https://img.shields.io/badge/Benchmark-SWE--bench-blue)](https://swe-bench.github.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)

> **Safety-first autonomous code repair with upstream learning.**

RFSN Benchmark is a complete agent architecture for SWE-bench-class autonomous code repair. It combines a **deterministic safety kernel** (the gate) with **upstream intelligence modules** (planner, search, learning, retrieval) that never touch the gate.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        UPSTREAM INTELLIGENCE                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │   Planner    │  │    Search    │  │   Learning   │  │  Retrieval  │  │
│  │  (planning)  │  │    (beam)    │  │  (Thompson)  │  │  (memory)   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘  │
│         │                 │                 │                 │         │
│         └─────────────────┴────────┬────────┴─────────────────┘         │
│                                    │                                    │
│                          ┌─────────▼─────────┐                          │
│                          │   ORCHESTRATOR    │                          │
│                          │   (loop_v2.py)    │                          │
│                          └─────────┬─────────┘                          │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼  PROPOSALS ONLY
┌─────────────────────────────────────────────────────────────────────────┐
│                        DETERMINISTIC KERNEL                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  Plan Gate   │  │ Self-Critique│  │  Controller  │  │   Sandbox   │  │
│  │  (validate)  │──│   (rubric)   │──│   (serial)   │──│  (execute)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │
│                                                                         │
│  ✓ Command allowlist    ✓ Path restrictions    ✓ No shell injection    │
│  ✓ Deterministic        ✓ Fail-closed         ✓ Append-only logging    │
└─────────────────────────────────────────────────────────────────────────┘
```

## What This Repository Contains

### Deterministic Kernel (Gate)

- **`rfsn_controller/gates/`** — Plan validation, command filtering, policy enforcement
- **`rfsn_controller/gates/self_critique.py`** — 22-check pre-execution rubric
- **`cgw_ssl_guard/`** — Zero-trust execution sandbox

### Upstream Intelligence (Never Touches Gate)

- **`planner/`** — Multi-step repair planning with formal spec
- **`search/`** — Beam search over patch candidates
- **`learning/`** — Thompson sampling bandit for planner selection
- **`repair/`** — Bug taxonomy and failure classification
- **`skills/`** — Repo-specific prompt routing
- **`retrieval/`** — Failure index with embedding similarity
- **`orchestrator/`** — Full agent loop (the engine)
- **`memory/`** — Episode-level state persistence

### Benchmarking

- **`eval/`** — SWE-bench evaluation harness
- **`.github/workflows/`** — CI with learning persistence

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a single SWE-bench task
python -m eval.run --task-id "django__django-11099"

# Run with learning
python -c "
from orchestrator import run_episode_v2
from learning import Outcome

# Define your patch generator and executor
result = run_episode_v2(
    task={'repo': 'django/django', 'test_output': '...', 'failing_files': ['...']},
    patch_generator=your_patch_generator,
    executor=your_executor,
)
"
```

## Modules

### Planner (`planner/`)

Formal repair planning with structured output:

```python
from planner import generate_plan, Plan, RepairStep

plan = generate_plan(task, retrieval_context)
# Returns Plan with steps, confidence, metadata
```

### Search (`search/`)

Beam search for patch exploration:

```python
from search import BeamSearch, search_patches

candidates = search_patches(plan, patch_generator, width=3)
```

### Learning (`learning/`)

Thompson sampling for planner selection:

```python
from learning import ThompsonBandit, PlannerSelector

selector = PlannerSelector()
planner_name = selector.pick()  # Samples from posterior
selector.update(planner_name, success=True)
```

### Repair (`repair/`)

Bug taxonomy and failure classification:

```python
from repair import classify_failure, TAXONOMY

hypotheses = classify_failure(test_output, failing_files)
# Returns ranked RepairHypothesis objects
```

### Skills (`skills/`)

Repo-specific prompt routing:

```python
from skills import select_skill_heads, merge_skill_constraints

heads = select_skill_heads({'repo_fingerprint': 'django pandas'}, k=2)
constraints = merge_skill_constraints(heads)
```

### Retrieval (`retrieval/`)

Failure index with similarity search:

```python
from retrieval import FailureIndex, build_retrieval_context

index = FailureIndex()
context = build_retrieval_context(repo, test_output, index)
# Returns similar past failures for prompting
```

### Orchestrator (`orchestrator/`)

The full agent loop:

```python
from orchestrator import run_episode_v2

success = run_episode_v2(task, patch_generator, executor)
```

## Safety Invariants

The kernel enforces these **non-negotiable** invariants:

1. **Serial Authority** — Controller executes one step at a time
2. **Immutable Gating** — Gate cannot be bypassed or modified at runtime
3. **Deterministic Validation** — Same input → same gate decision
4. **Fail-Closed** — Any validation failure → reject
5. **Command Allowlist** — Only pre-approved operations execute
6. **Path Restrictions** — No access outside workspace
7. **Append-Only Logging** — Full audit trail

## Learning Persists Across Runs

The CI workflow saves learning state:

```yaml
- uses: actions/cache@v4
  with:
    path: .rfsn_state
    key: rfsn-learning-${{ github.ref_name }}
```

State includes:

- `.rfsn_state/failure_index.jsonl` — Past failures and fixes
- `.rfsn_state/memory.jsonl` — Episode-level state
- Bandit arm statistics (in-memory, checkpointed)

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `RFSN_BENCH_STRICT` | Enable strict mode (fail-fast) | `0` |
| `RFSN_LOG_LEVEL` | Logging verbosity | `INFO` |
| `RFSN_CACHE_DIR` | Cache directory | `.rfsn_cache` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `GEMINI_API_KEY` | Gemini API key | — |

## Tests

```bash
# All tests
pytest tests/ -v

# Self-critique tests
pytest tests/test_self_critique.py -v

# Learning module tests
pytest tests/ -k "bandit or thompson" -v
```

## Contributing

1. **Never modify the gate** — All intelligence is upstream
2. **Maintain determinism** — Gate decisions must be reproducible
3. **Add tests** — New modules need comprehensive tests
4. **Document invariants** — Safety properties must be explicit

## License

MIT

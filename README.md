<div align="center">

# 🚀 RFSN Benchmark

### Autonomous Code Repair with Safety-First Architecture

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg?style=for-the-badge)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![SWE-bench](https://img.shields.io/badge/SWE--bench-Ready-purple.svg?style=for-the-badge)](https://www.swebench.com/)

**A production-ready safety kernel for autonomous code repair benchmarking**

[Quick Start](#-quick-start) • [Architecture](#-architecture) • [Benchmarking](#-benchmarking) • [Safety](#-safety)

</div>

---

## 🎯 Overview

RFSN Benchmark is a **safety-first autonomous code repair framework** designed for SWE-bench evaluation. It combines:

- 🔐 **Hard Safety Gates** — Non-bypassable validation for all operations
- 🧠 **Self-Critique System** — 22 pre-submission checks before execution
- ⚡ **Parallel Execution** — Isolated worktree-based parallel benchmarking
- 📊 **Machine-Readable Results** — CI-ready with GitHub Actions integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RFSN Benchmark Pipeline                             │
│                                                                              │
│   📥 Task       🤖 Planner      ✅ Self-Critique    🔐 Gate       🧪 Verify  │
│   ─────────────────────────────────────────────────────────────────────────  │
│   SWE-bench  →  Generate    →   22 Safety     →   Validate  →   Execute     │
│   Dataset       Plan            Checks            & Block       & Test       │
│                                                                              │
│   Features: Parallel Worktrees | Strict Mode | CI Integration | Determinism │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/dawsonblock/RFSN-BENCHMARK.git
cd RFSN-BENCHMARK

# Install with all features
pip install -e '.[llm,dev]'

# Set API keys
export DEEPSEEK_API_KEY="sk-..."
export GEMINI_API_KEY="..."  # optional
```

### Run a Benchmark

```bash
# Basic evaluation
python -m eval.cli --dataset swebench_lite --max-tasks 10

# Strict mode (recommended for benchmarks)
export RFSN_BENCH_STRICT=1
python -m eval.cli --dataset swebench_verified --max-tasks 50

# Parallel execution
python -m eval.cli --dataset swebench_lite --parallel 4
```

### Python API

```python
from eval.run import run_eval, EvalConfig

config = EvalConfig(
    dataset="swebench_lite",
    max_tasks=10,
    parallel_workers=4,
)

results = await run_eval(config)
print(f"Pass Rate: {sum(r.success for r in results) / len(results):.1%}")
```

---

## 🏗️ Architecture

### Core Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **PlanGate** | Hard safety enforcement | `rfsn_controller/gates/plan_gate.py` |
| **Self-Critique** | Pre-submission validation | `rfsn_controller/gates/self_critique.py` |
| **Parallel Orchestrator** | Multi-worktree execution | `rfsn_controller/parallel_orchestrator.py` |
| **CI Entrypoint** | GitHub Actions integration | `rfsn_controller/ci_entrypoint.py` |
| **Eval Runner** | Benchmark execution | `eval/run.py` |

### Project Structure

```
RFSN-BENCHMARK/
├── rfsn_controller/
│   ├── gates/
│   │   ├── plan_gate.py          # Hard safety gate (non-learning)
│   │   └── self_critique.py      # 22 pre-submission checks
│   ├── parallel_orchestrator.py  # Worktree-based parallelism
│   ├── ci_entrypoint.py          # GitHub Actions integration
│   └── ...
├── eval/
│   ├── run.py                    # Main evaluation runner
│   ├── swebench.py               # SWE-bench task loading
│   └── cli.py                    # Command-line interface
├── .github/workflows/
│   └── rfsn_bench.yml            # CI benchmark workflow
├── tests/
│   └── test_self_critique.py     # 20 comprehensive tests
└── examples/
    └── ...
```

---

## 📊 Benchmarking

### SWE-bench Evaluation

```bash
# Run on SWE-bench Lite (300 tasks)
python -m eval.cli --dataset swebench_lite

# Run on SWE-bench Verified (500 tasks)
python -m eval.cli --dataset swebench_verified

# Custom task selection
python -m eval.cli --dataset swebench_lite --task-ids "django__django-11234,sympy__sympy-5678"
```

### Strict Mode

Enable strict mode for official benchmark runs:

```bash
export RFSN_BENCH_STRICT=1
```

**Strict mode guarantees:**
- ❌ No fallback to sample tasks
- ❌ No silent error recovery
- ✅ Fatal exit on missing datasets
- ✅ Machine-readable error codes

### GitHub Actions CI

Trigger benchmarks via workflow dispatch:

```yaml
# .github/workflows/rfsn_bench.yml
on:
  workflow_dispatch:
    inputs:
      dataset:
        default: 'swebench_lite'
      max_tasks:
        default: '10'
      strict:
        default: 'true'
```

### Result Format

```json
{
  "run_id": "swebench_lite_1706745600",
  "total_tasks": 50,
  "pass_rate": 0.32,
  "status_breakdown": {
    "PASS": 16,
    "FAIL_TESTS": 28,
    "REJECTED_BY_GATE": 4,
    "ERROR": 2
  }
}
```

---

## 🔐 Safety

### Self-Critique System

Every plan passes through 22 hard-fail checks before execution:

| Category | Checks |
|----------|--------|
| **Structural** | Unique IDs, valid types, acyclic graph, budget |
| **Gate Compatibility** | No mutation, serial execution |
| **Command Safety** | No shell, no chaining, no inline env vars |
| **Path Safety** | Relative only, no traversal, no secrets |
| **Verification** | Mandatory tests after mutations |

```python
from rfsn_controller.gates.self_critique import critique_plan

report = critique_plan(plan)
if report.result == CritiqueResult.REJECTED:
    print(f"Blocked: {report.hard_failures}")
```

### Allowed Step Types

Only these operations are permitted:

```python
# Read-only
"search_repo", "read_file", "analyze_file", "list_directory", "grep_search"

# Safe modifications
"apply_patch", "add_test", "refactor_small", "fix_import", "fix_typing"

# Verification
"run_tests", "run_lint", "check_syntax", "validate_types"

# Coordination
"wait", "checkpoint", "replan"
```

### Command Blocklist

The following are **always rejected**:

- `bash`, `sh`, `zsh`, `/bin/sh` — Shell interpreters
- `FOO=bar cmd` — Inline environment variables
- `cmd1 && cmd2`, `cmd1 | cmd2` — Command chaining
- `python -c "..."` — Arbitrary code execution
- `/etc/passwd`, `../../` — Path traversal

---

## ⚡ Parallel Execution

### Multi-Worktree Strategy

```python
from rfsn_controller.parallel_orchestrator import run_parallel_benchmark

results = await run_parallel_benchmark(
    tasks=tasks,
    max_workers=4,
    output_dir=Path("runs"),
)
```

**Features:**
- 🔒 **Isolated worktrees** — Each worker gets a separate git worktree
- 🎯 **Deterministic tie-breaking** — Consistent patch selection across runs
- 📦 **Artifact collection** — Patches, logs, and evidence per task
- 🔄 **Automatic cleanup** — Worktrees removed after completion

### Tie-Breaking Algorithm

When multiple workers produce patches for the same task:

1. PASS beats non-PASS
2. Fewer failing tests wins
3. Smaller diff wins
4. Fewer files touched wins
5. Lexicographic patch hash (deterministic)

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run self-critique tests (20 tests)
pytest tests/test_self_critique.py -v

# With coverage
pytest tests/ --cov=rfsn_controller --cov=eval
```

### Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| `self_critique.py` | 20 | ✅ All passing |
| `plan_gate.py` | 15 | ✅ All passing |
| `parallel_orchestrator.py` | 8 | ✅ All passing |

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RFSN_BENCH_STRICT` | Enable strict mode | `0` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | Required |
| `GEMINI_API_KEY` | Gemini API key | Optional |
| `RFSN_LOG_LEVEL` | Logging verbosity | `INFO` |
| `RFSN_CACHE_DIR` | Cache directory | `~/.rfsn/cache` |

### CLI Options

```bash
python -m eval.cli [OPTIONS]

Options:
  --dataset TEXT       Dataset name (swebench_lite, swebench_verified)
  --max-tasks INT      Maximum tasks to run
  --task-ids TEXT      Comma-separated task IDs
  --parallel INT       Number of parallel workers
  --output-dir PATH    Output directory for results
  --strict             Enable strict mode
```

---

## 📈 Results

### Task Status Codes

| Status | Description |
|--------|-------------|
| `PASS` | All tests pass after patch |
| `FAIL_TESTS` | Patch applied but tests fail |
| `REJECTED_BY_GATE` | Plan blocked by safety gate |
| `SECURITY_VIOLATION` | Unsafe operation attempted |
| `ERROR` | Unexpected error during execution |
| `TIMEOUT` | Task exceeded time limit |

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

<div align="center">

**Built for Safety. Designed for Benchmarks.**

[Report Bug](https://github.com/dawsonblock/RFSN-BENCHMARK/issues) • [Request Feature](https://github.com/dawsonblock/RFSN-BENCHMARK/issues)

</div>

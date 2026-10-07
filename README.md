# LockScope

[![Checks](https://github.com/brohum10/lockscope/actions/workflows/ci.yml/badge.svg)](https://github.com/brohum10/lockscope/actions/workflows/ci.yml)

**Explain a deadlock, not just that something is stuck.**

LockScope turns an exclusive-lock snapshot into a wait-for graph, finds cycles, emits the exact task → lock → owner witnesses, and separates cycle members from tasks blocked behind them. It runs entirely locally with the Python standard library. It never inspects or kills processes.

## Run

Python 3.11 or newer:

```sh
python3 lockscope.py examples/deadlock.json
python3 lockscope.py examples/deadlock.json --fail-on-cycle
python3 -m unittest discover -s tests -v
```

The example has `checkout` waiting for `refund`'s billing lock, `refund` waiting for `checkout`'s inventory lock, and `worker` blocked behind checkout. The report identifies the two-task cycle separately from the dependent worker.

Optional installation: `python3 -m pip install .` provides the `lockscope` command. Prefer a virtual environment for installation.

## Snapshot contract

```json
{
  "owners": {"lock-a": "task-a", "lock-b": "task-b"},
  "waits": {"task-a": "lock-b", "task-b": "lock-a"}
}
```

Each lock has exactly one owner. Each waiting task has exactly one blocking wait. IDs are nonblank, case-sensitive strings. Waited-on locks must have known owners. Duplicate JSON fields and unknown top-level fields fail closed with exit 2. Tasks owning locks but not waiting are terminal owners; they may still be doing useful work.

Exit status is 0 for a valid report, 1 when cycles exist with `--fail-on-cycle`, and 2 for invalid input or file errors. A cycle report is still printed with exit 1.

## Algorithm

1. Validate the complete snapshot before producing output.
2. Convert waits into directed edges from waiting task to lock owner.
3. Walk each unresolved path using a local position map. Re-entering the current path identifies a cycle; entering an already resolved path reuses its outcome.
4. Canonicalize cycle order by starting at its smallest task ID while preserving edge direction.
5. Group blocked dependents by reachable cycle and report noncyclic waits with their terminal owner.

Because every task has at most one outgoing edge, iterative functional-graph traversal avoids recursion and general-purpose graph dependencies. Core resolution is O(V + E). Sorting costs O(V log V); grouping dependents scans outcomes per cycle, adding O(V × number of cycles). Memory is O(V + E). No throughput claims are made.

## Interpretation and limits

This is a **single-instant, exclusive, single-owner, non-reentrant lock model**. Under this model and indefinite blocking, a directed cycle identifies circular waiting. A self-edge is reported as a one-task deadlock.

It does not model read/write lock modes, reentrant acquisitions, multiple interchangeable resources, timeouts, cancellation, distributed leases, fairness, lock-free algorithms, or concurrent changes during capture. A non-atomic snapshot can manufacture a false cycle. No cycle does not prove progress: starvation, I/O waits, and missing instrumentation remain possible. Terminal owners are not declared healthy.

This is an offline debugging utility, not a production deadlock monitor or recovery system. It proposes no victim to terminate and performs no automatic remediation. Reports retain IDs: sanitize snapshots before sharing.

## Verification

- 500 seeded random wait-for graphs checked against independent per-task reachability walks.
- Every reported cycle is checked for valid directed witness edges.
- Regression coverage for separate cycles, self-deadlock, dependent chains, terminal chains, malformed input, deterministic input reordering, and exit codes.
- A 10,000-edge chain checks that deep input does not require Python recursion.
- GitHub Actions tests Python 3.11 and 3.13 plus the installed CLI.

Future work: adapters for real lock dumps, more efficient grouping for many independent cycles, and separate models for shared locks and cancellable waits.

Built as a learning and portfolio project with AI assistance. MIT licensed.

"""Analyze exclusive single-owner lock snapshots; never terminate processes."""
import argparse
import json
from pathlib import Path


def analyze(data):
    if not isinstance(data, dict) or set(data) != {'owners', 'waits'}:
        raise ValueError('snapshot requires exactly owners and waits')
    owners, waits = data['owners'], data['waits']
    if not isinstance(owners, dict) or not isinstance(waits, dict):
        raise ValueError('owners and waits must be objects')
    def valid(value):
        return isinstance(value, str) and bool(value.strip())
    if any(not valid(k) or not valid(v) for k, v in owners.items()):
        raise ValueError('owners maps nonblank lock IDs to nonblank task IDs')
    if any(not valid(k) or not valid(v) for k, v in waits.items()):
        raise ValueError('waits maps each task to one nonblank lock ID')
    if any(lock not in owners for lock in waits.values()):
        raise ValueError('each waited-on lock must have a known owner')
    edges = {task: owners[lock] for task, lock in waits.items()}
    nodes = set(edges) | set(owners.values())
    # Every task has at most one outgoing edge. Resolve each path once.
    outcomes = {}
    cycles = {}
    for start in sorted(nodes):
        if start in outcomes:
            continue
        path, positions = [], {}
        current = start
        while current not in outcomes and current not in positions and current in edges:
            positions[current] = len(path)
            path.append(current)
            current = edges[current]
        if current in positions:
            members = path[positions[current]:]
            pivot = members.index(min(members))
            cycle = tuple(members[pivot:] + members[:pivot])
            cycles[cycle[0]] = cycle
            outcome = ('cycle', cycle[0])
        elif current in outcomes:
            outcome = outcomes[current]
        else:
            outcome = ('terminal', current)
            outcomes[current] = outcome
        for task in path:
            outcomes[task] = outcome
    reports = []
    for cycle_id, members in sorted(cycles.items()):
        member_set = set(members)
        reports.append({'id': cycle_id, 'tasks': list(members),
                        'witness': [{'task': task, 'waits_for': waits[task], 'owner': edges[task]} for task in members],
                        'blocked_dependents': sorted(t for t, outcome in outcomes.items()
                                                     if outcome == ('cycle', cycle_id) and t not in member_set)})
    return {'model': 'exclusive single-owner non-reentrant locks; one blocking wait per task',
            'task_count': len(nodes), 'wait_count': len(waits), 'cycles': reports,
            'noncyclic_waits': [{'task': t, 'terminal_owner': outcomes[t][1]}
                               for t in sorted(waits) if outcomes[t][0] == 'terminal']}


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field: ' + key)
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--fail-on-cycle', action='store_true', help='exit 1 when cycles exist')
    args = parser.parse_args(argv)
    try:
        report = analyze(json.loads(args.snapshot.read_text(encoding='utf-8'), object_pairs_hook=unique_fields))
    except (OSError, ValueError) as error:
        parser.exit(2, f'lockscope: {error}\n')
    print(json.dumps(report, indent=2))
    return int(args.fail_on_cycle and bool(report['cycles']))


if __name__ == '__main__':
    raise SystemExit(main())

import contextlib
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from lockscope import analyze, main


def snapshot(edges):
    return {'owners': {'lock:'+t:owner for t, owner in edges.items()},
            'waits': {t:'lock:'+t for t in edges}}


class Tests(unittest.TestCase):
    def test_cycle_and_dependents(self):
        r = analyze(snapshot({'a':'b','b':'a','c':'a','d':'c'}))
        self.assertEqual(r['cycles'][0]['tasks'], ['a','b'])
        self.assertEqual(r['cycles'][0]['blocked_dependents'], ['c','d'])

    def test_self_deadlock(self):
        self.assertEqual(analyze(snapshot({'a':'a'}))['cycles'][0]['tasks'], ['a'])

    def test_terminal_chain(self):
        r = analyze(snapshot({'a':'b','b':'c'}))
        self.assertEqual(r['cycles'], [])
        self.assertEqual(r['noncyclic_waits'], [{'task':'a','terminal_owner':'c'},{'task':'b','terminal_owner':'c'}])

    def test_separate_cycles(self):
        r = analyze(snapshot({'a':'b','b':'a','x':'y','y':'x'}))
        self.assertEqual(len(r['cycles']), 2)

    def test_order_independent(self):
        edges = {'c':'a','a':'b','b':'c','z':'a'}
        self.assertEqual(analyze(snapshot(edges)), analyze(snapshot(dict(reversed(list(edges.items()))))))

    def test_empty(self):
        self.assertEqual(analyze(snapshot({}))['task_count'], 0)

    def test_owners_without_wait(self):
        self.assertEqual(analyze({'owners':{'x':'a'},'waits':{}})['task_count'], 1)

    def test_deep_chain(self):
        r = analyze(snapshot({str(i):str(i+1) for i in range(10000)}))
        self.assertEqual(len(r['noncyclic_waits']), 10000)

    def test_invalid(self):
        for value in [None, {}, {'owners':[], 'waits':{}},
                      {'owners':{},'waits':{'a':'unknown'}},
                      {'owners':{'x':True},'waits':{}},
                      {'owners':{},'waits':{'': 'x'}}]:
            with self.assertRaises(ValueError): analyze(value)

    def test_seeded_reachability_oracle(self):
        rng = random.Random(92)
        for _ in range(500):
            nodes = [str(i) for i in range(12)]
            edges = {n:rng.choice(nodes) for n in nodes if rng.random()<.8}
            r = analyze(snapshot(edges))
            # Independent per-node walks classify reachable cycles, without shared outcomes.
            expected = set()
            for n in edges:
                seen = set()
                while n in edges and n not in seen:
                    seen.add(n)
                    n = edges[n]
                if n in seen:
                    expected.update(seen)
            actual = {t for c in r['cycles'] for t in c['tasks'] + c['blocked_dependents']}
            self.assertEqual(actual, expected)
            for c in r['cycles']:
                tasks = c['tasks']
                self.assertEqual(len(tasks), len(set(tasks)))
                for i, t in enumerate(tasks):
                    self.assertEqual(edges[t], tasks[(i+1)%len(tasks)])
                for witness in c['witness']:
                    self.assertEqual(edges[witness['task']], witness['owner'])

    def test_cli_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'input.json'
            path.write_text(json.dumps(snapshot({'a':'a'})))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(path)]), 0)
                self.assertEqual(main([str(path),'--fail-on-cycle']), 1)
            for text in ['{','{"owners":{},"owners":{},"waits":{}}']:
                path.write_text(text)
                with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as out:
                    with self.assertRaises(SystemExit) as e: main([str(path)])
                self.assertEqual(e.exception.code, 2)
                self.assertEqual(out.getvalue(), '')


if __name__ == '__main__': unittest.main()

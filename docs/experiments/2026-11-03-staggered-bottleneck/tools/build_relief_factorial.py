"""Split fixed F into two diagnostic factors; no new control condition."""
import ast
from dataclasses import asdict
import difflib
import hashlib
import json
from pathlib import Path
import random
import sys
import types


REPO = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parents[1]
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
E_PATH = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
F_PATH = REPO / "tmp/staggered_bottleneck/candidates/local_oneway_relief/native_rules.py"
E_SHA = "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
F_SHA = "f3a7acba6a812196d357cdccefb707ffec88df1e744d6f4dfc77ce26d916464d"
sha = lambda data: hashlib.sha256(data).hexdigest()
before = {p: p.read_bytes() for p in (E_PATH, F_PATH, REPO / NAME)}
assert sha(before[E_PATH]) == E_SHA and sha(before[F_PATH]) == F_SHA
e, f = before[E_PATH].decode(), before[F_PATH].decode()
marker = "    if preparing and ego.lane == 2:\n"
block = """    if preparing and mode == "transform" and ego.lane < 2:
        window = [c for c in (ego, *rows) if ego.x - 60.0 <= c.x <= ego.x + 30.0]
        pressure = sum(1 if c.lane in (1, 2) else -1 for c in window)
        if ego.lane == 1 and pressure >= 2 and _clear(ego, rows, 0):
            memory = Memory(lane_target=0, joining=True)
            speed, target, memory = _join_speed(ego, rows, memory, 0)
            return action(speed, 0, "local_relief", target), memory
        reason = "join_follow" if memory.joining else "formation_follow"
        return action(speed, None, reason, target, reference), memory

"""
stop = """        reason = "join_follow" if memory.joining else "formation_follow"
        return action(speed, None, reason, target, reference), memory
"""
assert e.count(marker) == 1 and e.replace(marker, block + marker) == f
blocks = {"F_B": block.splitlines(True)[0] + stop + "\n", "F_R": block.replace(stop, "")}


def module(name, source):
    result = types.ModuleType(name)
    sys.modules[name] = result
    exec(compile(source, name + "/native_rules.py", "exec"), result.__dict__)
    return result


baseline = module("factorial_e", e)
sources = {name: e.replace(marker, inserted + marker) for name, inserted in blocks.items()}
modules = {name: module(name, source) for name, source in sources.items()}
for name, source in sources.items():
    assert source.count(blocks[name]) == 1 and source.replace(blocks[name], "") == e
    original_ast, current_ast = ast.parse(e), ast.parse(source)
    original_nodes = {getattr(n, "name", str(i)): ast.dump(n) for i, n in enumerate(original_ast.body)}
    current_nodes = {getattr(n, "name", str(i)): ast.dump(n) for i, n in enumerate(current_ast.body)}
    assert original_nodes.keys() == current_nodes.keys()
    assert [k for k in original_nodes if original_nodes[k] != current_nodes[k]] == ["_decide"]

rng = random.Random(202611033)
equivalence = 0
for mode, area in (("noa", "any"), ("formation", "any"), ("transform", "before"),
                   ("transform", "after"), ("transform", "straight")):
    for _ in range(200):
        x = rng.uniform(200, 620) if area == "before" else rng.uniform(1020, 1150) if area == "after" else rng.uniform(200, 1150)
        lane = rng.randrange(2 if area == "after" else 3)
        states = [dict(track=0, x=x, y=(lane + .5) * 3.3, speed=rng.uniform(0, 33.3), lane=lane)]
        for i in range(1, 9):
            peer_lane = rng.randrange(3)
            states.append(dict(track=i, x=x + rng.uniform(-130, 230), y=(peer_lane + .5) * 3.3,
                               speed=rng.uniform(0, 33.3), lane=peer_lane))
        memory = dict(lane_target=rng.choice([None, 0, 1, 2]),
                      gap=rng.choice([None, (1, 2), (None, 3)]), joining=rng.choice([False, True]))
        drop = None if area == "straight" else 1000.0
        cars = [baseline.Vehicle(**v) for v in states]
        expected = baseline.decide(cars[0], cars[1:], baseline.Memory(**memory), mode, drop)
        for candidate in modules.values():
            cars = [candidate.Vehicle(**v) for v in states]
            actual = candidate.decide(cars[0], cars[1:], candidate.Memory(**memory), mode, drop)
            assert tuple(map(asdict, actual)) == tuple(map(asdict, expected))
            equivalence += 1

for name, candidate in modules.items():
    car = lambda key, x, lane: candidate.Vehicle(key, x, (lane + .5) * 3.3, 28.8, lane)
    left = car(0, 700, 0)
    rows = tuple(car(i + 1, x, 0) for i, x in enumerate((640, 655, 670, 685, 715)))
    command, _ = candidate.decide(left, rows, candidate.Memory(), "transform")
    assert command.lane == (None if name == "F_B" else 1)
    middle, incoming = car(0, 700, 1), car(1, 715, 2)
    command, _ = candidate.decide(middle, (incoming,), candidate.Memory(), "transform")
    assert command.lane == (None if name == "F_B" else 0)

for name, source in sources.items():
    target = REPO / f"tmp/staggered_bottleneck/candidates/{name}/native_rules.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8", newline="\n")
    evidence = DOC / "ablations" / name
    evidence.mkdir(parents=True, exist_ok=True)
    patch = "".join(difflib.unified_diff(e.splitlines(True), source.splitlines(True),
                                        fromfile="E/" + NAME, tofile=name + "/" + NAME))
    (evidence / "native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
    metadata = dict(candidate=name, parent_e_sha256=E_SHA, parent_f_sha256=F_SHA,
                    source_sha256=sha(source.encode()), rules_path=str(target),
                    lines=len(source.splitlines()), changed_functions=["_decide"],
                    reverse_to_e_exact=True, unaffected_command_memory_comparisons=equivalence // 2,
                    policy_contracts=2, production_e_f_unchanged=True)
    (evidence / "source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata))
assert all(path.read_bytes() == data for path, data in before.items())

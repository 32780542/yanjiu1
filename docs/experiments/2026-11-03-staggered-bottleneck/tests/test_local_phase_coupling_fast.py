"""Save J2's oracle before refactoring; compare full results by float.hex."""
import argparse
from dataclasses import asdict
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "tmp/staggered_bottleneck"
ORIGINAL = BASE / "candidates/local_phase_coupling_physical/native_rules.py"
OLD_SHA = "895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689"
ORACLE = BASE / "J2fast_oracle_20261103"
MODES = ("noa", "formation", "transform")
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def load(path):
    spec = importlib.util.spec_from_file_location("oracle_rules_" + digest(path)[:12], path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def exact(value):
    if isinstance(value, float):
        assert math.isfinite(value)
        return {"float_hex": value.hex()}
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(v) for v in value]
    return value


def outputs(rules, state):
    cars = [rules.Vehicle(**c) for c in state["cars"]]
    assert len({c.track for c in cars}) == len(cars)
    assert all(c.lane in (0, 1, 2) and 0 <= c.speed <= rules.MAX_SPEED for c in cars)
    assert all(math.isfinite(float(v)) for c in cars for v in asdict(c).values() if v is not None)
    memory = dict(state["memory"])
    if memory["gap"] is not None:
        memory["gap"] = tuple(memory["gap"])
    decisions = {mode: [asdict(v) for v in rules.decide(cars[0], cars[1:], rules.Memory(**memory), mode,
                                                       state["drop_x"])] for mode in MODES}
    return exact(dict(decisions=decisions, safe_speed=rules.safe_speed(cars[0], cars[1:])))


def vehicle(track, x, lane, speed=28.8, **kw):
    return dict(track=track, x=x, y=(lane + .5) * 3.3, speed=speed, lane=lane, **kw)


def recorded():
    trace = BASE / "diagnostic2500_20261103/transform/20261103T031406911129Z_lane_drop_transform_s1_5390a4/diagnostic.jsonl.gz"
    targets = iter((100, 180, 250))
    target = next(targets)
    with gzip.open(trace, "rt", encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            if frame["time_s"] < target:
                continue
            cars = [dict(track=i, **s) for i, s in enumerate(frame["states"].values())]
            for ego in cars:
                rows = [c for c in cars if c is not ego and -100 <= c["x"]-ego["x"] <= 200]
                yield dict(kind="recorded_" + str(target), cars=[ego, *rows],
                           memory=dict(lane_target=None, gap=None, joining=False), drop_x=1000.)
            target = next(targets, None)
            if target is None:
                break


def generated(index):
    rng = random.Random(202611030000 + index)
    x = rng.choice((639.999, 640., 640.001, 999.999, 1000., 1000.001, rng.uniform(100, 1400)))
    lane = rng.randrange(3)
    cars = [vehicle(0, x, lane, rng.uniform(0, 33.3), vy=rng.choice((0., -3.3, 3.3)),
                    acceleration=rng.uniform(-10, 5), time=index * .1)]
    if index % 4 == 0:
        cars[0]["y"] = rng.uniform(.9, 9.)
    offsets = rng.sample([7.5 * i for i in range(-14, 29) if i], rng.randrange(0, 31))
    for i, offset in enumerate(offsets, 1):
        c = vehicle(10000 - i * 7, x + offset + rng.uniform(-.3, .3), rng.randrange(3),
                    rng.uniform(0, 33.3), vy=rng.choice((0., 0., -3.3, 3.3)),
                    acceleration=rng.uniform(-10, 5), time=index * .1)
        if i % 5 == 0:
            c["y"] = rng.uniform(.9, 9.)
        cars.append(c)
    # Fixed exact boundaries and same-x peers are separate valid cross-lane cases.
    if index % 23 == 0:
        cars = [vehicle(0, x, lane), vehicle(7, x, (lane + 1) % 3)]
    elif index % 29 == 0:
        dx = (-200., -5.5, 0., 200., 200.001)[index % 5]
        cars = [vehicle(0, x, lane, 33.3), vehicle(7, x + dx, (lane + 1) % 3 if dx == 0 else lane, 0.)]
    if index % 2:
        cars[1:] = reversed(cars[1:])
    tracks = [c["track"] for c in cars[1:]]
    gap = None if len(tracks) < 2 or rng.randrange(2) else tuple(rng.sample(tracks, 2))
    return dict(kind="random_finite", cars=cars,
                memory=dict(lane_target=rng.choice((None, None, 0, 1, 2)), gap=gap,
                            joining=bool(rng.randrange(2))), drop_x=rng.choice((None, 1000.)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--rules", type=Path)
    parser.add_argument("--sha")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    assert digest(ORIGINAL) == OLD_SHA
    if args.record:
        assert not ORACLE.exists() and args.count == 10000
        ORACLE.mkdir()
        rules = load(ORIGINAL)
        states = recorded()
        with gzip.open(ORACLE / "oracle.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as stream:
            for index in range(args.count):
                state = next(states, None)
                if state is None:
                    state = generated(index)
                stream.write(json.dumps(dict(index=index, state=state, expected=outputs(rules, state)),
                                        separators=(",", ":")) + "\n")
        metadata = dict(source_sha256=OLD_SHA, cases=args.count, modes=MODES, float_comparison="float.hex",
                        oracle_sha256=digest(ORACLE / "oracle.jsonl.gz"), saved_before_fast_source=True)
        assert not (BASE / "candidates/local_phase_coupling_fast/native_rules.py").exists()
        (ORACLE / "source.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps(metadata))
        return
    assert args.rules and args.sha and args.report and not args.report.exists()
    assert digest(args.rules) == args.sha
    metadata = json.loads((ORACLE / "source.json").read_text())
    assert digest(ORACLE / "oracle.jsonl.gz") == metadata["oracle_sha256"]
    rules, checked = load(args.rules), 0
    with gzip.open(ORACLE / "oracle.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if not args.start <= row["index"] < args.start + args.count:
                continue
            actual = outputs(rules, row["state"])
            assert actual == row["expected"], (row["index"], row["state"], row["expected"], actual)
            checked += 1
    assert checked == args.count
    result = dict(checked=checked, start=args.start, decisions=checked * 3, safe_speeds=checked,
                  source_sha256=args.sha, original_sha256=OLD_SHA, full_command_memory_float_hex_exact=True,
                  oracle_sha256=metadata["oracle_sha256"])
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

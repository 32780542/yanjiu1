"""Independent tail-lane optimization and cross-check against the frozen selector."""
import argparse
import ast
from collections import Counter
from functools import lru_cache
from itertools import combinations, combinations_with_replacement, permutations, product
from math import comb
from pathlib import Path
import random
import statistics
import sys
from time import perf_counter


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / "tmp/nov25study/selected_demo/source"


def solve_tail(source, lanes, phase, omitted, strict):
    """Return (selected extra lanes, min max shift, min total shift).

    The frozen function returns the first extra tuple when no legal profile
    exists. We preserve that result and expose its missing costs as None.
    """
    if lanes < 1:
        raise ValueError("At least one target lane is required")
    xs = sorted(source)
    n = len(xs)
    layers, tail = divmod(n + len(omitted), lanes)
    missing = Counter(omitted)
    invalid = (tuple(range(tail)), None, None)
    if any(not 0 <= j < lanes or count > layers + 1 for j, count in missing.items()):
        return invalid
    forced = [missing[j] > layers for j in range(lanes)]
    spare = tail - sum(forced)
    if spare < 0:
        return invalid
    favored = [j % 2 == phase for j in range(lanes)]
    choices = []
    free_favored = sum(wanted and not must for wanted, must in zip(favored, forced))
    for j in range(lanes):
        if forced[j] or (strict and favored[j] and spare >= free_favored):
            choices.append((1,))
        elif strict and not favored[j] and spare <= free_favored:
            choices.append((0,))
        else:
            choices.append((0, 1))

    # The target prefix through k is base[k] + number of selected extras.
    base = []
    cumulative = 0
    for k in range(lanes):
        cumulative += layers - missing[k]
        base.append(cumulative)

    def cut_radius(k, q):
        left = xs[q - 1] - k if q else 0
        right = k + 1 - xs[q] if q < n else 0
        return max(0, left, right)

    # The implicit cut k=-1 catches sources far below the first target lane.
    best = [None] * (tail + 1)
    best[0] = max(0, -xs[0]) if n else 0
    for k, bits in enumerate(choices):
        after = [None] * (tail + 1)
        for selected, previous in enumerate(best):
            if previous is None:
                continue
            for take in bits:
                s = selected + take
                if s > tail or s + lanes - k - 1 < tail:
                    continue
                q = base[k] + s
                if 0 <= q <= n:
                    radius = max(previous, cut_radius(k, q))
                    if after[s] is None or radius < after[s]:
                        after[s] = radius
        best = after
    radius = best[tail]
    if radius is None:
        return invalid

    # Once the radius is fixed, use exact integer cut costs. Work backwards:
    # a tied take at the earliest undecided lane wins lexicographically.
    suffix = [None] * (tail + 1)
    suffix[tail] = (0, 0)
    decisions = [bytearray(tail + 1) for _ in range(lanes)]
    source_prefix = n
    for k in reversed(range(lanes)):
        before = [None] * (tail + 1)
        while source_prefix and xs[source_prefix - 1] > k:
            source_prefix -= 1
        for selected in range(max(0, tail - (lanes - k)), min(k, tail) + 1):
            for take in choices[k]:
                s = selected + take
                if s > tail or suffix[s] is None:
                    continue
                q = base[k] + s
                if not 0 <= q <= n or cut_radius(k, q) > radius:
                    continue
                cost = abs(source_prefix - q) if k < lanes - 1 else 0
                value = (suffix[s][0] + cost, suffix[s][1] - take * favored[k])
                if before[selected] is None or value < before[selected] or (value == before[selected] and take):
                    before[selected] = value
                    decisions[k][selected] = take
        suffix = before
    exterior = sum(max(0, -x) + max(0, x - (lanes - 1)) for x in xs)
    selected = []
    for k, decisions_for_lane in enumerate(decisions):
        if decisions_for_lane[len(selected)]:
            selected.append(k)
    return tuple(selected), radius, suffix[0][0] + exterior


def frozen_selector():
    sys.path.insert(0, str(FROZEN))
    from noa import staggered
    assert Path(staggered.__file__).resolve() == FROZEN / "noa/staggered.py"
    paths = (FROZEN, ROOT / "variants/phase5g_pure_formation")
    trees = [ast.parse((path / "noa/staggered.py").read_bytes()) for path in paths]
    body = [next(node for node in tree.body if getattr(node, "name", "") == "_tail_lanes") for tree in trees]
    assert ast.dump(body[0]) == ast.dump(body[1])
    return staggered._tail_lanes


@lru_cache(maxsize=32768)
def permutation_cost(source, targets):
    """Brute force all vehicle-to-slot permutations, independent of the sorted-pair theorem."""
    best = (float("inf"), float("inf"))
    for p in permutations(targets):
        hops = [abs(x - y) for x, y in zip(source, p)]
        best = min(best, (max(hops, default=0), sum(hops)))
    return best


def permutation_oracle(source, lanes, phase, omitted, strict):
    layers, tail = divmod(len(source) + len(omitted), lanes)
    best = None
    for extra in combinations(range(lanes), tail):
        target = [j for j in range(lanes) for _ in range(layers + (j in extra))]
        try:
            for j in omitted:
                target.remove(j)
        except ValueError:
            continue
        pref = sum(j % 2 == phase for j in extra)
        key = (-(pref if strict else 0), *permutation_cost(source, tuple(target)), -pref, extra)
        if best is None or key < best:
            best = key
    if best is None:
        return tuple(range(tail)), None, None
    return best[-1], best[1], best[2]


def verify():
    original = frozen_selector().__wrapped__
    assert original((1,), 3, 0, (), True) == (0,)
    assert original((1,), 3, 0, (), False) == (1,)
    total = clipped = overflow = 0
    for lanes in range(1, 6):
        max_n = 4 if lanes <= 4 else 3
        omissions = [v for r in range(lanes + 1) for v in combinations(range(lanes), r)]
        for n in range(max_n + 1):
            for source in combinations_with_replacement(range(-1, lanes + 2), n):
                for phase, strict, omitted in product((0, 1), (False, True), omissions):
                    args = (source, lanes, phase, omitted, strict)
                    got = solve_tail(*args)
                    expected = permutation_oracle(*args)
                    assert got == expected, (args, got, expected)
                    assert got[0] == original(*args), args
                    total += 1
                    clipped += bool(omitted)
                    overflow += bool(source and source[-1] >= lanes)
    rng = random.Random(111705)
    random_count = invalid = 0
    for lanes in range(1, 13):
        for _ in range(100):
            n = rng.randrange(0, 4 * lanes + 1)
            source = tuple(rng.choices(range(-2, lanes + 5), k=n))
            omitted = tuple(rng.choices(range(-1, lanes + 1), k=rng.randrange(lanes + 1)))
            args = (source, lanes, rng.randrange(2), omitted, rng.choice((False, True)))
            extra, radius, _ = solve_tail(*args)
            assert extra == original(*args), args
            random_count += 1
            invalid += radius is None
    print(f"All {total} exhaustive three-way comparisons agree "
          f"({clipped} cropped, {overflow} with sources above the last lane).")
    print(f"All {random_count} random comparisons agree, including {invalid} wholly invalid omission sets.")


def benchmark():
    original = frozen_selector().__wrapped__
    rng = random.Random(250112)
    print("K,n,r,profiles,DP_us,enumeration_us")
    for lanes in (2, 3, 4, 6, 8, 12, 16, 18, 20, 32, 64, 128, 256, 512):
        tail = lanes // 2
        n = 2 * lanes + tail
        values = range(lanes + 3)
        cases = [(tuple(sorted(rng.choices(values, k=n))), lanes, 0, (), lanes == 3) for _ in range(3)]
        def measure(fn, repeats):
            observations = []
            for args in cases:
                start = perf_counter()
                for _ in range(repeats):
                    fn(*args)
                observations.append((perf_counter() - start) * 1e6 / repeats)
            return statistics.median(observations)
        dp_us = measure(solve_tail, max(1, 2000 // (lanes * lanes)))
        enum_us = ""
        if lanes <= 20:
            for args in cases:
                assert original(*args) == solve_tail(*args)[0]
            enum_us = f"{measure(original, max(1, 250 // comb(lanes, tail))):.2f}"
        print(f"{lanes},{n},{tail},{comb(lanes, tail)},{dp_us:.2f},{enum_us}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    options = parser.parse_args()
    if not options.bench_only:
        verify()
    if not options.verify_only:
        benchmark()

"""Assign the fewest previously observed movers when some repetition is unavoidable."""
import argparse
from pathlib import Path
from receiving_contact_trial import build


def create(folder):
    build(folder, "hold")
    path = folder / "noa/transport.py"
    source = path.read_text(encoding="utf8")
    start = source.index("    blocked =", source.index("def _one_hop_mask"))
    end = source.index("def _integer_positions", start)
    source = source[:start] + '''    population, goals = Counter(source), Counter(target)
    available = Counter(lane for lane, used in zip(source, moved) if not used)
    departures = {}
    flow = 0
    for lane in sorted(population.keys() | goals.keys()):
        right = flow + population[lane] - goals[lane]
        departures[lane] = max(0, -flow) + max(0, right)
        flow = right
    result = []
    for origin, used, row in zip(source, moved, ordinary):
        fresh_suffices = departures[origin] <= available[origin]
        if used and fresh_suffices:
            result.append([blocked or destination != origin for blocked, destination in zip(row, target)])
        elif not used and not fresh_suffices:
            result.append([blocked or destination == origin for blocked, destination in zip(row, target)])
        else:
            result.append(row)
    return result


''' + source[end:]
    path.write_text(source, encoding="utf8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    create(parser.parse_args().folder)

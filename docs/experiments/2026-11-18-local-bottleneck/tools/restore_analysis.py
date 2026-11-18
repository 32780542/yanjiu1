"""Restore the original analysis files used to verify a sealed experiment."""

from argparse import ArgumentParser
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[4]
PIN = "fba326b023871a354d2577bfe7ecb90ccd8e68db"
EXPERIMENTS = "docs/experiments"
VARIANT = "variants/phase5g_pure_formation"
FILES = (
    f"{EXPERIMENTS}/2026-11-04-timegap-staggered/tools/report_trial.py",
    *(f"{EXPERIMENTS}/2026-11-03-staggered-bottleneck/tools/{name}.py"
      for name in ("runner", "seal_case", "summarize")),
    f"{EXPERIMENTS}/2026-10-30-rule-trials/analysis/bottleneck_trials.py",
    f"{EXPERIMENTS}/2026-10-30-rule-trials/evidence/compact_evidence.py",
    *(f"{VARIANT}/{name}" for name in (
        "experiments/native_sumo.py",
        "experiments/native_comparison.py",
        "experiments/bottleneck_attribution.py",
        "experiments/complete_layers.py",
        "experiments/__init__.py",
        "research/__init__.py",
        "research/common.py",
    )),
)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="New folder for the 13 frozen analysis files")
    parser.add_argument("--revision", default=PIN, help="Git commit recorded for the analysis files")
    args = parser.parse_args()
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", args.revision + "^{commit}"], cwd=REPO, text=True
    ).strip()
    directory = args.directory.resolve()
    directory.mkdir(parents=True)
    for relative in FILES:
        data = subprocess.check_output(["git", "show", f"{revision}:{relative}"], cwd=REPO)
        destination = directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    print(directory / FILES[0])


if __name__ == "__main__":
    main()

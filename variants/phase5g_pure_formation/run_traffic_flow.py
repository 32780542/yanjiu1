"""连续大交通流的54例配对实验。"""

import argparse
from experiments.traffic_flow import run_study


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    run_study(workers=args.workers)

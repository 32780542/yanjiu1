"""运行预先固定的 65 例随机车流编队验证。"""

import argparse
from experiments.formation_study import run_study


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    arguments = parser.parse_args()
    run_study(workers=arguments.workers)

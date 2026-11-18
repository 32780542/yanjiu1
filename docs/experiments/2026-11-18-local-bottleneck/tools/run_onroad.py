"""用相同来车分别运行三种控制，可另外复跑 MATLAB 原环境的普通 HDV。"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
import subprocess
import sys

VARIANT = Path(__file__).resolve().parents[4] / "variants/phase5g_pure_formation"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="新批次目录")
    parser.add_argument("--matlab-data", type=Path)
    parser.add_argument("--legacy-sumo-home", type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--road-limit", type=float, choices=(28.8, 33.3), default=33.3)
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument("--original-hdv", action="store_true", help="复跑旧版车型对照")
    profiles.add_argument("--matched-tau", action="store_true", help="复跑共同底层 IDM 时距的对照")
    args = parser.parse_args()
    if bool(args.matlab_data) != bool(args.legacy_sumo_home):
        parser.error("原环境复跑需要同时提供 --matlab-data 和 --legacy-sumo-home")
    base = args.directory.resolve()
    base.mkdir(parents=True, exist_ok=False)
    modes = ["transform", "noa", "hdv"]
    if args.matlab_data:
        modes.append("hdv_matlab")

    def run(case):
        flow, seed, mode = case
        folder = base / f"{mode}_f{flow}_s{seed}"
        folder.mkdir()
        if mode in ("transform", "noa"):
            cmd = [VARIANT / "run_native_flow.py", "--mode", mode, "--scenario", "lane_drop",
                   "--flow", str(flow), "--seed", str(seed), "--output-base", folder]
        else:
            cmd = [VARIANT / "run_cai_hdv.py", "--flows", str(flow), "--seeds", str(seed),
                   "--output", folder]
            if mode == "hdv_matlab":
                cmd += ["--matlab-data", args.matlab_data, "--sumo-home", args.legacy_sumo_home]
            elif args.original_hdv:
                cmd.append("--original-hdv")
            elif args.matched_tau:
                cmd.append("--matched-tau")
        if mode != "hdv_matlab":
            cmd += ["--road-limit", str(args.road_limit)]
        with (folder / "run.log").open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-X", "utf8", "-B", *cmd, "--duration", "600",
                            "--max-time", "1800"], stdout=log, stderr=subprocess.STDOUT, check=True)
        print(folder.name, flush=True)

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(run, product((2000, 1750, 1500), range(311, 316), modes)))


if __name__ == "__main__":
    main()

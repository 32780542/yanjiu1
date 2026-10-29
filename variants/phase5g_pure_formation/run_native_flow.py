"""Command line for real SUMO traffic and paired four-mode experiments."""

import argparse
import json
from pathlib import Path

from experiments.native_sumo import MODES, SCENARIOS, run_case


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="transform")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--flow", type=float, default=1250.0)
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--scenario", choices=SCENARIOS, default="lane_drop")
    parser.add_argument("--output-base", type=Path)
    parser.add_argument("--max-time", type=float)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument(
        "--initial", type=Path, help="JSON array of {depart,lane,x,speed,id?}; overrides demand"
    )
    parser.add_argument("--diagnostic", action="store_true", help="also save 0.1 s state and action trace")
    parser.add_argument("--matrix", action="store_true", help="all four modes, paired seeds and scenarios")
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3, 4, 5])
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=["lane_drop"])
    args = parser.parse_args(argv)
    initial = json.loads(args.initial.read_text(encoding="utf-8-sig")) if args.initial else None
    cases = (
        [(mode, seed, scenario) for scenario in args.scenarios for seed in args.seeds for mode in MODES]
        if args.matrix
        else [(args.mode, args.seed, args.scenario)]
    )
    for mode, seed, scenario in cases:
        directory = run_case(
            mode=mode,
            seed=seed,
            flow=args.flow,
            duration=args.duration,
            scenario=scenario,
            output_base=args.output_base,
            gui=args.gui,
            initial=initial,
            max_time=args.max_time,
            diagnostic=args.diagnostic,
        )
        result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        print(
            json.dumps(
                dict(
                    run_dir=str(directory),
                    mode=mode,
                    seed=seed,
                    scenario=scenario,
                    status=result["status"],
                    requested=result["requested"],
                    departed=result["departed"],
                    completed=result["completed"],
                    pending=result["pending_final"],
                    onroad=result["onroad_final"],
                    collisions=result["collisions"],
                    teleports=result["teleports"],
                    mean_travel_time_s=result["mean_travel_time_s"],
                    formation_state=result["formation_state"],
                ),
                ensure_ascii=True,
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

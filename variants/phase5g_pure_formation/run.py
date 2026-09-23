"""Isolated project entry point. Use python -I -B -S run.py COMMAND."""
from pathlib import Path
import os
import sys
import sysconfig

ROOT = Path(__file__).resolve().parent
if not sys.flags.isolated or not sys.dont_write_bytecode or not sys.flags.no_site:
    raise SystemExit('Required invocation: python -I -B -S run.py <command> (no .pth processing)')
sys.path.insert(0, str(ROOT))
# Add installed tool packages WITHOUT running site/.pth editable-path hooks.
sys.path.append(sysconfig.get_path('purelib'))
# MCP's Windows transport needs these declared pywin32 paths, without .pth hooks.
site_packages = Path(sysconfig.get_path('purelib'))
sys.path.extend(str(site_packages / p) for p in ('win32', 'win32/lib'))
DLL_HANDLES = [os.add_dll_directory(str(site_packages / 'pywin32_system32'))]
os.chdir(ROOT)
SCRATCH_ROOT = ROOT.parents[1] / 'tmp'
for key in ('TEMP', 'TMP', 'TMPDIR', 'MPLCONFIGDIR', 'XDG_CACHE_HOME'):
    os.environ[key] = str(SCRATCH_ROOT)
SCRATCH_ROOT.mkdir(exist_ok=True)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'


def main():
    import argparse
    import math
    import re

    def positive_finite(value):
        try:
            number = float(value)
        except (OverflowError, TypeError, ValueError) as error:
            raise argparse.ArgumentTypeError('must be a finite number') from error
        if not math.isfinite(number) or number <= 0:
            raise argparse.ArgumentTypeError('must be a positive finite number')
        return number

    def uint64(value):
        try:
            number = int(value, 10)
        except (TypeError, ValueError) as error:
            raise argparse.ArgumentTypeError('must be an exact uint64 integer') from error
        if str(number) != value.strip() or not 0 <= number < 2**64:
            raise argparse.ArgumentTypeError('must be an exact uint64 integer')
        return number

    def demo_vehicle_count(value):
        try:
            number = int(value, 10)
        except (TypeError, ValueError) as error:
            raise argparse.ArgumentTypeError('must be an integer from 3 to 60') from error
        if str(number) != value.strip() or not 3 <= number <= 60:
            raise argparse.ArgumentTypeError('must be an integer from 3 to 60')
        return number

    def sha256_hex(value):
        if not re.fullmatch(r'[0-9a-fA-F]{64}', value):
            raise argparse.ArgumentTypeError('must be an exact 64-digit SHA-256 hex digest')
        return value.lower()

    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['registry', 'build', 'verify', 'test', 'environment', 'mcp', 'smoke', 'screenshot', 'phase2', 'phase2-replay', 'phase3', 'phase3-replay', 'phase4', 'phase4-replay', 'phase5', 'phase5-replay', 'phase5-r5', 'phase5-r5-replay', 'phase5g', 'phase5g-replay', 'phase5g-formal', 'phase5g-demo', 'phase5g-simple-matrix'])
    parser.add_argument('--run-dir', help='Replay an existing phase2/phase3 run directory inside keyan1')
    parser.add_argument('--case', action='append', dest='case_names', help='Phase5 explicit development case selection')
    parser.add_argument('--offline', action='store_true', help='Phase5 diagnostic only, no SUMO verification')
    parser.add_argument('--no-sampling', action='store_true', help='Phase5 partial development run')
    parser.add_argument('--case-file', help='Explicit previously frozen R5 private/physical initial case JSON')
    parser.add_argument('--waiting-policy', choices=('fixed','minimax','stackelberg'), default='fixed',
                        help='R5 local longitudinal waiting policy, subject to the unchanged guard')
    parser.add_argument('--lane-change-policy', choices=('fixed','adaptive_duration'), default='fixed',
                        help='Phase5F finite measured-speed duration policy; guard remains unchanged')
    parser.add_argument('--vehicle-count', type=demo_vehicle_count, default=12,
                        help='Phase5G demo controlled vehicle count')
    parser.add_argument('--seed', type=uint64, default=1,
                        help='Phase5G demo exact uint64 seed')
    parser.add_argument('--target-speed-mps', type=positive_finite, default=10.0,
                        help='Phase5G demo target speed')
    parser.add_argument('--duration-s', type=positive_finite, default=90.0,
                        help='Phase5G demo duration')
    parser.add_argument('--depart-interval-min-s', type=positive_finite, default=2.5,
                        help='Minimum sequential departure interval')
    parser.add_argument('--depart-interval-max-s', type=positive_finite, default=4.0,
                        help='Maximum sequential departure interval')
    parser.add_argument('--initial-speed-min-mps', type=positive_finite, default=8.0,
                        help='Minimum seeded initial speed')
    parser.add_argument('--initial-speed-max-mps', type=positive_finite, default=12.0,
                        help='Maximum seeded initial speed')
    parser.add_argument('--formation-join-range-m', type=positive_finite, default=50.0,
                        help='Local connected-component gap')
    parser.add_argument('--middle-lane-offset-m', type=positive_finite, default=15.0,
                        help='Middle-lane follower offset behind an upper leader')
    parser.add_argument('--same-lane-gap-m', type=positive_finite, default=30.0,
                        help='Simple formation same-lane follower gap')
    parser.add_argument('--position-tolerance-m', type=positive_finite, default=2.0,
                        help='Simple formation longitudinal position tolerance')
    parser.add_argument('--speed-tolerance-mps', type=positive_finite, default=1.0,
                        help='Simple formation speed tolerance')
    parser.add_argument('--stable-time-s', type=positive_finite, default=1.0,
                        help='Continuous stable time required for FORMED')
    parser.add_argument('--reference-switch-gain-m', type=positive_finite, default=2.0,
                        help='Minimum position-error improvement before reference switch')
    parser.add_argument('--min-formation-lane-change-speed-mps',
                        type=positive_finite, default=5.0,
                        help='Minimum speed for starting a formation lane change')
    parser.add_argument('--hard-lane-change-gap-m', type=positive_finite, default=8.0,
                        help='Hard target-lane center clearance')
    parser.add_argument('--output-base', default='results/phase5g/demo',
                        help='Phase5G demo append-only result base inside this variant')
    parser.add_argument('--expected-source-sha256', type=sha256_hex,
                        help='Optional caller-held source root for standalone Phase5G replay')
    parser.add_argument('--expected-input-sha256', type=sha256_hex,
                        help='Optional caller-held input root; must accompany the source root')
    args = parser.parse_args()
    if args.command in ('phase5g', 'phase5g-formal'):
        if not args.case_file:
            parser.error(f'{args.command} requires an explicit --case-file')
        from experiments.phase5g import expected_replay_anchors, run_phase5g
        replay_anchors = (expected_replay_anchors(args.case_file)
                          if args.command == 'phase5g-formal' else {})
        source = run_phase5g(args.case_file, live=not args.offline,
                             formal=args.command == 'phase5g-formal')
        if args.command == 'phase5g-formal':
            from experiments.phase5g_replay import replay_run
            replay = replay_run(source, **replay_anchors)
            if not replay['passed'] or not replay['scientific_gate_passed']:
                raise SystemExit(1)
        return
    if args.command == 'phase5g-replay':
        if not args.run_dir:
            parser.error('phase5g-replay requires an explicit --run-dir')
        if bool(args.expected_source_sha256) != bool(args.expected_input_sha256):
            parser.error('standalone replay trust roots must be supplied together')
        from experiments.phase5g_replay import replay_run
        anchors = ({'expected_source_sha256': args.expected_source_sha256,
                    'expected_input_sha256': args.expected_input_sha256}
                   if args.expected_source_sha256 else {})
        raise SystemExit(0 if replay_run(args.run_dir, **anchors)['passed'] else 1)
    if args.command == 'phase5g-simple-matrix':
        if not args.offline:
            parser.error('phase5g-simple-matrix requires --offline')
        supplied_options = {
            token.split('=', 1)[0] for token in sys.argv[1:]
            if token.startswith('--')
        }
        unsupported = sorted(
            supplied_options - {'--offline', '--output-base'}
        )
        if unsupported:
            parser.error(
                'phase5g-simple-matrix does not accept: '
                + ', '.join(unsupported)
            )
        from experiments.phase5g_matrix import run_matrix
        run_matrix(args.output_base, live=False)
        return
    if args.command == 'phase5g-demo':
        from experiments.phase5g import run_phase5g_demo
        run_phase5g_demo(vehicle_count=args.vehicle_count, seed=args.seed,
                         target_speed_mps=args.target_speed_mps,
                          duration_s=args.duration_s, output_base=args.output_base,
                          mode='lane_priority', formal=False, live=not args.offline,
                          depart_interval_min_s=args.depart_interval_min_s,
                          depart_interval_max_s=args.depart_interval_max_s,
                          initial_speed_min_mps=args.initial_speed_min_mps,
                          initial_speed_max_mps=args.initial_speed_max_mps,
                          formation_join_range_m=args.formation_join_range_m,
                          middle_lane_offset_m=args.middle_lane_offset_m,
                          same_lane_gap_m=args.same_lane_gap_m,
                          position_tolerance_m=args.position_tolerance_m,
                          speed_tolerance_mps=args.speed_tolerance_mps,
                          stable_time_s=args.stable_time_s,
                          reference_switch_gain_m=args.reference_switch_gain_m,
                          min_formation_lane_change_speed_mps=
                              args.min_formation_lane_change_speed_mps,
                          hard_lane_change_gap_m=args.hard_lane_change_gap_m)
        return
    if args.command == 'phase5-r5':
        if not args.case_file or args.case_names:
            parser.error('phase5-r5 requires --case-file and executes its complete frozen case list')
        from experiments.phase5_r5 import run_phase5_r5
        run_phase5_r5(args.case_file, live=not args.offline, sampling=not args.no_sampling,
                     waiting_policy=args.waiting_policy,
                     lane_change_policy=args.lane_change_policy)
        return
    if args.command == 'phase5-r5-replay':
        if not args.run_dir:
            parser.error('phase5-r5-replay requires an explicit --run-dir')
        from experiments.phase5_r5_replay import replay_run
        raise SystemExit(0 if replay_run(args.run_dir)['passed'] else 1)
    if args.command == 'phase5':
        from experiments.phase5 import run_phase5
        run_phase5(live=not args.offline,case_names=args.case_names,sampling=not args.no_sampling)
        return
    if args.command == 'phase5-replay':
        if not args.run_dir:
            parser.error('phase5-replay requires --run-dir; latest is not an evidence source')
        from experiments.phase5_replay import replay_run
        replay_run(args.run_dir)
        return
    if args.command == 'test':
        import unittest
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
        raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
    if args.command == 'registry':
        from research.registry import build_registry
        build_registry()
    elif args.command == 'build':
        from research.registry import build_registry
        from research.network import build
        from research.demand import build_all
        build_registry()
        build()
        build_all()
    elif args.command == 'verify':
        from research.verify import verify
        verify()
    elif args.command == 'environment':
        from research.environment import probe_environment
        probe_environment()
    elif args.command == 'mcp':
        import asyncio
        from research.environment import probe_mcp
        asyncio.run(probe_mcp())
    elif args.command == 'smoke':
        from research.smoke import run_smoke
        run_smoke()
    elif args.command == 'screenshot':
        from research.screenshot import capture
        capture()
    elif args.command == 'phase2':
        from experiments.phase2 import run_phase2
        run_phase2()
    elif args.command == 'phase2-replay':
        from experiments.phase2 import replay_run
        replay_run(args.run_dir)
    elif args.command == 'phase3':
        from experiments.phase3 import run_phase3
        run_phase3()
    elif args.command == 'phase3-replay':
        from experiments.phase3_replay import replay_run
        replay_run(args.run_dir)
    elif args.command == 'phase4':
        from experiments.phase4 import run_phase4
        run_phase4()
    elif args.command == 'phase4-replay':
        from experiments.phase4_replay import replay_run
        replay_run(args.run_dir)


if __name__ == '__main__':
    main()

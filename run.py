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
for key in ('TEMP', 'TMP', 'TMPDIR', 'MPLCONFIGDIR', 'XDG_CACHE_HOME'):
    os.environ[key] = str(ROOT / 'tmp')
(ROOT / 'tmp').mkdir(exist_ok=True)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['registry', 'build', 'verify', 'test', 'environment', 'mcp', 'smoke', 'screenshot', 'phase2', 'phase2-replay', 'phase3', 'phase3-replay', 'phase4', 'phase4-replay', 'phase5', 'phase5-replay'])
    parser.add_argument('--run-dir', help='Replay an existing phase2/phase3 run directory inside keyan1')
    parser.add_argument('--case', action='append', dest='case_names', help='Phase5 explicit development case selection')
    parser.add_argument('--offline', action='store_true', help='Phase5 diagnostic only, no SUMO verification')
    parser.add_argument('--no-sampling', action='store_true', help='Phase5 partial development run')
    args = parser.parse_args()
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

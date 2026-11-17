"""直接运行真实 SUMO 3→2 局部编队变换；窗口随首次计算逐步推进。"""

# 常用设置
FLOW_VEH_H_LANE = 1750.0  # 每车道每小时请求数，三车道独立来车
DEMAND_DURATION_S = 600.0  # 来车持续时间；之后最多留 300 秒排空
RANDOM_SEED = 1  # 来车随机种子
GUI_DELAY_MS = 40  # 每个 0.1 秒仿真步的 GUI 延时；0 为最快

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
VARIANT_ROOT = PROJECT_ROOT / "variants/phase5g_pure_formation"
if str(VARIANT_ROOT) not in sys.path:
    sys.path.insert(0, str(VARIANT_ROOT))

from experiments import native_sumo as native  # noqa: E402
from experiments.native_sumo import run_case  # noqa: E402


def _validate(duration, gui_delay_ms):
    if type(FLOW_VEH_H_LANE) not in (int, float) or not 0 <= FLOW_VEH_H_LANE <= 36000:
        raise ValueError("FLOW_VEH_H_LANE 必须在 0–36000 之间")
    native._ticks(duration)
    if type(RANDOM_SEED) is not int or RANDOM_SEED < 0:
        raise ValueError("RANDOM_SEED 必须是非负整数")
    if type(gui_delay_ms) is not int or gui_delay_ms < 0:
        raise ValueError("GUI_DELAY_MS 必须是非负整数")


def _check(gui, duration, gui_delay_ms, output_fn):
    for name in ("sumo-gui" if gui else "sumo", "netconvert"):
        path = Path(native.binary(name))
        if not path.is_file():
            raise FileNotFoundError(f"未找到 {name}: {path}")
        output_fn(f"  {name}: {path}")
    traci = native.lock_traci()
    output_fn(f"  TraCI: {traci.__file__}")
    output_fn(f"  真实运行器: {Path(native.__file__).resolve()}")
    output_fn(f"  运行环境: {native.runtime_metadata()}")
    output_fn(f"  每道 {FLOW_VEH_H_LANE:g} 辆/h，来车 {duration:g} 秒，随机种子 {RANDOM_SEED}。")
    if gui:
        output_fn(f"  窗口每步延时 {gui_delay_ms} ms，支持手动平移和缩放。")
    output_fn("  巡航 28.8m/s；最高 33.3m/s；1000m 处 3→2，1200m 出口。")
    output_fn("自检通过：没有启动 SUMO，也没有创建运行目录。")


def main(argv=None, *, input_fn=input, output_fn=print) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查依赖与配置")
    parser.add_argument("--headless", action="store_true", help="不打开窗口，不等待输入")
    parser.add_argument("--duration", type=float, default=DEMAND_DURATION_S, help="来车时长，秒")
    parser.add_argument("--max-time", type=float, help="绝对仿真时间上限，秒")
    parser.add_argument("--gui-delay-ms", type=int, default=GUI_DELAY_MS, help="每步 GUI 延时，毫秒")
    parser.add_argument("--no-wait", action="store_true", help="运行结束后立即封存退出")
    parser.add_argument("--output-base", type=Path, help="结果根目录；每次新建独立子目录")
    args = parser.parse_args(argv)
    gui = not args.headless
    _validate(args.duration, args.gui_delay_ms)
    if args.check:
        _check(gui, args.duration, args.gui_delay_ms, output_fn)
        return 0
    output_fn(f"实时 SUMO：{FLOW_VEH_H_LANE:g} 辆/h/车道，局部编队形成与 3→2 变换。")
    directory = run_case(
        mode="transform",
        scenario="lane_drop",
        seed=RANDOM_SEED,
        flow=FLOW_VEH_H_LANE,
        duration=args.duration,
        gui=gui,
        gui_delay_ms=args.gui_delay_ms,
        auto_zoom=False,
        wait_before_close=gui and not args.no_wait,
        max_time=args.max_time,
        output_base=args.output_base,
        input_fn=input_fn,
        output_fn=output_fn,
    )
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    output_fn(f"结果: {directory}")
    output_fn(
        f"状态 {result['status']}；请求/发车/完成 "
        f"{result['requested']}/{result['departed']}/{result['completed']}；"
        f"接触 {result['collisions']}，瞬移 {result['teleports']}。"
    )
    state = result.get("formation_state")
    if state and state["participation_rate"] is not None:
        hold = state["mean_episode_s"]
        hold_text = f"{hold:.2f}秒" if hold is not None else "无"
        output_fn(
            f"本车编队关系参与率 {state['participation_rate']:.2%}；"
            f"同时参与峰值 {state['peak_participants']}辆；平均连续1状态 {hold_text}。"
        )
    return 1 if result["status"] in ("error", "unsafe") else 0


def _debug_friendly_entry() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    try:
        return main()
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        print(f"启动失败：{error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(_debug_friendly_entry())

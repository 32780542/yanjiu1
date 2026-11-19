"""在实时 SUMO 窗口比较 HDV、纯 NOA 和交错编队通过缩道的过程。"""

# 常用设置
MODEL = "formation"  # "hdv" 普通车，"noa" 纯 NOA，"formation" 交错编队（形成与变换）
LANE_COUNT = 3  # 缩道前的车道数：3 表示三变二，4 表示四变三
FLOW_VEH_H_LANE = 1750.0  # 每车道每小时流量，各车道独立来车
DEMAND_DURATION_S = 600.0  # 来车持续时间；之后最多留 300 秒排空
RANDOM_SEED = 20  # 来车随机种子
GUI_DELAY_MS = 1000  # 每个 0.1 秒仿真步的 GUI 延时；0 为最快
FORMATION_DEMO = False  # True 看 12 辆车在三车道直路补位；False 看连续车流通过缩道

import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent
VARIANT_ROOT = PROJECT_ROOT / "variants/phase5g_pure_formation"
if str(VARIANT_ROOT) not in sys.path:
    sys.path.insert(0, str(VARIANT_ROOT))

from experiments import native_sumo as native  # noqa: E402
from experiments.native_sumo import run_case  # noqa: E402
import run_cai_hdv  # noqa: E402

MODEL_NAMES = {"hdv": "普通 HDV（IDM 时距 0.85 秒）", "noa": "纯 NOA", "formation": "交错编队"}


def _validate(duration, gui_delay_ms):
    if type(FLOW_VEH_H_LANE) not in (int, float) or not 0 <= FLOW_VEH_H_LANE <= 36000:
        raise ValueError("FLOW_VEH_H_LANE 必须在 0–36000 之间")
    native._ticks(duration)
    if type(RANDOM_SEED) is not int or RANDOM_SEED < 0:
        raise ValueError("RANDOM_SEED 必须是非负整数")
    if type(gui_delay_ms) is not int or gui_delay_ms < 0:
        raise ValueError("GUI_DELAY_MS 必须是非负整数")


def _check(gui, gui_delay_ms, output_fn, model):
    for name in ("sumo-gui" if gui else "sumo", "netconvert"):
        path = Path(native.binary(name))
        if not path.is_file():
            raise FileNotFoundError(f"未找到 {name}: {path}")
        output_fn(f"  {name}: {path}")
    traci = native.lock_traci()
    output_fn(f"  TraCI: {traci.__file__}")
    runner = run_cai_hdv if model == "hdv" else native
    output_fn(f"  真实运行器: {Path(runner.__file__).resolve()}")
    output_fn(f"  运行环境: {native.runtime_metadata()}")
    if gui:
        output_fn(f"  窗口每步延时 {gui_delay_ms} ms，支持手动平移和缩放。")
    output_fn("  发车速度 28.8 m/s，车辆最高速度 33.3 m/s。")
    output_fn("自检通过：没有启动 SUMO，也没有创建运行目录。")


def main(argv=None, *, input_fn=input, output_fn=print) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=str.lower, choices=MODEL_NAMES, default=MODEL,
                        help="hdv 普通车，noa 纯 NOA，formation 交错编队")
    parser.add_argument("--lanes", type=int, choices=(3, 4), help="缩道前的车道数（3 或 4）")
    parser.add_argument("--check", action="store_true", help="只检查依赖与配置")
    parser.add_argument("--headless", action="store_true", help="不打开窗口，不等待输入")
    demos = parser.add_mutually_exclusive_group()
    demos.add_argument("--four-to-three-demo", action="store_true", help="观察 12 辆车从四道三层重排成三道四层")
    demos.add_argument("--transform-demo", action="store_true", help="观察同一批 12 辆从三道四层变成两道六层")
    demos.add_argument("--formation-demo", action=argparse.BooleanOptionalAction, default=FORMATION_DEMO,
                        help="在三车道直路观察 12 辆车由 6/4/2 补成四层交错队形")
    parser.add_argument("--duration", type=float, help="连续车流的来车时长，秒")
    parser.add_argument("--max-time", type=float, help="绝对仿真时间上限，秒")
    parser.add_argument("--gui-delay-ms", type=int, default=GUI_DELAY_MS, help="每步 GUI 延时，毫秒")
    parser.add_argument("--no-wait", action="store_true", help="运行结束后立即封存退出")
    parser.add_argument("--output-base", type=Path, help="结果根目录；每次新建独立子目录")
    args = parser.parse_args(argv)
    if args.model not in MODEL_NAMES:
        parser.error('MODEL 可选 "hdv"、"noa" 或 "formation"')
    lane_count = LANE_COUNT if args.lanes is None else args.lanes
    if args.four_to_three_demo:
        if args.lanes == 3:
            parser.error("--four-to-three-demo 使用四条上游车道")
        lane_count = 4
    if lane_count not in (3, 4):
        parser.error("LANE_COUNT 可选 3 或 4")
    if args.formation_demo and lane_count != 3 and not (args.transform_demo or args.four_to_three_demo):
        parser.error("--formation-demo 是三车道直路演示，四变三演示请用 --transform-demo")
    gui = not args.headless
    initial = None
    scenario = "lane_drop" if lane_count == 3 else "four_to_three"
    output_fn(f"模型：{MODEL_NAMES[args.model]}")
    if args.formation_demo or args.transform_demo or args.four_to_three_demo:
        if args.duration is not None:
            parser.error("--duration 用于连续车流；队形演示使用固定的 12 辆来车")
        lanes = (0, 0, 1, 0, 2, 0, 1, 0, 1, 2, 1, 0)
        if lane_count == 4:
            lanes = (0, 1, 2, 3, 0, 2, 1, 0, 3, 0, 1, 2)
            scenario = "four_to_three_demo"
        elif args.transform_demo:
            scenario = "formation_demo"
        else:
            scenario = "straight3"
        initial = [dict(lane=lane, depart=round(i * .7, 1), x=0, speed=28.8) for i, lane in enumerate(lanes)]
        duration = 8.
        if lane_count == 4:
            output_fn("12 辆车逐辆入场。四道 1600 米后缩成三道，再行驶 1000 米。")
        elif args.transform_demo:
            output_fn("12 辆车逐辆入场。三道 1600 米后缩成两道，再行驶 1000 米。")
        else:
            output_fn("三车道直路演示。12 辆车从入口逐辆发车，三道分别出发 6、4、2 辆。")
    else:
        duration = DEMAND_DURATION_S if args.duration is None else args.duration
        output_fn(f"连续车流。每道 {FLOW_VEH_H_LANE:g} 辆/h，来车 {duration:g} 秒，随机种子 {RANDOM_SEED}。"
                  f"1000 m 处从 {lane_count} 道缩至 {lane_count - 1} 道。")
    _validate(duration, args.gui_delay_ms)
    if args.max_time is not None:
        native._ticks(args.max_time)
    if args.check:
        _check(gui, args.gui_delay_ms, output_fn, args.model)
        return 0
    if args.model == "hdv":
        base = args.output_base or VARIANT_ROOT / "results/native_flow"
        directory = base.resolve() / f"{scenario}_hdv_s{RANDOM_SEED}_{uuid4().hex}"
        output_fn(f"结果: {directory}")
        successful = run_cai_hdv.run(
            native.lock_traci(), native.binary("sumo-gui" if gui else "sumo"), directory,
            flow=FLOW_VEH_H_LANE, seed=RANDOM_SEED, duration=duration,
            max_time=duration + 300 if args.max_time is None else args.max_time,
            matlab_data=None, gui=gui, road=scenario, initial=initial, gui_delay_ms=args.gui_delay_ms,
            wait_before_close=gui and not args.no_wait, input_fn=input_fn,
        )
        return 0 if successful else 1
    directory = run_case(
        mode="transform" if args.model == "formation" else "noa",
        scenario=scenario,
        seed=RANDOM_SEED,
        flow=FLOW_VEH_H_LANE,
        initial=initial,
        duration=duration,
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

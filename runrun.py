"""在实时 SUMO 窗口比较 HDV、纯 NOA 和交错编队通过车道数变化处的过程。"""

# 常用设置
MODEL = "formation"  # "hdv" 普通车，"noa" 纯 NOA，"formation" 交错编队（形成与变换）
LANE_COUNT = 3  # 缩道前的车道数：3 表示三变二，4 表示四变三
LAYOUT = None  # 可选 "3to2"、"4to3"、"3to4"、"2to3"；None 沿用 LANE_COUNT
TRANSFORM_DEMO = False  # True 观察同一批 12 辆车经过所选缩道或扩道
FLOW_VEH_H_LANE = 1750.0  # 每车道每小时流量，各车道独立来车
DEMAND_DURATION_S = 600.0  # 来车持续时间；之后最多留 300 秒排空
RANDOM_SEED = 20  # 来车随机种子
GUI_DELAY_MS = 40  # 每个 0.1 秒仿真步的 GUI 延时；0 为最快
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
LAYOUTS = {
    "3to2": ("lane_drop", "formation_demo"), "4to3": ("four_to_three", "four_to_three_demo"),
    "3to4": ("three_to_four", "three_to_four_demo"), "2to3": ("two_to_three", "two_to_three_demo"),
}
DEMO_ENTRY_LANES = {
    2: (0, 1) * 6,
    3: (0, 0, 1, 0, 2, 0, 1, 0, 1, 2, 1, 0),
    4: (0, 1, 2, 3, 0, 2, 1, 0, 3, 0, 1, 2),
}


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
    parser.add_argument("--layout", choices=LAYOUTS, help="车道变化，适用于连续来车和固定车队演示")
    parser.add_argument("--check", action="store_true", help="只检查依赖与配置")
    parser.add_argument("--headless", action="store_true", help="不打开窗口，不等待输入")
    demos = parser.add_mutually_exclusive_group()
    demos.add_argument("--four-to-three-demo", dest="demo", action="store_const", const="four_to_three",
                       help="观察 12 辆车从四道三层重排成三道四层")
    demos.add_argument("--transform-demo", dest="demo", action="store_const", const="transform",
                       help="观察同一批 12 辆车在所选缩道或扩道上变换队形")
    demos.add_argument("--long-platoon-demo", dest="demo", action="store_const", const="long",
                       help="观察 24 辆车在 2800 米上游整队，再经过所选缩道或扩道")
    demos.add_argument("--sparse-platoon-demo", dest="demo", action="store_const", const="sparse",
                       help="观察互相可见但起初分开的 24 辆车先整队，再通过车道变化处")
    demos.add_argument("--initial-demo", type=Path, metavar="JSON",
                       help="在 2800 米上游重现实验的逐车发车表（JSON 数组）")
    demos.add_argument("--formation-demo", dest="demo", action="store_const", const="straight",
                        help="在三车道直路观察 12 辆车由 6/4/2 补成四层交错队形")
    demos.add_argument("--no-formation-demo", "--no-transform-demo", dest="demo", action="store_const",
                       const="flow", help="使用连续车流")
    parser.set_defaults(demo="transform" if TRANSFORM_DEMO else "straight" if FORMATION_DEMO else "flow")
    parser.add_argument("--duration", type=float, help="连续车流的来车时长，秒")
    parser.add_argument("--max-time", type=float, help="绝对仿真时间上限，秒")
    parser.add_argument("--gui-delay-ms", type=int, default=GUI_DELAY_MS, help="每步 GUI 延时，毫秒")
    parser.add_argument("--no-wait", action="store_true", help="运行结束后立即封存退出")
    parser.add_argument("--output-base", type=Path, help="结果根目录；每次新建独立子目录")
    args = parser.parse_args(argv)
    if args.initial_demo is not None:
        args.demo = "initial"
    if args.model not in MODEL_NAMES:
        parser.error('MODEL 可选 "hdv"、"noa" 或 "formation"')
    layout = args.layout
    if layout is None and args.lanes is None:
        layout = LAYOUT
    if args.demo == "four_to_three":
        if args.lanes == 3 or (args.layout is not None and args.layout != "4to3"):
            parser.error("--four-to-three-demo 使用四变三布局")
        layout = "4to3"
    if layout is None:
        lane_count = LANE_COUNT if args.lanes is None else args.lanes
        if lane_count not in (3, 4):
            parser.error("LANE_COUNT 可选 3 或 4")
        layout = "3to2" if lane_count == 3 else "4to3"
    if layout not in LAYOUTS:
        parser.error("LAYOUT 可选 3to2、4to3、3to4 或 2to3")
    flow_scenario, demo_scenario = LAYOUTS[layout]
    lane_count = native.upstream_lanes(flow_scenario)
    if args.lanes is not None and args.lanes != lane_count:
        parser.error("--lanes 与 --layout 的上游车道数不符")
    transform_demo = args.demo in ("transform", "four_to_three")
    if args.demo == "straight" and (lane_count != 3 or args.layout is not None):
        parser.error("--formation-demo 是三车道直路演示，观察车道变化请用 --transform-demo")
    gui = not args.headless
    initial = None
    scenario = flow_scenario
    output_fn(f"模型：{MODEL_NAMES[args.model]}")
    if args.demo != "flow" and args.duration is not None:
        parser.error("--duration 用于连续车流；队形演示使用固定发车表")
    if args.demo == "initial":
        scenario = flow_scenario + "_long"
        try:
            initial = json.loads(args.initial_demo.read_bytes())
            if not isinstance(initial, list) or not initial or not all(isinstance(c, dict) for c in initial):
                raise ValueError("需要非空的逐车记录数组")
            duration = max(8., max(float(c.get("depart", 0.)) for c in initial) + .1)
        except (OSError, ValueError, TypeError) as error:
            parser.error(f"读取发车表失败：{error}")
        output_fn(f"从 {args.initial_demo.name} 读取 {len(initial)} 辆车，在 {layout} 道路上重现实验。")
    elif args.demo in ("long", "sparse"):
        scenario = flow_scenario + "_long"
        if args.demo == "sparse":
            tape = VARIANT_ROOT / "configs/sparse_demo_8721.json"
            initial = json.loads(tape.read_bytes())[layout]
        else:
            lanes = DEMO_ENTRY_LANES[lane_count]
            initial = [dict(lane=lanes[i % len(lanes)], x=526-22*i, speed=28.8) for i in range(24)]
        duration = 8.
        approach, downstream, outgoing = native.ROAD_LAYOUT[scenario]
        positions = [c["x"] for c in initial]
        output_fn(f"24 辆车在 0 秒从 {min(positions):g}–{max(positions):g} m 的初始位置同时发车。"
                  f"{approach} m 处由 {lane_count} 道变为 {outgoing} 道，再行驶 {downstream} m。")
    elif args.demo != "flow":
        lanes = DEMO_ENTRY_LANES[lane_count]
        scenario = demo_scenario if transform_demo else "straight3"
        initial = [dict(lane=lane, depart=round(i * .7, 1), x=0, speed=28.8) for i, lane in enumerate(lanes)]
        duration = 8.
        if transform_demo:
            approach, downstream, outgoing = native.ROAD_LAYOUT[scenario]
            output_fn(f"12 辆车逐辆入场。{approach} m 处由 {lane_count} 道变为 {outgoing} 道，再行驶 {downstream} m。")
        else:
            output_fn("三车道直路演示。12 辆车从入口逐辆发车，三道分别出发 6、4、2 辆。")
    else:
        duration = DEMAND_DURATION_S if args.duration is None else args.duration
        approach, _, outgoing = native.ROAD_LAYOUT[scenario]
        change = "缩至" if outgoing < lane_count else "扩至"
        output_fn(f"连续车流。每道 {FLOW_VEH_H_LANE:g} 辆/h，来车 {duration:g} 秒，随机种子 {RANDOM_SEED}。"
                  f"{approach} m 处从 {lane_count} 道{change} {outgoing} 道。")
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

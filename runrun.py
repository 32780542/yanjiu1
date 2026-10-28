"""直接运行真实 SUMO 3→2 局部编队变换；窗口随首次计算逐步推进。"""

# ===================== 用户配置区 =====================
FLOW_VEH_H_LANE = 1250.0  # 每车道每小时请求数，三车道独立来车
DEMAND_DURATION_S = 600.0  # 来车持续时间；之后最多留 300 秒排空
RANDOM_SEED = 1
SHOW_GUI = True
GUI_DELAY_MS = 40  # 每个 0.1 秒仿真步的 GUI 延时；0 为最快
AUTO_ZOOM = True  # 600m视野跟随前车，最后固定600–1200m瓶颈与下游
WAIT_BEFORE_CLOSE = True  # 交互式终端中，运行结束后按 Enter 关闭并封存
# 共同物理参数固定：巡航 28.8m/s，最高 33.3m/s；1000m 处 3→2。
# =====================================================

import argparse
from dataclasses import dataclass, replace
import json
import math
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
VARIANT_ROOT = PROJECT_ROOT / "variants/phase5g_pure_formation"
if str(VARIANT_ROOT) not in sys.path:
    sys.path.insert(0, str(VARIANT_ROOT))

from experiments import native_sumo as native  # noqa: E402
from experiments.native_sumo import run_case  # noqa: E402


@dataclass(frozen=True, slots=True)
class NativeDemoConfig:
    mode: str = "transform"
    scenario: str = "lane_drop"
    flow_veh_h_lane: float = 1250.0
    demand_duration_s: float = 600.0
    seed: int = 1
    show_gui: bool = True
    gui_delay_ms: int = 40
    auto_zoom: bool = True
    wait_before_close: bool = True


def build_config() -> NativeDemoConfig:
    return NativeDemoConfig(
        flow_veh_h_lane=FLOW_VEH_H_LANE,
        demand_duration_s=DEMAND_DURATION_S,
        seed=RANDOM_SEED,
        show_gui=SHOW_GUI,
        gui_delay_ms=GUI_DELAY_MS,
        auto_zoom=AUTO_ZOOM,
        wait_before_close=WAIT_BEFORE_CLOSE,
    )


def _validate(config):
    if (
        not isinstance(config.flow_veh_h_lane, (int, float))
        or isinstance(config.flow_veh_h_lane, bool)
        or not math.isfinite(config.flow_veh_h_lane)
        or not 0 <= config.flow_veh_h_lane <= 36000
    ):
        raise ValueError("FLOW_VEH_H_LANE 必须在 0–36000 之间")
    native._ticks(config.demand_duration_s)
    if type(config.seed) is not int or config.seed < 0:
        raise ValueError("RANDOM_SEED 必须是非负整数")
    if type(config.gui_delay_ms) is not int or config.gui_delay_ms < 0:
        raise ValueError("GUI_DELAY_MS 必须是非负整数")
    for name, value in (
        ("SHOW_GUI", config.show_gui),
        ("AUTO_ZOOM", config.auto_zoom),
        ("WAIT_BEFORE_CLOSE", config.wait_before_close),
    ):
        if type(value) is not bool:
            raise ValueError(f"{name} 必须是 True 或 False")


def _check(config, output_fn):
    _validate(config)
    for name in ("sumo-gui" if config.show_gui else "sumo", "netconvert"):
        path = Path(native.binary(name))
        if not path.is_file():
            raise FileNotFoundError(f"未找到 {name}: {path}")
        output_fn(f"  {name}: {path}")
    traci = native.lock_traci()
    output_fn(f"  TraCI: {traci.__file__}")
    output_fn(f"  真实运行器: {Path(native.__file__).resolve()}")
    output_fn(f"  运行环境: {native.runtime_metadata()}")
    output_fn(f"  配置: {config}")
    output_fn("  巡航 28.8m/s；最高 33.3m/s；1000m 处 3→2，1200m 出口。")
    output_fn("自检通过：没有启动 SUMO，也没有创建运行目录。")


def main(argv=None, *, input_fn=input, output_fn=print) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查依赖与配置")
    parser.add_argument("--headless", action="store_true", help="不打开窗口，不等待输入")
    parser.add_argument("--duration", type=float, help="来车时长，秒；默认 600")
    parser.add_argument("--max-time", type=float, help="绝对仿真时间上限，秒")
    parser.add_argument("--gui-delay-ms", type=int, help="每步 GUI 延时，毫秒")
    parser.add_argument("--no-wait", action="store_true", help="运行结束后立即封存退出")
    parser.add_argument("--output-base", type=Path, help="结果根目录；每次新建独立子目录")
    args = parser.parse_args(argv)
    config = build_config()
    config = replace(
        config,
        demand_duration_s=args.duration if args.duration is not None else config.demand_duration_s,
        gui_delay_ms=args.gui_delay_ms if args.gui_delay_ms is not None else config.gui_delay_ms,
        show_gui=config.show_gui and not args.headless,
        wait_before_close=config.wait_before_close and not args.no_wait and not args.headless,
    )
    _validate(config)
    if args.check:
        _check(config, output_fn)
        return 0
    output_fn(f"直接运行真实 SUMO：{config.flow_veh_h_lane:g}辆/h/车道，局部编队形成与3→2变换。")
    output_fn("SUMO 负责真实发车和运动，窗口与本次逐步计算同步推进。")
    directory = run_case(
        mode=config.mode,
        scenario=config.scenario,
        seed=config.seed,
        flow=config.flow_veh_h_lane,
        duration=config.demand_duration_s,
        gui=config.show_gui,
        gui_delay_ms=config.gui_delay_ms,
        auto_zoom=config.auto_zoom,
        wait_before_close=config.wait_before_close,
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

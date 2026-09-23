"""可直接点击“运行/调试”的SUMO可视化演示入口。"""

# ===================== 用户配置区：直接修改下面这些值 =====================

# 受控车辆总数：允许 3–60；默认 12 辆（最终目标是三车道各 4 辆）
VEHICLE_COUNT = 12

# 编队目标速度，单位 m/s
TARGET_SPEED_MPS = 10.0

# 每辆车私有随机初态的可重放种子：0 到 2**64-1 的整数
RANDOM_SEED = 1

# 相邻两辆车的随机发车间隔范围，单位秒
DEPART_INTERVAL_MIN_S = 2.5
DEPART_INTERVAL_MAX_S = 4.0

# 每辆车刚出现时的随机初速度范围，单位 m/s
INITIAL_SPEED_MIN_MPS = 8.0
INITIAL_SPEED_MAX_MPS = 12.0

# 仿真时长，单位秒；需覆盖最晚发车、30秒形成期限和10秒保持期
SIMULATION_DURATION_S = 90.0

# True：生成新轨迹后打开 SUMO-GUI；False：只生成轨迹
SHOW_GUI = True

# SUMO-GUI 每步播放延迟，单位毫秒（0 最快）
GUI_DELAY_MS = 40

# 是否自动调整 SUMO 视野
AUTO_ZOOM = True

# 轨迹播放结束后是否等待按 Enter 再关闭窗口
WAIT_BEFORE_CLOSE = True

# 简单局部规则1：同一局部编队的连续车距上限，单位 m
FORMATION_JOIN_RANGE_M = 50.0

# 简单局部规则2：中间车道车头相对上方车道车头的后移距离，单位 m
MIDDLE_LANE_OFFSET_M = 15.0

# 简单局部规则3：参考车在同车道或隔一条车道时的期望间距，单位 m
SAME_LANE_GAP_M = 30.0

# 简单局部规则4：位置误差容差，单位 m
POSITION_TOLERANCE_M = 2.0

# 编队稳定时允许的速度误差，单位 m/s
SPEED_TOLERANCE_MPS = 1.0

# 连续满足编队条件多久才记为已形成，单位秒
STABLE_TIME_S = 1.0

# 更换局部参考车所需的位置误差改善量，单位 m
REFERENCE_SWITCH_GAIN_M = 2.0

# 低于此速度不发起新的编队换道，单位 m/s
MIN_FORMATION_LANE_CHANGE_SPEED_MPS = 5.0

# 发起换道时，目标车道可见车辆的最小车头中心间距，单位 m
HARD_LANE_CHANGE_GAP_M = 8.0

# =========================== 用户配置区结束 =============================

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo.sumo_gui import (  # noqa: E402 - root must be available for editor debug
    SimpleFormationDemoConfig,
    check_simple_environment,
    run_simple_formation_demo,
)


def build_config() -> SimpleFormationDemoConfig:
    """Copy the editable constants into an immutable runtime configuration."""
    return SimpleFormationDemoConfig(
        vehicle_count=VEHICLE_COUNT,
        target_speed_mps=TARGET_SPEED_MPS,
        random_seed=RANDOM_SEED,
        depart_interval_min_s=DEPART_INTERVAL_MIN_S,
        depart_interval_max_s=DEPART_INTERVAL_MAX_S,
        initial_speed_min_mps=INITIAL_SPEED_MIN_MPS,
        initial_speed_max_mps=INITIAL_SPEED_MAX_MPS,
        simulation_duration_s=SIMULATION_DURATION_S,
        show_gui=SHOW_GUI,
        gui_delay_ms=GUI_DELAY_MS,
        auto_zoom=AUTO_ZOOM,
        wait_before_close=WAIT_BEFORE_CLOSE,
        formation_join_range_m=FORMATION_JOIN_RANGE_M,
        middle_lane_offset_m=MIDDLE_LANE_OFFSET_M,
        same_lane_gap_m=SAME_LANE_GAP_M,
        position_tolerance_m=POSITION_TOLERANCE_M,
        speed_tolerance_mps=SPEED_TOLERANCE_MPS,
        stable_time_s=STABLE_TIME_S,
        reference_switch_gain_m=REFERENCE_SWITCH_GAIN_M,
        min_formation_lane_change_speed_mps=
            MIN_FORMATION_LANE_CHANGE_SPEED_MPS,
        hard_lane_change_gap_m=HARD_LANE_CHANGE_GAP_M,
    )


def _print_check(report: dict, output_fn) -> None:
    output_fn('自检通过：没有启动SUMO GUI。')
    output_fn(f"  SUMO GUI: {report['sumo_gui']}")
    output_fn(f"  瓶颈路网: {report['network']}")
    output_fn(f"  Phase5G入口: {report['variant_run']}")
    output_fn(f"  Phase5G结果根目录: {report['variant_results']}")
    output_fn(f"  TraCI来源: {report['traci']}")
    output_fn(f"  已解析顶部配置: {report['configuration']}")


def main(argv=None, *, input_fn=input, output_fn=print) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    config = build_config()
    if arguments:
        if arguments != ['--check']:
            raise ValueError('runrun.py 只支持 --check；正常演示无需命令行参数')
        _print_check(check_simple_environment(config, PROJECT_ROOT), output_fn)
        return 0

    output_fn('直接运行：生成三车道领航者-跟随者编队（无通信、局部自组织、简单if/else规则）。')
    run_simple_formation_demo(
        config, input_fn=input_fn, output_fn=output_fn)
    return 0


def _debug_friendly_entry() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            reconfigure(encoding='utf-8', errors='replace')
    try:
        return main()
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        print(f'启动失败：{error}')
        if sys.stdin.isatty():
            try:
                input('按 Enter 结束...')
            except (EOFError, KeyboardInterrupt):
                pass
        return 1


if __name__ == '__main__':
    raise SystemExit(_debug_friendly_entry())

"""可直接点击“运行/调试”的SUMO可视化演示入口。"""

# ===================== 用户配置区：直接修改下面这些值 =====================

# 受控车辆总数：只允许 3、6 或 12；默认 6 辆
VEHICLE_COUNT = 6

# 编队目标速度，单位 m/s
TARGET_SPEED_MPS = 10.0

# 每辆车私有随机初态的可重放种子：0 到 2**64-1 的整数
RANDOM_SEED = 1

# 仿真时长，单位秒；必须是 0.1 秒的完整倍数
SIMULATION_DURATION_S = 45.0

# True：生成新轨迹后打开 SUMO-GUI；False：只生成轨迹
SHOW_GUI = True

# SUMO-GUI 每步播放延迟，单位毫秒（0 最快）
GUI_DELAY_MS = 40

# 是否自动调整 SUMO 视野
AUTO_ZOOM = True

# 轨迹播放结束后是否等待按 Enter 再关闭窗口
WAIT_BEFORE_CLOSE = True

# 简单局部规则1：本车前后对称观测范围，单位 m
LOCAL_FORMATION_RANGE_M = 90.0

# 简单局部规则2：参考车在相邻车道时的期望纵向间距，单位 m
ADJACENT_LANE_GAP_M = 15.0

# 简单局部规则3：参考车在同车道或隔一条车道时的期望间距，单位 m
SAME_LANE_GAP_M = 30.0

# 简单局部规则4：位置误差容差，单位 m
POSITION_TOLERANCE_M = 2.0

# 简单局部规则5：编队纵向加速度增量上限，单位 m/s²
FORMATION_ACCEL_LIMIT_MPS2 = 0.5

# 简单局部规则6：每辆车最多一次编队换道；当前规则固定为 1
MAX_FORMATION_LANE_CHANGES = 1

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
        simulation_duration_s=SIMULATION_DURATION_S,
        show_gui=SHOW_GUI,
        gui_delay_ms=GUI_DELAY_MS,
        auto_zoom=AUTO_ZOOM,
        wait_before_close=WAIT_BEFORE_CLOSE,
        local_formation_range_m=LOCAL_FORMATION_RANGE_M,
        adjacent_lane_gap_m=ADJACENT_LANE_GAP_M,
        same_lane_gap_m=SAME_LANE_GAP_M,
        position_tolerance_m=POSITION_TOLERANCE_M,
        formation_accel_limit_mps2=FORMATION_ACCEL_LIMIT_MPS2,
        max_formation_lane_changes=MAX_FORMATION_LANE_CHANGES,
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

    output_fn('直接运行：生成局部自组织交错编队新轨迹（无通信、简单if/else规则）。')
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

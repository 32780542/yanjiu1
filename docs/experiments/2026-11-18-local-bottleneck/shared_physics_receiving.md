# 接收道虚拟前车的范围

共同 IDM 参数下，C12 在 2000 辆/h/道两个种子的中道出流比 NOA 低 316.8 和 302.4 辆/h。中道在看到缩道时可把终止道尚未横移的车辆提前作为虚拟前车，前提是该车的位置与运动满足现行横移安全检查。这里检验缩短或取消这种提前调速的作用范围。两种规则仅替换 `_queue_front` 的中道 `direct` 条件，共用相同车辆物理、真实前车、0 道逻辑、横移执行和安全约束。 [中道出流与排队](shared_physics_queue.md)

- **PitchDirect**。只有前方终止道车辆位于本车一个接入间距内，缩道可见才允许提前跟驰。已经向内横移的前车仍可按原感知范围接续。接入间距沿用 `max(5.5+0.85v, 16)` 米。 [冻结规则](rules/PitchDirect.py)
- **MotionDirect**。中道根据终止道车辆实测向内横移接续。预先知道缩道位置仍用于其他原有判断。 [冻结规则](rules/MotionDirect.py)

旧 C12 轨迹在 100–600 s 每秒采样一次。取 x=800–1000 m 居中且横移速度绝对值不超过 0.1 m/s 的中道车辆，按相邻 0.1 s 的横向位置差估计横移速度。种子 211 和 212 中，分别有 77/5499 和 115/5208 个样本选择了尚未主动横移的终止道虚拟前车。保留近距离提前接续后，被替换的参考前车分别为 12 和 6 个。用同一物理前车限速估算，PitchDirect 在被替换样本中的换道计划前速度指令平均增加 4.08 和 4.18 m/s。MotionDirect 对应增加 1.92 和 1.52 m/s。这组读数来自固定轨迹上的前车选择复算，后面的配对仿真测量持续交通结果。 [快照复算脚本](../../../tmp/staggered_bottleneck/n18_receiving_candidate_rules/probe_snapshot_fronts.py) · [逐种子抽样](../../../tmp/staggered_bottleneck/n18_receiving_candidate_rules/snapshot_front_probe.json)

## 2000 辆/h/道配对

四例均用 600 s 需求、200 m 直接可见、相同请求序列和三参数迁移的 IDM，安全排空 4064 个请求，零碰撞和瞬移。表中单位为秒、辆/h 或辆·s，差值方向为候选减对应对照。中道断面流量在 100–600 s 按 x=1000 m 穿越量计算。 [逐例双基准结果](stage/shared_physics/receiving_lane_comparison.json) · [分道审计](stage/shared_physics/receiving_lane_queue.json)

| 规则 | 种子 | 系统时间（s） | 相对 C12（s） | 相对 NOA（s） | 相对 C12 的中道出流（辆/h） | 相对 C12 的末道停车（辆·s） |
|---|---:|---:|---:|---:|---:|---:|
| PitchDirect | 211 | 111.168 | +17.736 | +20.749 | −165.6 | −509.6 |
| PitchDirect | 212 | 102.235 | +0.897 | −0.701 | +28.8 | +119.6 |
| MotionDirect | 211 | 97.207 | +3.776 | +6.788 | +86.4 | +2471.5 |
| MotionDirect | 212 | 98.719 | −2.620 | −4.218 | +223.2 | +2974.8 |

MotionDirect 提高了两个种子的中道出流，也使 x=600–800 m 的中道低速暴露从 4098.0 和 2836.1 降至 2716.5 和 1993.0 辆·s。与此同时，瓶颈 x=800–1100 m 平均行程增加 1.030 和 2.534 s，终止道末端停车增加。两例入口等待分别变化 +2.113 和 −3.091 s。中道收益与终止道代价同时出现，最终系统时间一增一减。

PitchDirect 在两例均增加了系统时间。种子 211 的 x=100–600 m 行程增加 10.129 s，入口等待增加 3.964 s，断面总出流减少 216.0 辆/h。两种变化均作为共同物理下的机制敏感性保留。 [PitchDirect 原始批次](../../../tmp/staggered_bottleneck/n18_pitch_r01/protocol.json) · [MotionDirect 原始批次](../../../tmp/staggered_bottleneck/n18_motion_r01/protocol.json) · [试验入口](tools/run_shared_physics_candidate.py)

# 阶段5独立离线交错检测器

`experiments/phase5_detection.py` 只读完整记录，不参与控制、不输出控制指令。全局相位拟合仅用于评分；在线控制器不得导入此模块或读取它的结果。车辆键只标记跨帧的同一成员，车型、预设槽位、未来计划等附加字段均不参与判断。

## 输入与冻结口径

```python
detect_frames(frames, d=15.0, lane_width=3.3,
              position_tolerance=2.0, speed_tolerance=1.0,
              persistence_s=5.0, formation_deadline_s=30.0, hold_s=10.0)
```

`frames` 是时间严格递增的序列，每项为 `{'time_s': float, 'states': {key: VehicleState 的 asdict 结果}}`。只读取位置、速度、航向。车辆键使用可排序的字符串。道路直行方向为世界 x，y=0 为下边界，车道索引 `floor(y/lane_width)`；这是本研究直线路网的离线几何约定，不是一般曲线路网地图匹配。未增加车道中心偏差门槛。位置和时间非有限值、逆序/重复时间、非正参数会报错。

主参数 d=15 m 时，格点误差上限为规格 `max(2 m, 0.1d)=2 m`。显式 `position_tolerance` 就是实际阈值，敏感性分析可分别设 1/2/3 m；若将来改变 d，调用方应重新登记 `max(2, 0.1d)`，函数不暗中覆盖显式阈值。为避免相邻槽位歧义，要求容差小于 d/2。

每个局部组必须同时满足：

- 至少3辆，包含至少两个相邻车道。
- 全组标量速率 `hypot(vx_mps, vy_mps)` 的最大值减最小值不超过速度容差；不允许仅以相邻边速度差串接超过阈值的组。此标量口径不声称二维速度方向一致。
- 将 `(x-lane*d) mod (2d)` 放在圆上，取最短覆盖弧的中点拟合相位，每辆车离最近合法格点不超过位置容差。
- 同一 `(lane, slot)` 至多一辆；重叠占位不能扩大组规模。
- 已占格点图连通。同车道仅相隔一个 2d 槽位、相邻车道仅相隔 d 槽位建立边，隔空跳过空槽位无边。实际边距误差因此不超过两倍单点容差，并另记实际最大边距误差。

候选枚举使用至多 N 个圆周相位窗口乘 N 个速率窗口，再求相邻占位连通分量，不遍历 2^N 个车辆子集。重复占位时保守排除该槽的所有候选，不任选一辆以制造成功。当前只创建极大有效分量的跟踪项；已建立子群在其他成员加入后仍独立逐帧验证。未预先出现过的任意隐藏子集不会穷举创建，故局部持续子群检测具有这一保守漏报限制；严格全队检测没有该子集枚举依赖。

同一成员集合的有效样本从 `start_time_s` 到 `end_time_s`，持续时长严格为二者之差，不把最后一帧外推一个周期。任一成员消失、几何失效或缺帧结束该段；重新有效必须新计时。名义间隔取记录中最小正间隔并上限0.1 s，因此0.05 s对照中的单个缺帧同样打断；统一仅有0.2 s间隔的输入不能证明连续性。该规则证明的是给定采样上的持续，不声称帧间连续时间性质。

形成确认时刻为连续有效起点+5 s。严格开发里程碑为确认时刻不晚于记录起点+30 s，确认之后再保持10 s，即总连续有效至少15 s。`geometric_hold_10s_from_start` 另报告从几何起点计10 s的较宽口径，避免与严格确认后保持混淆。`formation_deadline_s`、`hold_s` 改变时同样使用上述语义，字段名中的10s表示默认值。

## 输出 schema

结果可直接 JSON 编码，`schema_version=1`、`offline_only=true`。主要字段：

| 字段 | 语义 |
| --- | --- |
| `parameters` | 实际检测参数，包括样本最大允许间隔与4×1.8 m车身尺寸 |
| `cohort_members/cohort_size` | 整份日志中出现过的所有车辆键及数量，包含后来离开的车辆 |
| `success/whole_cohort_success` | 同一、连通、包含整个cohort的组满足严格里程碑 |
| `local_success` | 至少一个局部子群满足严格里程碑；不得替代全队成功 |
| `failure_reasons` | 无持久组、局部截止/保持不通过、全队门槛未通过等原因 |
| `sampling_gap_count` | 发现的超间隔次数 |
| `intervals` | 已达到5 s持续的组区间 |
| `candidate_intervals` | 全部跟踪区间，含不足5 s的失败短段，不能删掉失败段 |
| `frames` | 逐帧局部组、覆盖、全队失败原因和占路长度 |

区间含 `members/start_time_s/end_time_s/duration_s/formed_time_s/held_time_s/formation_by_deadline/whole_cohort/success/failure_reasons`。`end_reason` 为 `recording_end`、`geometry_or_membership_lost` 或 `sample_gap`；录制结束属于右截断，不能证明此后保持或失效。形成、保持时刻未达到时为 `null`。另记区间最大格点误差、最大组内速率范围、最小邻接完整度、最大占路长度。

逐帧 `groups` 是当时几何有效的组（包含仍验证中的历史子群），尚不表示已持续5 s。每组含相位、最大格点误差、速率范围、车道、成员、占位数、完整度及长度：

- `possible_slots` 分母：在该组最小至最大车道与最小至最大拟合纵向槽位坐标的矩形包络内，所有符合奇偶格点规则的位置数。`slot_occupancy_fraction=occupied_slots/possible_slots`。
- `occupancy_edges_denominator` 分母：上述全部合法槽位之间的无向邻接边数，边规则与检测完全相同。`occupancy_edges_numerator` 为实际有车占据的边数，`adjacency_occupancy_completeness` 为两者之比；不含包络外假想无限邻居。
- 例如三车 `(x,lane)=(0,0),(15,1),(30,2)` 连通，但包络有5个合法槽位、6条潜在边；实际3个占位、2条边，节点占位率3/5、邻接占位完整度2/6。完整度不是额外成功硬门槛，必须伴随检测结果报告。
- `road_span_m` 为组内最前车身边界至最后车身边界的世界x跨度，使用固定4×1.8 m矩形及各车航向投影；`center_span_m` 为车心跨度。二者均不是SUMO车头间距。逐帧 `fleet_road_span_m` 使用所有在场车辆。
- `fleet_coverage_fraction` 是有效局部组成员的并集除以全cohort；两个远离的三车组可覆盖6/6，仍不能构成一个六车组。`largest_group_fraction` 单独给出最大连通组/cohort，严格全队成功还要求持续同组。

## 验证与重放

`python -m unittest tests.test_phase5_detection -v` 使用固定轨迹测试，覆盖3/6/12车几何、远处稀疏格点、全组速度链、单车道、非相邻车道、重复占位、换成员、成员加入、两远处子群、短录制、断裂恢复、0.1/0.05 s缺帧、截止时刻、圆周相位、容差敏感性、隐藏字段不变与输入不可变。

开发红绿日志保存在 `results/phase5/detector_development_20260912/`。其中离线固定轨迹、全部检测输出、源文件哈希与独立 `replay.py` 用于重放；这些是检测器的合成测试证据，不是在线控制形成的研究结果。实验调用方须对同一原始轨迹分别重复1/2/3 m位置阈值、0.5/1/1.5 m/s速度阈值，保留所有结果，不替换默认主判定。

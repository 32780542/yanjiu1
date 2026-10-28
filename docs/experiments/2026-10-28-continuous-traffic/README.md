# 2026-10-28 持续大交通流实验成果

本目录保存54个预定工况的便携成果。正文见[持续大交通流验证报告](../../持续大交通流验证报告.md)，公式、实验设置与文献依据见[评价方法](../../持续交通流评价方法.md)。

| 文件 | 内容 |
| --- | --- |
| `protocol.json` | 原批次运行前固定的54例参数、车辆生成机制和源码摘要。 |
| `results.json`、`cases.csv` | 54例独立复算结果，包括安全失效。 |
| `groups.json`、`groups.csv` | 18个工况的运行数量、有效数量、均值与样本标准差。 |
| `pairs.json`、`pairs.csv` | 30个同种子配对及改善率。 |
| `pair_groups.json`、`pair_groups.csv` | 10组配对统计。 |
| `verification.json` | 324文件摘要、41282条车辆台账、54例逐拍累计及30个请求表配对的核验。另含每例原始目录与两批源码zip摘要。 |
| `traffic_efficiency.*` | 系统时间、在网行程时间、实际出口流量，PNG/SVG。 |
| `traffic_fuel.*` | 距离归一化油耗及每车燃油流率，PNG/SVG。 |
| `traffic_speed_maps.*` | seed 1的四档需求、两模式600 s时空速度图，PNG/SVG。 |

效率和燃油曲线来自`groups.json`的三车道`demand`组，误差条为3个种子的样本标准差；时空图从`verification.json`所指向的真实位置样本生成，5 s×25 m网格内求平均。PNG为300DPI，SVG可编辑；CSV带UTF-8 BOM，JSON保留完整精度。

关键字段：

| 字段 | 含义 |
| --- | --- |
| `formation` | `true`为纯规则编队，`false`为本工程常规跟驰和车道保持。 |
| `flow_veh_h_lane` | 每车道名义请求率，单位辆/h；随机实现数量单独记录。 |
| `requested` | 600 s完整计划请求数，包括早停时未来尚未释放的请求。 |
| `requested_until_end`、`not_yet_requested_final` | 实际记录终点已经释放、尚未释放的请求数。 |
| `entered`、`completed` | 实际入场数、实际离场数。 |
| `pending_final`、`onroad_final` | 终点实际入口队列数、在网车辆数。 |
| `pending_at_600s`、`onroad_at_600s` | 600 s时入口队列数、在网车辆数。 |
| `mean_entry_wait_s` | 请求至实际入场的平均等待。 |
| `mean_travel_time_s` | 实际入场至1200 m出口的平均在网时间。 |
| `mean_system_time_s` | 请求至实际出口的平均总时间，包含入口等待。 |
| `exit_flow_veh_h` | 0–600 s实际离场数折算的全路出口流量，单位辆/h。 |
| `fuel_g_per_km` | 燃油mg除以里程m，数值单位为g/km。 |
| `mean_fuel_rate_mg_s` | 在网燃油mg除以车辆在网时间s。 |
| `total_fuel_kg` | 同一在网区间的累计燃油质量，单位kg。 |
| `network_mean_speed_mps` | 累计行驶距离除以累计车辆在网时间。 |
| `collision_pairs`、`road_departure_vehicles` | 检测到接触的车辆对数、驶出道路的车辆数。 |
| `first_safety_event_s` | 首次实际安全事件时刻。 |
| `termination_reason` | 排空、达到上限、碰撞、驶出道路，或旧批次带事件的完整记录。 |
| `comparison_valid` | 两组均排空且均无接触、驶出道路，配对性能有效。 |
| `*_reduction_pct` | 相对配对对照的减少百分比，正值减少、负值增加。 |
| `runs`、`valid_runs` | 预定运行数、进入性能统计的有效运行数。 |
| `*_mean`、`*_sd` | 跨种子均值、样本标准差；改善率先逐配对计算后汇总。 |

早停例未观察完整600 s时，固定窗口指标为空；完整车群尚未排空时，车群平均等待、行程时间、系统时间为空。安全无效配对的改善率为空。组表的请求数、完成数保留全部运行；性能均值使用有效运行。两车道编队组为1/3有效，其单个有效值在原始表中保留。

原批次保留30个已封存条件，接续批次完成其余24个条件，每个工况只使用一份封存结果。原始gzip轨迹、行程台账、事件与源码快照在本机：

- `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\continuous_traffic\20261028T031206451914Z`
- `D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\continuous_traffic\20261028T041744709217Z`

旧批次的协议与实际源码摘要保留在`protocol.json`；接续的首次安全事件停止机制、数值记录等价读取及两批证据映射见正文和`verification.json`。两批原目录及中断前缀均保留。GitHub保存代码、报告和本目录的小体积成果。

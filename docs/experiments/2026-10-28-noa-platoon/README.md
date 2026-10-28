# 基础NOA修正后的持续车流与局部几何匹配指标

2026-10-28更正：这些`platoon`字段统计至少两辆车的几何匹配，并不要求完整多层编队。仅NOA的偶然并排会被计入。原数值与摘要保留，图表标签已更正；完整结构复查见[诊断报告](../../仅NOA误计与大流量小车组诊断.md)。

本目录为2026-10-28最终冻结代码的54工况成果。正文见[直路对照与编队报告](../../直路NOA与编队规模稳定度报告.md)，当前行驶与入口见[修正规则](../../基础NOA与入口修正规则.md)，编队识别、公式、时间权重和文献见[规模与稳定度评价](../../编队规模与稳定度评价.md)。

| 文件 | 内容 |
| --- | --- |
| `protocol.json` | 54个固定条件、v3入口、共同控制条件、评价参数及源码摘要。 |
| `results.json`、`cases.csv` | 54例独立复算结果，含全部预定运行。 |
| `groups.json`、`groups.csv` | 18组均值、样本标准差及有效数量。 |
| `pairs.json`、`pairs.csv` | 30个同种子配对的效率与燃油变化，负值保留。 |
| `pair_groups.json`、`pair_groups.csv` | 10组配对改善率统计。 |
| `verification.json` | 原始文件摘要、逐车与逐拍累计核验、配对请求一致性，以及每例实际来源。 |
| `noa_straight_comparison.*` | 直路行程时间和源端未放行等待，PNG/SVG。 |
| `platoon_size_stability.*` | 平均/最大规模、参与率、已编队成员稳定时间占比H，PNG/SVG。 |
| `platoon_quality.*` | 几何RMS、队内速度RMS和内部断裂率，PNG/SVG。 |
| `figure_sources.json` | 图的数据来源、筛选与误差条定义。 |

JSON保留完整数值，CSV为UTF-8 BOM。三组图为300DPI PNG与可编辑SVG。曲线来自主三车道的`demand`组；占比面板显示均值和实际种子点，其他面板显示均值±样本标准差。最大规模曲线按“各例观察最大值”求跨种子均值，正文另报跨种子观察到的实际最大值。

## 直接编队字段

| 字段 | 含义 |
| --- | --- |
| `mean_platoon_size` | 匹配车辆秒/匹配车组秒，包含全部成员，最小2辆。 |
| `max_platoon_size` | 实际记录中观察到的最大局部几何匹配分量人数。 |
| `participation_rate` | 局部匹配成员车辆秒/全部测量段车辆秒，数值为0–1。 |
| `geometry_rms_m` | 已识别邻接关系相对位置误差的关系时间加权RMS，单位m。 |
| `speed_rms_mps` | 各局部车组内实际速度偏差的车辆时间加权RMS，单位m/s。 |
| `stable_participation_rate` | 同一物理关系连续保持5s确认之后，其端点车辆时间/全部测量段车辆时间，数值为0–1。 |
| `platoon_stability_rate` | 离线派生：稳定车辆时间/已匹配车辆时间，数值为0–1；它把已编队成员的持续性与全体参与率分开。 |
| `internal_breaks_per_100_platoon_vehicle_s` | 内部关系丢失次数/100匹配车辆秒。正常出界、记录结束和采样缺口删失。 |

每例原始目录还保存`platoon_metrics.json`，含车辆秒、编队秒、关系秒、稳定车辆秒、删失数、缺口数、采样范围和全部识别参数。这些是复算分母与记录完整性的审计量。

只有同道真实D间距边能连接层与层，跨道只连接同层相位。双车或同层小队与完整多层大队在结构上有区别，规模字段统一报告局部连通车组人数。全部指标只读物理位置，不读控制器角色或补位标签。仅NOA中偶然出现的有序小队按同一标准记录。

## 时间与数量字段

v3逐车时刻为：请求`requested_s`、−300m源端放行`inserted_s`、0m测量入口`entered_s`、1200m出口`exited_s`。

| 字段 | 含义 |
| --- | --- |
| `mean_entry_wait_s` | v3中的源端未放行等待：inserted−requested。 |
| `mean_upstream_travel_s` | −300m至0m的实际运动时间：entered−inserted。 |
| `mean_entry_delay_s` | 请求至0m的合计时间，为前两项之和。 |
| `mean_travel_time_s` | 0m至1200m测量段的实际行程时间。 |
| `mean_system_time_s` | 请求至出口，包含源端等待、上游运动与测量段行驶。 |
| `source_queue_final`、`source_queue_at_600s` | 源端实际未放行请求数。 |
| `upstream_final`、`upstream_at_600s` | 已放行但尚未跨过0m的物理车辆数。 |
| `pending_final`、`pending_at_600s` | 尚未进入测量段的请求数，包含源端队列和上游运动车辆。 |
| `onroad_final`、`onroad_at_600s` | 0–1200m测量段内实际车辆数。 |
| `requested` | 0≤t<600s的完整计划请求数；早停的未来请求单独保存。 |
| `entered`、`completed` | 实际测量入场数和出口数。 |
| `exit_flow_veh_h` | 0–600s实际离场数折算的全路出口流量，单位辆/h。 |

`flow_veh_h_lane`是每车道名义请求率；随机实际请求数单列。上游段两组均为普通NOA；测量段各按仅NOA或NOA＋编队。源端短空隙保留请求，已经在道路上的车辆继续运动。真实过载队列全部保留。

燃油和里程在0–1200m同区间累计：`fuel_g_per_km`为mg/m，其数值单位为g/km；`mean_fuel_rate_mg_s`为每车在网时间加权燃油流率；`total_fuel_kg`为总燃油质量。HBEFA3模型与车辆类别沿原协议。

## 有效性与证据

`runs`是预定重复数，`valid_runs`是完整排空且无接触、无驶出道路的数量。性能组均值只用有效运行，请求数和完成数保留所有预定运行。`comparison_valid`还要求配对双方都有效。源端、在网和未来请求未完成时均保留数量，完整车群时间均值留空；没有编队时规模和条件误差留空，参与率按是否存在车辆暴露给0或空。

各指标的`_n`表示参与该均值统计的非空观测数，区别于安全有效运行数。例如2000辆/h的仅NOA组3次均安全排空，但两次没有物理车组；参与率的n=3（其中两次为0），条件规模、几何和稳定占比的n=1。图中n标出这种少于预定重复数的条件统计。条件均值不把未成队的缺测填成0。

原始根为`D:\yanjiu1\keyan1\variants\phase5g_pure_formation\results\continuous_traffic_v3\20261028T100105100032Z`，每例7个带摘要的文件加`hashes.json`，批次共享源码zip。原始轨迹采用gzip，代码和本目录的小体积成果随GitHub保存。旧边界探针和中断前缀保留在各自独立目录，未混入这54个正式条件。

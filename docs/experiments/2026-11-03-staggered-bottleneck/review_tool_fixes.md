# 工具审查修复与 104 例协议复核

此记录补充 `review_candidates.md` 中两项工具发现；不修改旧批次冻结 driver、旧原始数据和旧分析目录，不重新仿真。

## 修复

runner 保留整数流量原目录格式，启动前在参数校验阶段生成全部预定 case output 名称并检查重复（Windows 使用同一大小写归一规则）。
`1750.0001` / `1750.0002` 的 `:g` 目录名碰撞现在会在 batch.mkdir 或任何 worker 启动之前明确 parser.error。

summary 现在逐案核对：

- protocol task 与 manifest 的候选/阶段/流量/种子/道路/模式、输出路径及基线 commit。
- companion compact 原 input/result 中的模式、需求时长、上限及工况字段，与原六源 hash 和 protocol 的冻结源 hash。
- 原 input/result/trips 的 blob SHA 与既有 traffic case 中的对应 SHA。
- 原请求列表的既有 demand hash，以及 trips 的逐车请求时间、原始车道/位置/速度与请求身份。

所有 compact/traffic 归档仍重新离线复核。计划缺失和计划外案例均保留；协议不匹配显式写入 protocol_issues 并禁止有效配对。
不同 batch 的重复 candidate/flow/seed/scenario/mode 仍报错，不静默选择或合并。新增检查没有修改指标公式、时窗、SUMO 参数或均值口径。

## 先反例后通过

14 项工具合同：原实现的新增协议合同预期失败，路径反例也触发了“在碰撞检查前启动 worker”的边界错误，
记录为 `results/operations/20261103T032619727565Z_staggered-protocol-path-contract-red_9d98bcd6`（3 failures、1 error）。
修复后 14 项全通过，记录为 `results/operations/20261103T032753569637Z_staggered-protocol-path-contract-green_55282270`。
此前的限定 unlink、先检查两文件全部 hash、失败保留原件等合同继续通过。

## 只重算现有 104 例

六个原批次分别为 TM32、TM1250八例、A20、D10、C10、ablation24。
新输出 `tmp/staggered_bottleneck/20261103_screen104_protocol_analysis/` 保存 per_case.csv、paired.csv、summary.json。

`results/operations/20261103T032936732078Z_staggered-screen104-protocol-reanalysis_004a1e09`
退出 0，19.844 s；104/104 archive 和协议/input/request/source 对应均通过。
104 例物理 safe，102 例排空；NH 的 2500 流量、seed1/4 两例 time_limit 完整保留，未进入有效性能配对。
84 个配对中 82 个有效，正式完整 `[100,600)` 区域窗口仍为 0/104，没有补窗或改口径。

该 operation 的成功表示证据处理与协议核验成功，不表示所有策略通过性能验收。
紧凑字段对完整轨迹的限制仍见原独立审查报告；本修复没有把原 positions/events 变成可重建的证据。

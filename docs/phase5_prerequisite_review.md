# 阶段5前置条件独立审查

2026-09-12。审查根目录 `D:\yanjiu1\keyan1`。本审查只读生产代码、配置、原始运行和指定 MATLAB 参考源码；新增写入限定为本报告及 `results/phase5/prerequisites_20260912/`，没有提交 Git。

**阶段4固定基线的本次前置核验通过，可以继续阶段5小规模实现。** 这不等于阶段5实现、形成/恢复实验或阶段6入口已经验收。证据汇总为 [final_summary.json](D:/yanjiu1/keyan1/results/phase5/prerequisites_20260912/final_summary.json)。审查启动后主任务仍在开发；本报告不能替代开发完成后的受影响回归。

## 读取范围与基线版本

已读取第六版规格的主链距离定义、§4.7、§9、§10及阶段5条款，以及 `phase5_entry.md`、`phase4_completion_acceptance.md`、`phase4_closure_review.md`、`phase4_completion_methods.md`、`kinematic_motion.md`。实际代码核查覆盖 `run.py`、参数登记和基础核验、阶段4重放、时钟、局部观测/NOA记忆契约；六车几何另直接核对 `D:/matlab_huipu_2000/formationControlNormal.m`。

2026-09-12 09:26 UTC 启动前，普通固定运行 `20260910T232224392627Z_ab0de887` 和补充固定运行 `20260910T232224409038Z_4712f90d` 各登记的77个代码/配置文件，与当时当前完整清单逐项一致，没有修改或新增项。普通270项、补充157项封存哈希及两包77项源码快照全部匹配。见 [before.json](D:/yanjiu1/keyan1/results/phase5/prerequisites_20260912/before.json)。

09:30:36 UTC 的审查终点再次逐文件计算：两份固定包的全部文件（包括清单本身）与启动前一致；原77项当前源码仍无差异，当时仅新增 `experiments/phase5_detection.py` 和 `tests/test_phase5_detection.py`。这些新增文件属于并行开展的阶段5工作，不属于本次141项基线测试的发现范围。主任务后续计划扩展 `simulation/noa_clock.py`、`run.py` 和登记入口，应在最终阶段5验收中列出实际变化并重新检查，不能引用本报告声称扩展后源码仍与阶段4相同。

登记解释器实读 Python 3.12.9，隔离/禁用 site/禁止字节码标志均生效；登记二进制实读 SUMO 1.27.1。29个只读 MATLAB 参考文件哈希全部匹配。参数登记在核验时为264行；本审查没有改变任何算法、模型或安全参数。依据见 [几何与环境核对](D:/yanjiu1/keyan1/results/phase5/prerequisites_20260912/geometry_and_environment.json)。

## 执行结果与运行ID

| 检查 | 本次结果 |
|---|---|
| 原 `run.py verify` 入口 | 退出0；`passed=true`，需求数588/717/830/976 |
| 原 `run.py test` 入口 | 退出0；141项，96.341 s，OK |
| 固定普通阶段4重放 | 退出0；新ID `20260912T092616561829Z_ccefb980`，completed/passed |
| 固定补充阶段4重放重试 | 退出0；新ID `20260912T092708946460Z_2409e0de`，completed/passed |
| 六车源码几何及登记环境 | 退出0；算术关系及版本核验通过 |

普通重放复算16变体、2,222区间、90,060个车辆积分子步及6,000个积分细化子步；最大数值差0，1,000次隔离比较通过，9类篡改全部拒绝。补充重放复算6变体、1,410区间、102,000个车辆积分子步；最大数值差0，588次隔离比较通过，9类篡改全部拒绝。补充包没有积分细化轨迹，不重复计普通包的6,000子步。两次成功重放启动时记录的当前旧源码差异均为空。

成功运行明确引用固定源目录，没有使用 `latest` 选择源运行。结果分别为 [普通重放](D:/yanjiu1/keyan1/results/phase5/prerequisites_20260912/replays/20260912T092616561829Z_ccefb980/validation.json) 与 [补充重放](D:/yanjiu1/keyan1/results/phase5/prerequisites_20260912/replays/20260910T232224409038Z_4712f90d/20260912T092708946460Z_2409e0de/validation.json)。重放重建原局部决策、记忆、物理过程并核对原实跑 SUMO 读回，没有重启 SUMO。

## 输出重定向与失败保留

实际检查发现 `run.py verify` 会覆写既有阶段0/1核验 JSON，而标准重放会更新阶段4的输出索引。为满足本审查不得改变旧证据的写入边界，经主任务确认，使用 [audit_entry.py](D:/yanjiu1/keyan1/results/phase5/prerequisites_20260912/audit_entry.py) 经 `runpy` 执行原 `run.py`，仅重定向 `research.common.write_json` 的核验输出和阶段4重放函数已有的 `base` 参数。模型、控制、评估和重放数值函数没有被替换。不能将该调用描述为完全未经包装的直接 shell 命令。

每次调用的实际命令、原入口参数、UTC时间、日志路径和退出码分别保存为 `*_command.json`，完整输出为同名 `.log`。初次批处理 [summary.json](D:/yanjiu1/keyan1/results/phase5/prerequisites_20260912/summary.json) 保留 `all_command_exit_codes_zero=false`，最终汇总单独写入，不抹去失败：

- 首次补充重放与普通重放共用审查输出目录，竞争 `latest.json.writing` 导致启动时 `PermissionError`，进程退出1。初次ID为 `20260912T092616562829Z_be71230e`；由于异常发生在 `RunRecord.__enter__`，其原 `validation.json` 停留在 `running`，进程实际上已结束。该记录和 [失败日志](D:/yanjiu1/keyan1/results/phase5/prerequisites_20260912/sampling_replay.log) 原样保留，最终汇总明确标注，不能将其当作仍在运行或算法失败。随后按固定源ID分开审查输出目录，补充完整重试通过。
- 辅助几何脚本首次把源码公式的零基行索引误写为24/26，断言失败、退出1。按实际一基行号26/28更正为25/27后通过；源文件和几何公式未改。失败脚本、失败日志和退出码保存在 `geometry_attempt1_executed.py`、`geometry_attempt1.log` 与 `geometry_attempt1_command.json`。

重放可复用以下命令；每次都会创建新的重放ID，固定源运行不变。再次运行完整审查脚本或辅助日志入口时应使用新的审查目录/尝试名；保留目录的同名日志覆盖会被拒绝。

```powershell
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S results/phase5/prerequisites_20260912/audit_entry.py phase4-replay --run-dir results/phase4/runs/20260910T232224392627Z_ab0de887
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S results/phase5/prerequisites_20260912/audit_entry.py phase4-replay --run-dir results/phase4/completion_20260911/sampling_runs/20260910T232224409038Z_4712f90d
```

## 六车几何结论

`formationControl.m:7` 明确 `gap=15`；`formationControlNormal.m:24–28` 对完整两层、三车道的6个目标给出横向位置 `j×laneWidth+6`，奇数车道纵向 `xFront−2i×gap`、偶数车道再减一个gap。以源码 `xFront=1`、`laneWidth=3.3` 代入，两层三车道纵向坐标分别为 `[-29,-44,-29]` 和 `[-59,-74,-59]` m。同车道对应参考点间距均为30 m，邻接车道错位均为15 m。

此核对是离线源码公式转写和算术断言，没有运行 MATLAB 的全局分配/路径规划，也不将其绝对原点、目标槽位或编号传给在线策略。等长4 m车身对应理想同车道净空26 m；在中间格点插入后前后静态净空各11 m，仅是几何数值，不证明动态插入安全。`Three_Vehicle_Control.m` 的另一路 `vehicle_Gap/2` 不改变本主链定义。

## 保留的未通过条件与下一入口

原严重急刹压力案例仍以失败前缀重放，重放通过没有关闭碰撞或舒适失败。前轮已登记的任意突然横向动作、执行中没有普遍安全回退保证以及有限步长实际jerk结论边界继续有效；本审查没有证明连续时间有界jerk、全局收敛、串行稳定、交通收益或能耗改善。

下一入口仍是阶段5：本车状态、有限局部观测和本车记忆下的R1–R5；3/6/12车冻结随机初态，实际速度扰动，参考车进出观测范围，独立形成/保持/失效退出/恢复检测，保留失败和未完成。禁止真类型、真实ID优先权、全局槽位/共同领航车、隐含让行以及中心调度补救。阶段5实现后的开关恢复、信息隔离、实际jerk/车身几何、数值重放及受影响阶段4回归必须另有新证据；阶段6与正式矩阵未由本报告放行。

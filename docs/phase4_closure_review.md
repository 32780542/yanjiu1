# 阶段4最后封存缺口独立复核

2026-09-11。依据第六版研究规格、`phase4_completion_plan.md`、`phase4_completion_evidence_review.md` 与 `phase4_completion_maneuver_review.md`，按 requesting-code-review 和 verification-before-completion 复核最后一项重要证据缺口。本轮没有可比较的有效 Git 提交；比较固定运行的冻结文件及 SHA-256，不虚构提交差异。

本轮只读生产代码、配置、测试和运行证据。写入限于本文件和 `results/phase4/closure_20260911/review/`。本报告专门审查追加封存、共享输入来源和随后重放；前轮物理实现与完整套件审查仍以其原报告为准。

**封存及共享输入检查、固定目录整包标准重放、最终验收文档终审均通过，前轮唯一重要证据封存问题已关闭。** 本轮未发现新的未处理严重或重要问题；阶段4可按已登记小案例和数值门槛完成M1，后续限于阶段5小规模机制研究。独立交付清单的最终生成与冻结由主任务在本审查停止写入后完成。

## 封存前后核验

目标补充运行：`results/phase4/completion_20260911/sampling_runs/20260910T232224409038Z_4712f90d`。独立封存前清单由前轮审查于 **2026-09-10 23:28:33.535982 UTC** 记录，当时生产者已经完成；该清单的 SHA-256 为 `44a863cf195932d67ffe2735312313e65a2812d1b0f4e7741fe385119d0a05b0`。

本轮逐文件复算得到：

- 封存前156个既有文件中，155个字节不变，仅 `metadata.json` 改变；没有删除既有文件。
- 新增文件严格为 `sealer_snapshot.py` 与 `evidence_hashes.json`。新清单覆盖157个文件，所有哈希匹配，除清单本身外没有未登记文件。
- 从当前元数据移除新增的 `run_id` 与 `post_run_sealing`，按原 Windows CRLF 与原 JSON 格式序列化后，精确恢复原 SHA-256：`0eec532e6ee516ac56070dcbda0be54233ab228f1d7a30d8fea7af9bd7f70bed`。因此原元数据内容没有夹带修改，轨迹、初态、脚本、指标和原驾驶结果均保留。
- `sealer_snapshot.py` 与实际封存入口 `results/phase4/completion_20260911/seal_sampling.py` 字节相同。`driver_snapshot.py` 与补充入口、封存前清单及新增元数据中的驱动哈希均一致。
- 元数据明确记录追加封存时间 **2026-09-11 12:00:53.970661 UTC**，晚于独立封存前观察；没有把该步骤描述为生产启动或运行结束时已经存在。

证据：[独立封存和共享输入审计](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/seal_and_shared_input_audit.json)。复算入口为 [audit_closure.py](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/audit_closure.py)。首次辅助审计把 JSON 内存文本按 LF 编码，无法匹配原 Windows 文件；定位 CRLF 后精确匹配，首次失败日志保留在 `review/audit_and_replay.log`，没有改动被审计文件。

封存元数据中的 `producer_invocation` 明确标记为封存时根据已授权调用补记的命令信息。本次文件审计能够核对保存的驱动源码及数值结果，不独立认证当时进程的实际命令行，也不追溯证明独立观察之前已有防修改保护。不得将事后封存写成原始运行从启动起就具备完整哈希链。

## 共享输入与冻结版本

补充包**没有自己的 `input_snapshot`**。共享输入实际保存在普通固定运行：

`results/phase4/runs/20260910T232224392627Z_ab0de887/input_snapshot/`

该目录的5个文件为第六版研究规格、参数登记表、阶段3验收、阶段4实现计划和 `scenarios/cai2024/bottleneck.net.xml`。5项均受到普通包的原封存清单覆盖且重新计算一致。普通包共270项封存记录全部匹配，无额外未登记文件。

普通包、补充包记录的77个源码/配置哈希完全相同，各自 `source_snapshot` 与当前工作源码也逐项相同；完整当前清单无额外源码/配置文件。补充6个变体的案例、初态、模型参数及道路几何与普通包对应原案例相同。对照中的参数差异只限预声明的控制/感知周期0.1 s→0.05 s，不能把共享输入描述为补充包原本自带的文件。

历史保护另行复核：原阶段4失败运行 `20260910T185443571873Z_3776ab63` 的269项、固定阶段3运行 `20260910T163533938451Z_2dcd59f7` 的242项均无哈希差异。证据：[源码清单与历史保护](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/historical_protection_and_source_inventory.json)。

## 标准重放

运行登记解释器 `C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe -I -B -S`，直接调用未修改的 `experiments.phase4_replay.replay_run`，仅将其既有 `base` 参数设为审查目录，避免覆盖主任务的重放索引。已经先核对当前研究源码与目标 `source_snapshot` 完全相同；这与标准 `run.py phase4-replay` 使用相同重放函数。

固定重放目录：`results/phase4/closure_20260911/review/replays/20260911T120457075743Z_693f1f6d`。过程完整退出0，`validation.json` 的 `status=completed`、`passed=true`、`source_driving_gate_passed=true`。6/6变体共1,410区间、102,000个车辆积分子步全部重放，最大数值差0；588次信息隔离比较通过，9/9类篡改均拒绝。没有证据哈希差异或当前源码差异；本次补充没有固定命令积分细化轨迹，不能把普通包的两份细化轨迹重复计入补充重放。

重放前后整个补充包的逐文件哈希完全一致。证据：[固定重放结果](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/replays/20260911T120457075743Z_693f1f6d/validation.json)、[调用与模块来源](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/standard_replay_summary.json)、[完整日志](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/audit_and_replay_final.log)。

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S results/phase4/closure_20260911/review/audit_closure.py replay
```

重放仅复算局部决策、记忆、物理积分及隔离审计，并核查保存的原始 SUMO 读回；不重新启动 SUMO，也不把原驾驶失败改为成功。

## 结论限制与文档终审

终审覆盖 `phase4_completion_acceptance.md`、当前/历史导航 `phase4_acceptance.md`、`phase5_entry.md`、README、`phase4_model.md`、`phase4_next_entry.md`、`phase4_completion_plan.md` 及第六版规格的当前入口，共8份文件。结论、固定运行来源和下一阶段范围一致，旧9/14验收与早期审查仍明确作为历史记录保留。

使用登记解释器独立读取普通16变体与补充6变体的原始轨迹，重新调用原评估器计算驾驶指标，22个变体均与原保存指标及本轮 `closure_20260911/summary.json` 一致；从子步独立提取的实际零速时刻也一致。两包77份代码/配置与当前完整清单相同，参数登记264行；普通14/14、补充6变体与3项比较、普通90,060子步/补充102,000子步及所有汇总计数相符。压力案例11个碰撞子步与失败状态保留。文档表中的停车、并道、切入、跟踪及步长误差数值与这些保存值在所示精度内一致。

主任务本次141项测试日志为97.402 s、`OK`；基础核验为通过，需求数588/717/830/976。普通阶段4固定重放 `20260911T120126895260Z_f9ce3be5` 和阶段3固定重放 `20260911T120207532541Z_21a47adb` 均保存完成/通过状态并指向所声明的源运行；阶段3仍如实列出阶段4接入产生的3项当前入口代码差异，未把它写成阶段3以来完全没有代码变化。

8份文件共64个本地Markdown链接已核对。唯一缺失为两处指向待主任务最终生成的 `closure_20260911/delivery_manifest.json`，属于明确安排在本审查停止写入后的交付步骤，不计作已验证完成的产物；其余链接均存在。普通包共享输入链接最初误指向普通元数据，已按审查建议改为 `summary.json` 的逐文件映射。新旧运行、补充的事后封存保护起点和共享输入来源没有混淆。

证据：[文档数据与链接最终审计](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/document_data_final_audit.json)、[完整检查日志](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/document_data_final_audit.log)、[复算入口](D:/yanjiu1/keyan1/results/phase4/closure_20260911/review/audit_document_data.py)。全部已执行检查通过，进程退出0；各文档审查时点SHA-256保存在审计JSON中。

最终文本明确保留：14个预声明普通案例与指定采样对照的适用范围、严重急刹压力碰撞失败、执行中无普遍安全回退保证、有限范围理想观测、通信及编队在阶段4关闭、简化运动学和指定积分步长的数值语义。原离线探针不替代真实 SUMO 驾驶证据；指定0.01/0.005 s下实际 jerk 通过不等于连续时间有界或任意步长收敛。阶段5入口仍只安排6车离线几何核对、3/6/12车局部小案例、独立队形检测及成功/失败记录，没有声称编队、串行稳定、交通效率或节能增益已经验证，也未放行正式收益矩阵。

前轮预备筛选诊断 `reason`/`lead_gap_m` 与最终请求含义不一致的非阻塞建议仍保留；本轮未改冻结控制器来消除该建议。

本报告是此次独立审查的最后写入。审查文件已稳定，后续交付清单生成与冻结由主任务负责；本审查不再修改上述文档或审查产物。

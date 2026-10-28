# 阶段2验收报告：连续车辆动力学与SUMO同步

日期：2026-09-10。唯一研究工作目录：`D:\yanjiu1\keyan1`。

**阶段2限定范围的门槛通过，可以进入阶段3有限范围理想观测的小案例开发。** 已补齐上次中断的动力学、同步、独立几何检测、工况、失败记录和重放。这里没有完成NOA、感知适配器、编队、多车交通实验或能耗研究；不宣称完整复现Cai 2024。

最终冻结运行：`20260910T124949249161Z_77673fca`。

- [完整运行汇总](D:/yanjiu1/keyan1/results/phase2/runs/20260910T124949249161Z_77673fca/validation.json)
- [原始运行目录的证据哈希](D:/yanjiu1/keyan1/results/phase2/runs/20260910T124949249161Z_77673fca/evidence_hashes.json)
- [52项自动测试日志](D:/yanjiu1/keyan1/results/phase2/tests_final.log)
- [数值重放日志](D:/yanjiu1/keyan1/results/phase2/replay_final.log)
- [模型、同步语义、假设与门槛](D:/yanjiu1/keyan1/docs/phase2_model.md)

## 1. 前置条件和授权修订

接续任务此前明确授权“继续执行阶段2”，上次失败是会话传输/压缩中断。恢复时25项测试中23项通过、2项因尚未实现simulation/experiments模块失败，证据为 `results/phase2/preflight/resume_tests.log`。没有重建或复制父目录废案。

当前研究规格和入口已包含用户后来批准的有限范围理想观测修订；继续保持无通信、范围外信息隔离、零额外测量延迟，未重新加入遮挡/噪声/漏检。该模块属于下一阶段，尚未实现。

最终运行开始时在独立进程重新执行源码、路网、需求核验：29个只读参考源文件哈希匹配；路网仍为1000 m三车道＋200 m两车道、3.3 m车道宽，连接仅0→0/1→1；四档统一需求逐条重放一致，计划数588/717/830/976。此前原生道路smoke验收仍为通过，它只证明拓扑。最终运行的 `preconditions.json` 保存这些检查与历史smoke run_id。

固定工具实际运行版本为SUMO 1.27.1，TraCI来自同版工具目录。所有新研究代码、日志、临时文件及结果都在keyan1；没有安装或修改外部工具。

## 2. 实际完成的文件

| 类别 | 文件与作用 |
|---|---|
| 接续并修复模型 | `models/vehicle.py`：连续积分、执行器及全速度融合附着投影；保留既有geometry、safety实现并独立审查 |
| 新增同步 | `simulation/__init__.py`、`simulation/external_bridge.py`：逐子步真实性校验、CG转换、单次SUMO推进、精确回验 |
| 新增工况与记录 | `experiments/__init__.py`、`phase2_cases.py`、`offline.py`、`phase2.py`、`records.py`：五个工况、三种步长版本、独立目录、原始日志、负例及重放 |
| 接入工程 | `run.py`新增phase2/phase2-replay；`research/common.py`将models/safety/simulation/experiments纳入哈希；`research/registry.py`纳入phase2登记 |
| 参数 | `configs/phase2.json`：39项模型开发设置和固定门槛；`docs/parameter_registry.csv`与phase0登记摘要重新生成 |
| 必要测试 | 新增/补齐`tests/test_phase2_model.py`、`test_phase2_bridge.py`、`test_phase2_geometry.py`、`test_phase2_offline.py`、`test_phase2_records.py`、`test_phase2_replay.py`、`test_phase2_live.py` |
| 文档 | 本报告、`phase2_model.md`、`phase3_entry.md`、两份独立评审；更新README和阶段2实施清单 |
| 最终证据 | `results/phase2/run_final.log`、`tests_final.log`、`replay_final.log`、`runs/<run_id>/`及独立replays目录 |

完整交付路径与SHA-256见 `results/phase2/delivery_manifest.json`。代码仍保留在现有独立仓库的phase01分支工作区，未提交、未推送。

## 3. 单车工况与真实SUMO结果

五个工况均完成基线、同命令积分步长减半、同跟踪律控制步长减半，共15份离线轨迹；基线和控制半步两套均同步到真实SUMO，共10次单车运行、1320个正常同步区间。初始化单独排除并记录时间偏移。

| 工况 | 最终实测事实 | 结果 |
|---|---|---|
| 恒速10 s | vx=28.8 m/s；解析位置最大误差1.01e−11 m | 通过 |
| 加减速、停车、再启动14 s | 停车段速度0；再启动终速8.947921 m/s；未出现倒车 | 通过阶段2门槛，实际jerk限制见第7节 |
| 恒转角3 s | δ命令0.01 rad；终态yaw=0.03703703686 rad/s，与解析稳态差1.78e−10 rad/s | 通过 |
| 单次换道10 s | 前5 s参考换道；全过程最大误差0.159551 m；10 s终态误差0.028359 m；最大实际ay=0.949880 m/s² | 通过 |
| 跨edge直行7 s | upstream_0→downstream_0；基线物理时刻3.5 s发生转换，横向跳变0 m | 通过 |

换道5 s参考结束时的位置误差另经独立复算为0.044698 m。表中的终态门槛是在10 s、包含额外5 s保持后评估，不能混为“5 s时误差0.028359 m”。有实际转角、vy和yaw响应，真实状态不是直接设置到参考轨迹。

10次SUMO运行中，位置回验最大差5.68e−14 m、航向差3.69e−16 rad、时刻差6.39e−14 s；速度与区间加速度回验差均为0。跨edge后仍按同一积分状态接续。正常工况未报告碰撞/传送；独立车身及子步道路扫掠均无越界，轴力附着、执行器jerk、转角速率和小侧偏区检查均无违规。最终SUMO日志检索未发现Warning/Error。

这些误差说明接口忠实显示积分状态，不表示积分模型与实车误差近于零。SUMO的区间加速度与物理模型瞬时加速度分别保存，没有伪造二者相等。

## 4. 步长减半、重放及负例

| 对照 | 位置最大差 | 航向最大差 | 原定门槛 |
|---|---:|---:|---|
| 同命令，积分0.01→0.005 s | 1.681e−5 m | 1.824e−9 rad | 0.02 m / 0.002 rad |
| 同跟踪律，控制/同步0.1→0.05 s | 0.038032 m | 0.001759 rad | 0.15 m / 0.02 rad |

分别对齐全部共同子步时点，两个最大值不一定发生在同一工况。不存在通过只比较终态隐去中途误差。

最终独立数值重放检查15份轨迹、17600个子步，每个状态字段重放差为0；命令、初态链和所有诊断字段一致；原始证据哈希无不匹配，当前代码/配置与运行时哈希无差异。重放使用冻结参数和命令，未再次启动SUMO。原始SUMO读回文件作为已执行证据保留并校验哈希。

故障注入实际检出：15 m瞬移、重复积分、缺失子步、两端安全但中间发生的旋转矩形碰撞、两端在路内但旋转中间越界、质心尚在上游但车身已进入终止车道缺口。额外测试检出细小子步篡改、错误命令/诊断、截断日志、错误读回时刻/姿态/速度/区间加速度及启动依赖失败。故障注入的“检出通过”与正常工况无违规分别记账。

## 5. 参数变化及保留的失败

现有质量1500 kg、惯量2500 kg·m²、轴距2.7 m、整轴刚度80000 N/rad、μ=0.9、执行器时间常数0.2/0.15 s以及原跟踪增益0.6/1.5均未调改。

最终登记214项：文献18、只读源码67、主配置44、拓扑测试37、敏感性候选9、phase2设置39。相对历史174项的差额来自既有理想观测修订的主层净增1项，以及新增phase2层39项；不能写成40项新物理参数。phase2中23项为中断前已声明设置，16项是首版验收代码内数值原值抽入配置；全部来源及状态明确，无缺失字段。

| 开发问题 | 实测/处理 | 保留证据 |
|---|---|---|
| 首版换道跟踪未过门槛 | 峰值0.652939 m；用已有2DOF与转向滞后参数推导低频参考前馈，未放宽0.35 m门槛 | `preflight/offline_first_implementation.txt`、`offline_model_feedforward.txt`、`offline_final_summary.json` |
| 低速融合绕过附着 | 原例μg=8.829但合加速度8.831275 m/s²；改为融合请求轴力统一投影，反例与可达轨迹复查通过 | `docs/phase2_dynamics_review.md`、`tmp/review_dynamics/` |
| 初始化失败可残留旧成功 | 每次尝试在读配置之前建立独立记录，初始化异常写failed | `preflight/initialization_failure_red.log`及green |
| 早期异常缺详细诊断 | metadata、TraCI载入、子工况生命周期纳入异常保护 | `preflight/early_diagnostics_red.log`及green |
| 门槛失败结果可能被异常覆盖 | 在记录上下文结束后再返回非零退出；cases/faults及哈希完整保留 | `preflight/gate_preservation_green.log`、`docs/phase2_sync_review.md` |

先前会话与开发失败日志未被删除。评审中的一次同进程测试曾使前置路径检查临时失败；该事实和修复隔离方式见同步评审报告。最终前置核验及完整运行在独立干净进程重做并通过。开发失败日志不是交通收益实验，不能择取其中有利结果做论文对比。

## 6. 实际运行和复跑命令

在keyan1运行，PowerShell包装器固定使用登记的解释器：

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
.\scripts\run.ps1 registry
.\scripts\run.ps1 verify
.\scripts\run.ps1 phase2
.\scripts\run.ps1 phase2-replay
.\scripts\run.ps1 test
```

本轮实际执行对应的 `python -I -B -S run.py <command>`，最终run/replay/test日志均保存，52项测试全部通过。只重放本报告固定运行可执行：

```powershell
python -I -B -S run.py phase2-replay --run-dir results/phase2/runs/20260910T124949249161Z_77673fca
```

最终运行目录包含 `metadata.json`、`preconditions.json`、`source_snapshot/`、`input_snapshot/`、每工况 `case.json`、三变体 `metadata.json/trace.jsonl/validation.json`、两套SUMO的命令/初始时间偏移/逐区间readback/日志、`faults.json`、完整validation及证据哈希。运行和重放各有独立latest指针，不覆盖旧目录。

## 7. 未通过或尚未覆盖的条件

1. **停车处实际jerk舒适性没有通过。** 非负速度约束将制动速度导数切为零，基线最大采样实际纵向jerk约300 m/s³；执行器jerk仍约2 m/s³。积分减半会改变该尖峰幅度，不能用位置收敛替代jerk收敛。本阶段未以实际停车jerk≤2作为通过门槛，后续NOA舒适性必须单独处理。
2. 当前前馈仅在固定高速、小侧偏、未饱和工作点做一阶低频补偿；还不是全速度NOA控制器。线性轮胎、静态轴荷、简化纵横耦合和低速等效力都未做实车标定。
3. 子步扫掠对线性插值姿态保守检测，未证明任意未采样非线性轨迹的连续时间安全。单车正常工况零碰撞不能外推到拥挤交通。
4. 多车统一时钟、感知隔离、NOA跟驰/并道/应急、局部交错和公平交通对比均未实现或验收。M1（阶段0–4）仍未完成，因此未运行正式批量实验，没有交通效率或节能提升结论。

下一阶段按 [phase3_entry.md](D:/yanjiu1/keyan1/docs/phase3_entry.md) 实现有限范围理想观测及信息不变性审计，继续保留上述限制和失败，不引入通信或隐藏真值补救。

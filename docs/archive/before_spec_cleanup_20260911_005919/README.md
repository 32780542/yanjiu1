# keyan1：无通信 NOA 交错编队研究

阶段3已完成有限范围理想观测、局部信息隔离、统一多车时钟和可重放日志，见[验收报告](D:/yanjiu1/keyan1/docs/phase3_acceptance.md)。按用户2026-09-11要求，主车辆运动已简化为运动学模型与分段二次贝塞尔，不再需要质量、惯量或刚度。完整NOA和交错控制尚未实现，没有效率或节能改善结论。

当前感知要求（2026-09-10更新）：只做有限范围内理想观测，范围内允许状态精确、额外测量延迟为零；不考虑遮挡、噪声、漏检或传感器失联。无通信、局部信息隔离和连续车辆动力学要求继续适用。

## 研究入口

- [完整科研方案与分阶段 AI 执行步骤](D:/yanjiu1/keyan1/docs/noa_staggered_formation_research_plan_2026-09-10.md)
- [MATLAB 源码参数登记表](D:/yanjiu1/keyan1/docs/cai2024_source_parameters_2026-09-10.json)

## 工作目录约束

唯一研究根目录为 `D:\yanjiu1\keyan1`。所有新代码、配置、文档、临时文件、日志和仿真结果均写入本目录。父目录已有研究代码属于废案，不复制、不导入、不作为测试或结论依据。

允许的外部只读输入为用户提供的两篇 PDF 和 `D:\matlab_huipu_2000` 的论文相关改编源码。已安装的 `D:\yanjiu1\SUMO\sumo-1.27.1` 与 `D:\yanjiu1\SUMO-MCP-Server` 可作为工具依赖使用。源码中的参数和方法均须区分与论文一致的内容、改编差异和待补数据。

## 下一阶段

下一步为[阶段4：独立NOA基线](D:/yanjiu1/keyan1/docs/phase4_entry.md)，继续使用已验证的局部观测、统一时钟和[简化运动模型](D:/yanjiu1/keyan1/docs/kinematic_motion.md)。

## 本轮产物

- [阶段3验收与重放入口](D:/yanjiu1/keyan1/docs/phase3_acceptance.md)
- [二次贝塞尔实际轨迹与误差](D:/yanjiu1/keyan1/results/phase3/bezier_motion.png)
- [局部观测和统一时钟语义](D:/yanjiu1/keyan1/docs/phase3_model.md)

- [阶段2验收与完整结果入口](D:/yanjiu1/keyan1/docs/phase2_acceptance.md)
- [连续动力学、前馈跟踪、同步语义与限制](D:/yanjiu1/keyan1/docs/phase2_model.md)
- [阶段0–1验收及完整文件清单](D:/yanjiu1/keyan1/docs/phase01_acceptance.md)
- [当前参数登记表](D:/yanjiu1/keyan1/docs/parameter_registry.csv)
- [论文对齐与补充假设](D:/yanjiu1/keyan1/docs/paper_alignment.md)
- [源码改编差异审计](D:/yanjiu1/keyan1/docs/source_adaptation_audit.md)
- [标注拓扑图](D:/yanjiu1/keyan1/results/phase1/topology.png)
- [SUMO实际瓶颈截图](D:/yanjiu1/keyan1/results/phase1/gui/sumo_bottleneck_zoom.png)

## 运行

在 `D:\yanjiu1\keyan1` 的 PowerShell 中按下列顺序运行。默认解释器和SUMO由`configs/tools.json`固定；不使用PATH中的旧SUMO0.32.0。

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
.\scripts\run.ps1 build
.\scripts\run.ps1 verify
.\scripts\run.ps1 environment
.\scripts\run.ps1 mcp
.\scripts\run.ps1 smoke
.\scripts\run.ps1 screenshot
.\scripts\run.ps1 test
.\scripts\run.ps1 phase2
.\scripts\run.ps1 phase2-replay
.\scripts\run.ps1 phase3
.\scripts\run.ps1 phase3-replay
```

如系统脚本策略不允许，可直接调用解释器：

```powershell
python -I -B -S run.py verify
```

其余子命令相同。`phase2`执行五个单车工况及步长细化，`phase2-replay`数值重放最近一次完整记录；指定历史运行可用 `python -I -B -S run.py phase2-replay --run-dir results/phase2/runs/<run_id>`。每次尝试独立建档，异常和门槛失败均保留，失败退出码非零。`-I -B -S`禁用环境搜索路径、字节码写入及`.pth`自动处理，入口仅显式加载项目和已登记依赖。已安装工具包版本见`requirements-tooling.txt`和`results/phase0/environment.json`，本轮没有安装或修改外部依赖。若将来必须安装，虚拟环境、缓存和临时文件也必须放在keyan1。

`build`只生成四档600 s需求，不运行实验矩阵。`smoke`只用1250 veh/(lane·h)的前60 s计划，加一个单独终止车道探针，并最多排空至240 s。各档CSV为共同到达计划；`.types.csv`是真实类型的离线初始化标签，不可进入邻车观测；`.rou.xml`为原生拓扑测试适配，不是NOA实现。所有方法后续必须复用相同需求文件。

运行日志保存在`results/phase0`、`results/phase1`与`results/phase2`；阶段2每次尝试在runs或replays下独立建档，最终验收引用固定run_id。冒烟重复运行前，旧目录会归档至`results/phase1/smoke_history`；当前结果先标记未完成，失败会留下明确状态与traceback；其他已知失败证据另存带`initial_failed`或`red`的文件。研究代码及配置有逐文件SHA-256记录，当前git分支为`phase01`，尚未提交。没有借用父目录测试基线。

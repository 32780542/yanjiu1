# keyan1：无通信 NOA 交错编队研究

本项目从零研究仅依靠自车传感器的多车道交错编队及三变二瓶颈通行。阶段0–1已建立独立工程、参数登记、3→2路网和统一随机需求，并通过原生SUMO小规模道路核验。尚未实现连续车辆动力学、感知模拟、NOA或交错控制，也没有效率或节能提升结论。

## 研究入口

- [完整科研方案与分阶段 AI 执行步骤](D:/yanjiu1/keyan1/docs/noa_staggered_formation_research_plan_2026-09-10.md)
- [MATLAB 源码参数登记表](D:/yanjiu1/keyan1/docs/cai2024_source_parameters_2026-09-10.json)

## 工作目录约束

唯一研究根目录为 `D:\yanjiu1\keyan1`。所有新代码、配置、文档、临时文件、日志和仿真结果均写入本目录。父目录已有研究代码属于废案，不复制、不导入、不作为测试或结论依据。

允许的外部只读输入为用户提供的两篇 PDF 和 `D:\matlab_huipu_2000` 的论文相关改编源码。已安装的 `D:\yanjiu1\SUMO\sumo-1.27.1` 与 `D:\yanjiu1\SUMO-MCP-Server` 可作为工具依赖使用。源码中的参数和方法均须区分与论文一致的内容、改编差异和待补数据。

## 下一阶段

下一步为[阶段2：连续动力学与状态同步](D:/yanjiu1/keyan1/docs/phase2_entry.md)。先完成单车积分、转向和跨edge一致性，再进入感知和NOA阶段。

## 本轮产物

- [阶段0–1验收及完整文件清单](D:/yanjiu1/keyan1/docs/phase01_acceptance.md)
- [最终参数登记表（174项）](D:/yanjiu1/keyan1/docs/parameter_registry.csv)
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
```

如系统脚本策略不允许，可直接调用解释器：

```powershell
python -I -B -S run.py verify
```

其余子命令相同。`-I -B -S`禁用环境搜索路径、字节码写入及`.pth`自动处理，入口仅显式加载项目和已登记依赖。已安装工具包版本见`requirements-tooling.txt`和`results/phase0/environment.json`，本轮没有安装或修改外部依赖。若将来必须安装，虚拟环境、缓存和临时文件也必须放在keyan1。

`build`只生成四档600 s需求，不运行实验矩阵。`smoke`只用1250 veh/(lane·h)的前60 s计划，加一个单独终止车道探针，并最多排空至240 s。各档CSV为共同到达计划；`.types.csv`是真实类型的离线初始化标签，不可进入邻车观测；`.rou.xml`为原生拓扑测试适配，不是NOA实现。所有方法后续必须复用相同需求文件。

运行日志保存在`results/phase0`、`results/phase1`。冒烟重复运行前，旧目录会归档至`results/phase1/smoke_history`；当前结果先标记未完成，失败会留下明确状态与traceback；其他已知失败证据另存带`initial_failed`或`red`的文件。研究代码及配置有逐文件SHA-256记录，当前git分支为`phase01`，尚未提交。没有借用父目录测试基线。

# 阶段0与阶段1验收报告

日期：2026-09-10。研究根目录：`D:\yanjiu1\keyan1`。

**阶段0–1基础门槛通过，可以进入阶段2单车连续动力学开发。** 本轮仅实现工程基础和SUMO原生道路验证；没有完成NOA、感知模拟或编队算法，没有正式交通效率、能耗对比，也不宣称完整复现Cai 2024。

## 1. 已修改和新增的文件

原有文件仅更新 `README.md`。原研究规格和 `docs/cai2024_source_parameters_2026-09-10.json` 保持原样。

| 类别 | 实际文件 |
|---|---|
| 独立入口/依赖 | `run.py`、`scripts/run.ps1`、`scripts/mcp_server_entry.py`、`requirements-tooling.txt`、`.gitignore`；新建独立`.git`，分支`phase01` |
| 配置 | `configs/tools.json`、`paper_reference.json`、`no_comm_main.json`、`topology_smoke.json`、`sensitivity.json` |
| 新实现 | `research/common.py`、`registry.py`、`network.py`、`demand.py`、`verify.py`、`environment.py`、`smoke.py`、`screenshot.py`、包初始化文件 |
| 局部接口 | `perception/contracts.py`及包初始化文件；仅接口，没有控制器 |
| 测试 | `tests/test_foundation.py`、`tests/test_artifacts.py` |
| 最终文档 | `docs/parameter_registry.csv`、`paper_alignment.md`、`source_adaptation_audit.md`、`phase01_implementation_plan.md`、本报告、`phase2_entry.md` |
| 路网 | `scenarios/cai2024/bottleneck.nod.xml`、`.edg.xml`、`.con.xml`、`.net.xml` |
| 统一需求 | `scenarios/cai2024/demand/q{1250,1500,1750,2000}_seed20260910.csv`、`.types.csv`、`.rou.xml` |
| 小测试配置 | `scenarios/cai2024/smoke_demand.csv`、`smoke.rou.xml`、`smoke.sumocfg`、`empty.rou.xml`、`mcp_probe.sumocfg`、`gui_probe.sumocfg` |
| 溯源/环境 | `results/phase0/source_hash_check*.json`、`paper_hashes.json`、`environment.json`、`*_version.json`、`mcp_probe.json`、MCP日志和测试日志 |
| 拓扑/需求证据 | `results/phase1/netconvert.json`、`network_validation.json`、`demand_manifest.json`、`foundation_verification.json`、`topology.png` |
| 实际SUMO截图 | `results/phase1/gui/sumo_topology_full.png`、`sumo_bottleneck_zoom.png`、`capture.json` |
| 原生通行日志 | `results/phase1/smoke/run_metadata.json`、`validation.json`、`departures.csv`、`transitions.csv`、`conservation.csv`、`state_trace.csv`、`tripinfo.xml`、`summary.xml`、`fcd.xml`、`lanechanges.xml`、`sumo.log`、`stdout.log` |
| 临时论文证据 | `tmp/papers/cai2024.txt`、`cai2022.txt`及关键页PNG；没有写回原PDF |

逐文件路径、大小及SHA-256见 `results/phase01_file_manifest.json`。工作保留在指定目录，未提交、未推送，无父工程基线或依赖关系。

## 2. 参数、资料与环境门槛

| 检查 | 实际结果 | 证据 |
|---|---|---|
| MATLAB参考源码变化 | 29/29 SHA-256一致，无新增变化需要补审 | `results/phase0/source_hash_check.json` |
| 两篇论文 | 原始PDF路径/哈希已登记，2024 p3–4 Table I/Fig.4和2022 p13 Table2已视觉复核 | `paper_hashes.json`、`paper_alignment.md` |
| 参数登记 | 174行：paper18/source67/main43/smoke37/sensitivity9；活动项无缺失来源字段 | `parameter_registry.csv`、`parameter_registry_summary.json` |
| 工具版本 | Python3.12.9，SUMO/netconvert/GUI/TraCI/sumolib1.27.1，MCP SDK1.27.0，Pillow11.0.0，pywin32 311 | `environment.json` |
| 时间单位 | getDeltaT=0.1 s；推进一次实测增加0.1 s | `environment.json` |
| MCP | stdio initialize/list_tools/get_sumo_info/connect/step/query/disconnect均成功；查询time=0.1 | `mcp_probe.json`；公开工具11个 |
| 路径隔离 | `-I -B -S`、禁用`.pth`；研究入口未载入父研究路径 | `foundation_verification.json`、隔离回归测试 |
| 局部接口 | 冻结slots数据类，无邻车类型/全局表/共同领航车/他车计划/全局槽位字段 | `perception/contracts.py`和测试 |

缺失车宽/轴距/质量/轮胎参数以假设补齐：1.8 m/2.7 m/1500 kg，I_z=2500 kg·m²，C_f=C_r=80000 N/rad（整轴），执行器与感知假设见登记表。它们尚未通过动力学/实车标定。HBEFA3/PC_G_EU4仅为显式候选通用类别，本轮能耗分析关闭。

## 3. 路网验收

| 物理车道 | 起终点x（m） | 中心y（m） | 宽度（m） | SUMO长度 / 几何长度（m） |
|---|---|---|---|---|
| upstream_0 | 0→1000 | 1.65 | 3.3 | 1000 / 1000 |
| upstream_1 | 0→1000 | 4.95 | 3.3 | 1000 / 1000 |
| upstream_2 | 0→1000 | 8.25 | 3.3 | 1000 / 1000 |
| downstream_0 | 1000→1200 | 1.65 | 3.3 | 200 / 200 |
| downstream_1 | 1000→1200 | 4.95 | 3.3 | 200 / 200 |

仅两个连接：`upstream_0→downstream_0`、`upstream_1→downstream_1`，无内部合流连接，也没有2→1的跨edge连接。保留车道中心线无横移。五条lane均显式speed=33.3 m/s。负例测试能抓住错误宽度、长度、错移中心线、非法2→1及丢失连接。

`netconvert`输入是本工程新建PlainXML，未复用MATLAB的3→3 net.xml。实际GUI截图和从生成net提取的标注图均已检查；原始GUI全路截图因1200 m纵横尺度差异，车道很窄，瓶颈放大图与标注图用于补充识别。

## 4. 统一随机需求

固定种子20260910，需求文件覆盖`[0,600)` s；每0.1 s、每入口车道一次独立Bernoulli试验。q单位为veh/(lane·h)，`p=q×0.1/3600`。三条入口车道合计期望流率是3q。

| 每车道q | 三车道合计q | 每步每车道p | 600 s计划数lane0/1/2 | 合计 |
|---|---|---|---|---|
| 1250 | 3750 | 0.0347222222222 | 200 / 198 / 190 | 588 |
| 1500 | 4500 | 0.0416666666667 | 246 / 236 / 235 | 717 |
| 1750 | 5250 | 0.0486111111111 | 285 / 278 / 267 | 830 |
| 2000 | 6000 | 0.0555555555556 | 324 / 342 / 310 | 976 |

这些是随机计划数，不是实际进入数，也不要求它们恰等于期望625/750/875/1000。全部逐条重生成一致，XML的ID/时刻/车道与CSV一致；类型流与到达流分离，改变MPR不改变到达，算法不参与生成器。同种子跨q共用随机试验且形成嵌套集合，是明确声明的共同随机数设计，不是四档独立重复样本。没有运行四档600 s仿真。

## 5. 实际原生SUMO小测试

只模拟1250档前60 s的47辆需求车，加1辆在62 s于上游x=850 m/lane2放入的低速终止车道探针；探针与入口需求分别记账，不用于未来交通指标。

| 验收项 | 实测 |
|---|---|
| 已出发/已到达 | 48 / 48（含1探针） |
| 未插入/未完成 | 0 / 0 |
| 排空通知时刻 | 100.4 s，上限240 s；结束原因demand_drained |
| 碰撞车辆报告/开始传送 | 0 / 0 |
| 上游2→1并道 | 17次（含探针） |
| 合法跨edge通行 | 48次，全部0→0或1→1 |
| 跨edge最大横向跳变 | 0 m |
| 全程最大单步横向位移 | 0.11 m，dt=0.1 s |
| 最大入口等待 | 5.0 s，逐车计划/实际出发与tripinfo一致 |
| 逐步车辆守恒 | 全部成立 |

有17辆lane2出发车（含探针）都先在上游完成车道编号2→1转换，再通过保留连接。TraCI入口和跨edge日志给出实际坐标。`arrival_s`是tripinfo事件时间；`arrival_notification_time_s`保留通知时间，不能把晚一个步长的通知当真实旅行时间结束。SUMO出口位于1200 m，未使用源码1190 m完成标志。

碰撞计数为SUMO原生检测报告，不是自建连续二维安全证明。全程运动来自原生IDM/LC2013，用途严格限定道路测试。下一阶段的车辆运动必须改为外部连续动力学积分，moveToXY只同步。

## 6. 运行命令和测试

本机已实际运行以下等效命令；PowerShell包装器使用`configs/tools.json`的绝对解释器路径：

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

直接命令形式是 `python -I -B -S run.py <子命令>`。netconvert精确参数保存在`results/phase1/netconvert.json`；SUMO命令、代码/配置/路网/需求哈希保存在`smoke/run_metadata.json`。

12项自动测试通过，日志为`results/phase0/tests_final.log`。覆盖概率单位、需求重放和类型独立性、拒绝外部输出路径、禁用`.pth`、局部接口字段、拓扑五种负例、四档计划完整性、真实通行映射、到达时间、失败记录及阶段状态。测试使用新工程数据，未读取父研究代码作基线。

独立代码评审发现并修复了一项P2问题：冒烟异常时旧passed=true可能残留。新增启动失败/错误dt故障注入测试先失败再通过；每次运行立即写未完成状态，异常保存失败原因与traceback，旧目录归档至`results/phase1/smoke_history`，本次validation与metadata共享run_id。真实小案例重跑后仍48/48排空。

最初无实现的失败日志、路径污染失败、MCP工具名失败、到达偏差回归失败和GUI异步截图失败均保留并记录原因；当前通过文件与失败记录区分命名。未以自动修复路网、隐藏传送或删去失败车辆掩盖异常。

## 7. 下一阶段与限制

入口为 `docs/phase2_entry.md`：独立实现纵向/转向执行器、2-DOF单轨、低速处理、刚度/附着约束、二维车身、CG/前保险杠及角度转换和单次积分的SUMO同步；先单车与跨edge，再步长减半核验。

后续范围更新（2026-09-10）：按用户要求，阶段3只需有限范围内的理想观测过滤和动作不变审计，取消遮挡、测量噪声、额外感知延迟、漏检与传感器失联要求。理想观测模块仍未实现；阶段4 NOA基线未做；阶段5编队未做。当前接口字段测试不能替代这些门槛。源码的全局分组/车型标签/计划/领航车/槽位不得进入以后控制器。车辆动力学与执行器要求保留，M1（阶段0–4）尚未完成，因此不运行正式大批量实验。本报告此前的运行结果属于阶段0–1历史记录；当前参数以重新生成的登记表为准。

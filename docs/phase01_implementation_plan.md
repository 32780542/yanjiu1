# 阶段 0–1 实施计划

依据已获用户授权的 `docs/noa_staggered_formation_research_plan_2026-09-10.md`，在指定目录内顺序执行，不建立指向父工程的工作树。使用 writing-plans、executing-plans 和 verification-before-completion 工作流。

目标：建立可审计的参数、环境、感知接口契约和 3→2 路网及共同随机需求；本轮不实现 NOA 控制、编队或动力学。

架构：`run.py` 是隔离入口；`research/` 实现参数读取、路网及需求构建、核验与工具桥接；`perception/contracts.py` 只定义冻结的局部数据契约。SUMO 原生运动仅供道路冒烟测试。所有输出路径必须经过研究根目录检查。参数按 paper_reference/source_snapshot/no_comm_main/sensitivity/topology_smoke 分层登记。

技术：Python 3.12.9 标准库、SUMO/TraCI/sumolib 1.27.1、MCP 1.27.0、Pillow（拓扑图）；`python -I -B -S run.py` 禁用环境模块路径和外部字节码写入。

- [x] 先读取规格 4.3–4.7 与已有 JSON；逐一核对 29 个参考文件哈希。
- [x] 定位只读 PDF，登记 SHA-256，复核 2024 p3–4 Table I/Fig.4 与 2022 p13 Table 2，核对集中信息前提。
- [x] 写入 `tests/test_foundation.py`：拒绝外部输出路径；概率单位；共同随机序列/类型流隔离；恶意路网连接和宽度变动应被检出；局部接口字段限制。先运行缺实现的失败测试，保存日志。
- [x] 创建 `configs/*.json`、参数登记器、独立 git 仓库及固定工具路径；生成 `docs/parameter_registry.csv`。记录所有活动参数的值、单位、来源、位置、状态和理由，源码条目附原 SHA-256。
- [x] 创建 `research/network.py`：从 nodes/edges/connections plain XML 调用指定 netconvert；坐标保留入口 0、瓶颈 1000、出口 1200；五条 lane 的 width=3.3，保留中心线 y=1.65/4.95；禁止 2→1 连接。生成图与机器核验。
- [x] 创建 `research/demand.py`：每 0.1 s 每车道独立 Bernoulli；q=1250/1500/1750/2000、seed=20260910、600 s 计划；到达/类型随机流分离，类型仅离线标签。同方法共用完全相同的文件。冒烟仅使用最低档前 60 s，并增加独立终止车道探针。
- [x] 创建 `research/smoke.py`：TraCI 只读采集原生运动；记计划/实际出发、等待、lane 过渡、碰撞、传送、守恒、结束原因；保存配置及代码哈希；排空上限 240 s，超限算失败。
- [x] 创建 `research/environment.py` 与 MCP stdio 启动器：探测真实版本、模块路径、getDeltaT 秒值；MCP initialize/list_tools/get_sumo_info/connect/step/disconnect，所有工作目录和日志在 keyan1。不得使用含 --random 的 MCP run_simple_simulation 作为随机需求实验入口。
- [x] 运行 `python -I -B -S run.py test`、`build`、`verify`、`environment`、`mcp`、`smoke`；对拓扑做断开连接、宽度错误、非法 2→1、错移中心线等负例验证。
- [x] 输出 `docs/paper_alignment.md`、`docs/source_adaptation_audit.md`、`docs/phase01_acceptance.md`、`docs/phase2_entry.md`，更新 README。保留失败记录，不进行批量性能试验。

命令均在 `D:\yanjiu1\keyan1` 下通过 `powershell -NoProfile -File scripts/run.ps1 <command>` 执行。`build` 仅生成四份 600 s 需求文件，不运行四档交通实验。阶段 2 的入口先完成单车动力学与同步测试；阶段 3 才实施感知，阶段 4 才得到 NOA 基线。



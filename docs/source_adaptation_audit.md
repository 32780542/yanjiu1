# 改编源码与新工程差异审计

2026-09-10。依据 `cai2024_source_parameters_2026-09-10.json` 的29个文件逐项SHA-256核验，全部与初始快照一致。当前 `results/phase0/source_hash_check.json` 保存预期/观察哈希、字节数和判定。原始源码保持只读；无源码、MAT、路网或研究结果从父项目导入。本工程只调用允许的 SUMO/SUMO-MCP 安装。

## 差异清单

| 项目 | MATLAB改编源码 | 本工程处理 |
|---|---|---|
| 下游车道数 | New_Edge.m:10–11 为3→3 | 新建3→2，五条物理lane逐项验证 |
| 连接 | 0→0、1→1、2→1 | 删除终止车道出连接，2号车道必须在上游并入 |
| 路网限速 | 41.66 m/s | 主网络33.3 m/s，与论文车辆上界对齐 |
| 优化速度上界 | 33.33 m/s | 论文33.3优先；33.33只存源码层 |
| 车道宽度 | 规划3.3；旧net未显式width | 每个edge及lane均显式3.3，禁止库默认宽度 |
| 坐标 | lane中心y为负值 | 本工程lane0/1/2中心1.65/4.95/8.25 m；保留lane0/1上下游完全相同 |
| 车长 | 两种基础车均4 m | 显式4 m，采用源码补充值 |
| 缺失物理参数 | width、轴距、质量、惯量、轮胎/执行器未确证 | 明确通用假设；见paper_alignment和no_comm_main |
| vType | CAV_ICV、CAV_HDV及异常/侵略/退化类型 | 本轮统一native_probe只测道路；异常/退化分支不迁移 |
| 紧急制动 | emergencyDecel30 m/s² | 保留参考；测试显式10，不能当真实车辆能力证明 |
| 跟驰tau | 0.2/0.65 s | 仅源码参考；原生测试1.2 s，不等于传感器延迟 |
| minGap | 1.5/2 m | 原生测试2.5 m，与编队15 m无关 |
| 自动车加速度 | accel5/decel10 | 论文硬边界保留；原生测试accel2/decel4.5 |
| 发车概率 | 当前Tflow=0.042 | 等效1512 veh/(lane·h)，不标1500；四档按精确q反算 |
| 随机数 | rand(seed=run_i)，占比也由run_i确定；算法分支消耗共享随机流 | 种子20260910；各车道到达和类型流独立；类型/算法不改变到达；不同q采用共同随机数嵌套 |
| 发车截止/终止 | 600 s固定仿真截止 | 600 s为新需求文件范围；本轮只跑前60 s需求并排空，上限240 s |
| 完成标志 | x≥1190 m | 使用经过完整下游的SUMO到达事件，route出口x=1200；保留通知时刻与tripinfo事件时刻 |
| 类型分组/全局表 | mainmain:525–555按类型和全局位置分组 | 不迁移；EgoState+LocalObservation+LocalMemory契约无隐藏字段 |
| 固定切换阈值 | x≥640 m | 参考值；不是论文固定S1/S2，也不是允许的控制输入 |
| 共同规划 | assign/pathRelativeCalculate/CBS等集中机制 | 不作为无通信主线实现 |
| 运动执行 | setSpeed+changeLane，未发现独立横摆/轮胎积分主链 | 本轮原生路测明确标注；下一阶段从连续动力学积分产生运动，moveToXY仅同步 |
| 时间语义 | 旧MATLAB getDeltaT()/1000 | Python1.27.1 getDeltaT实测0.1 s，禁止再除1000 |
| 换道时间 | 命令有效期2 s；GUI启动另有1 s | 本轮测试设置3 s仅做原生连续横移；阶段2独立执行器和转向积分 |
| 优化器 | GPOPS-II/SNOPT | 不作为阶段0–1依赖；未宣称优化等效 |
| 旧MAT变量m | 约0.1824、对应runm概率 | 不作质量使用；三个MAT的初始只读核验结论保留 |
| VSP后处理 | 截断a至[0,3]；停车时0；未按真实公里归一化；只选已完成车辆 | 只留原始登记；legacy_vsp关闭，不称L/100 km，不用于当前能耗结论 |

## 工程环境发现与修正

1. PATH 的 `sumo`/`netconvert` 指向 `C:/Program Files (x86)/DLR/Sumo/bin` 的0.32.0。工程使用 `configs/tools.json` 的1.27.1绝对路径；环境文件记录二进制SHA-256、包版本和模块来源。
2. Python全局 `_editable_impl_sumo_mcp.pth` 会自动加入MCP安装路径。首次隔离检查主动失败，记录保存在 `foundation_verification_initial_failed.json`。入口改为 `-I -B -S`，禁用 `.pth` 自动执行；只显式添加已安装依赖目录。MCP子进程单独加入允许的工具src。未修改全局Python环境。
3. 禁用 `.pth` 后MCP所需Windows支持包不再自动加载，现显式添加pywin32库与DLL目录，包版本311已锁定。MCP完成真正stdio握手及查询/步进/断开。首次把内部辅助函数名当MCP工具名的失败记录已保留；现调用服务公开的 `query_simulation_state(target="simulation")`。
4. SUMO到达通知在推进结束后可晚于tripinfo事件0.1 s。回归测试首先抓住偏差，现 `arrival_s` 使用tripinfo时间，`arrival_notification_time_s`保留通知时刻，检查两者差值在一个dt以内。
5. Windows SUMO GUI截图异步生成。首次检查过早失败的记录保留；现等待PNG完整写出后才改变视口或关闭进程。截图只用于拓扑检查。
6. 独立代码评审用启动失败和错误dt故障注入复现了旧成功记录残留。现每次冒烟先标记running/passed=false，任何异常均保存failed、错误及traceback；先前整份运行目录归档到`results/phase1/smoke_history`。当前validation与metadata共用run_id，避免混用不同次运行。回归测试经历红→绿，真实小案例再次通过。

MCP 的 `run_simple_simulation` 内部带 `--random`，因此本工程不以该工具作为确定性实验入口。MCP验证采用新建空路由配置；研究主循环使用显式种子及TraCI。所有MCP工作目录、SUMO输出、临时和截图文件均指向keyan1。

## 当前隔离保证及限度

`perception/contracts.py`只定义冻结、带slots的局部接口，邻车字段限定为局部track编号、相对位置/速度/航向、外形与测量时刻。没有真实SUMO ID、NOA/HDV、他车计划、全局领航车或槽位。`research/smoke.py`中的全局车辆表只用于原生路测的独立日志/验收，没有控制器消费它。

这不是已经完成感知隔离或动作不变证明。阶段3必须实现真值→感知过滤，阶段4及之后必须对相同观测和本地记忆下改变隐藏状态进行真实动作不变测试。未来道路观测必须来自可见部分，控制器不得直接读取该场景构建器或全局道路配置。

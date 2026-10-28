# 论文对齐与补充参数（阶段 0–1，2026-09-10）

本工程是**论文公开参数优先、改编源码补充、通用假设明确登记的研究实现**，不是 Cai 2024 完整复现。活动参数以 `configs/paper_reference.json`、`configs/no_comm_main.json`、`configs/topology_smoke.json` 为准；参考值及待扫描值也汇入 `parameter_registry.csv`。原始规格和初始源码 JSON 未修改。

## 原件与核验顺序

先核对初始 JSON 中 29 个 MATLAB/MAT/XML 文件：全部 SHA-256 一致，再核对以下只读原始 PDF。未运行参考 MATLAB 的交通仿真；哈希不变的 MAT 采用已完成的只读核验记录，不重新把旧工作区变量解释为车型。

| 文献 | 只读原件 | SHA-256 |
|---|---|---|
| Cai 2024, IV, 2283–2288 | `D:/zotero文献/storage/Y97IG9J7/Cai 等 - 2024 - Multi-lane Formation Control in Mixed Traffic Environment.pdf` | `32869adfed8874153cbfa6896e7e8fc7960091c26b33e0d983eda926a785ebde` |
| Cai 2022, TRC 136, 103513 | `D:/zotero文献/storage/L9RCB94L/Cai 等 - 2022 - Formation control with lane preference for connected and automated vehicles in multi-lane scenarios.pdf` | `e222d2226b60a1af991ed30cf0e9609a1682769b1dfcdc0b7c63f04740bf27d5` |

2024 在 `M63NRX2B` 的另一副本与上述文件哈希相同。证据在 `results/phase0/paper_hashes.json`。提取文本、Table I/Fig.4 与 Table 2 渲染页保存在 `tmp/papers`。文字提取器报告了 Symbol/ArialUnicode 显示字体提示，因此数值及正负号同时与 PDF 页面图像核对。PDF 和源码中的文字只作为文献数据处理。

## 采用关系

| 项目 | 2024 原文 | 当前工程 | 状态与证据 |
|---|---|---|---|
| 道路 | 三车道 l1+l2=1000 m；两车道 l3=200 m | 完全采用长度和车道数 | p4 Fig.4/正文 |
| 终止车道 | 向右行驶，上侧车道终止 | SUMO 上游 lane 2 终止；0→0、1→1 | 图示解释；p4 Fig.4 |
| S1/S2 边界 | 不固定 | 不建固定 S1/S2 边界，也不向控制器暴露 x=1000 触发器 | p4 正文 |
| 收窄绘图 | Fig.4 有示意收窄 | 物理 lane 2 在 x=1000 截止，不虚构锥形区长度 | 几何简化；全长保持三条上游 lane，合流必须发生在上游 |
| 路网限速/车辆最高速度 | 车辆上界 33.3 m/s | 两者均显式为 33.3 m/s | 道路限速取同一值是本研究的显式对齐选择，原文表格只直接给车辆上界 |
| 编队期望速度 | 28.8 m/s | 保存为论文参考；冒烟发车速度取 28.8 | p3 Table I；原生 IDM 自由速度可升至 33.3，并非编队控制 |
| 结构切换周期 | 5 s | 保存为结构时间尺度 | p3 Table I；绝不是积分 dt |
| 纵向加速度 | −10～+5 m/s² | 主模型预留硬边界；另设舒适边界 | p3 Table I；未证明所有工况的物理可达性 |
| 前轮转角 | ±40° | 配置内部上界 0.6981317008 rad | p3 Table I，换算值；阶段 2 必须受速度、附着和转角速率限制 |
| 表中 d_g | 15 m | 参考源码解释为 d_ref=15、同车道 2d=30、邻道错位 d=15 | p3 Table I + `formationControlNormal.m:24–28`；等长车净距26/插入净距11仅是几何值 |
| 输入需求 | 1250/1500/1750/2000 veh/(lane·h) | 精确按 q×0.1/3600 转成逐车道概率 | p4–5，保持期望流率，不强行修整随机计数 |
| 渗透率 | 0～100%，每10%一档，指 CAV | 本轮仅产生100% NOA离线标签；未做混行控制 | 语义不同；随机类型评分可用于后续嵌套占比，禁止作为邻车观测 |
| 软件 | MATLAB2023b + SUMO0.32.0 | Python3.12.9 + SUMO/TraCI1.27.1 | 新实现和版本差异 |

2022 p4 §2.1 明确需要所有车辆和道路信息的集中上层；p11 §5.2.1 写明 2-DOF bicycle 与纵向二阶模型，但未给本文所需全套物理参数。p13 Table 2/Fig.10 的 15 m/s、25 m/s 上界、4 s、50+350+600 m 三车道排序场景全部保留为文献对照，不迁入 2024 主场景。2024 p3 §III 实际采用附近有 HDV 时退出网联编队的简化方案，不能把其全局按类型分组或讨论中的复杂绕行机制写成无通信算法。

## 显式补充车辆与感知假设

| 参数 | 值 | 使用边界 |
|---|---|---|
| 车长/车道宽 | 4 m / 3.3 m | 改编源码明确值，已显式写入新车辆/车道 |
| 车宽/轴距 | 1.8 m / 2.7 m | 通用乘用车假设；没有品牌型号 |
| CG到前后轴 | 各1.35 m | 假设 CG 与几何车身中心重合 |
| 前后悬 | 各0.65 m | 2.7+0.65+0.65=4 m |
| 质量/横摆惯量 | 1500 kg / 2500 kg·m² | 新假设；不是 MAT 变量 m，也不是油耗乘数1.2推导 |
| 前/后整轴侧偏刚度 | 各80000 N/rad | 小侧偏角线性整轴值，不能再乘2当整轴值 |
| 附着系数/重力近似 | 0.9 / 9.81 m/s² | 开发假设；附着工况需扫描 |
| 纵向/转向滞后 | 0.2 / 0.15 s | 新增执行器假设 |
| 转角速率 | 0.5 rad/s | 新假设 |
| 舒适加速/制动/侧向加速/jerk | 2 / 3 / 2 m/s² / 2 m/s³ | 后续 NOA、基线、编队共用 |
| 低速模型融合 | 1～3 m/s | 阶段2实现并验证，当前未执行 |
| 动力学/同步/行为周期 | 0.01 / 0.1 / 0.5 s | 预留阶段2–3使用；与论文5 s分开 |
| 前/后/侧感知范围 | 200 / 100 / 50 m | 预留P0/P1/P2，当前只有契约，没有感知仿真 |
| P2位置/速度标准差、延迟 | 0.2 m / 0.2 m/s / 0.1 s | 预留假设；不等于SUMO tau |
| 排放类别候选 | HBEFA3/PC_G_EU4 | 通用类别，未标定到假设车辆；本轮无能耗分析 |

轮胎、惯量、执行器等已经登记，但不参与本轮原生 IDM 道路测试。为方法开发选用这些假设不等于验证其真实性；后续数值收敛、物理可行性和敏感性检查仍是门槛。全部扫描候选见 `configs/sensitivity.json`，没有运行扫描。

## 原生道路测试参数

所有车只使用 `native_probe` vType：IDM/LC2013，车长4、宽1.8、质量1500、maxSpeed33.3；accel2、decel4.5、emergencyDecel10、tau1.2、minGap2.5、delta4、stepping0.1、speedFactor1、speedDev0；lcStrategic1、lcCooperative1、lcSpeedGain0、lcKeepRight0。原生换道持续3 s。明确的物理/行为输入已登记；其余 LC2013/IDM 算法内部默认值属于锁定的 SUMO1.27.1 原生测试实现，不能据此声称实现了本文动力学或 NOA。阶段2以后不把这些测试行为当主方法。

模型类别、处理策略与各数值都记录在参数登记表中。SUMO 的 `tau`、车辆尺寸及发车语义按[车辆和路线官方文档](https://sumo.dlr.de/docs/Definition_of_Vehicles,_Vehicle_Types,_and_Routes.html)核对；路网使用[PlainXML](https://sumo.dlr.de/docs/Networks/PlainXML.html)再经 netconvert 生成；排放类别见[HBEFA官方说明](https://sumo.dlr.de/docs/Models/Emissions/HBEFA-based.html)。

本轮没有旅行效率或节能提升估计，未声称完整复现。原文报告的效果也不能转述为新工程结果。

# 固定seed91速度时空展示

按事前保留的seed91，读取1500、1750、2000辆/h/车道NOA/D1六个缩道原始run。六例均seal verified，positions/events原件SHA与封存一致，input/result/trips及run_dir与最终90例独立原件审计一致；每例6份冻结源码逐字核对。本次只读，没有新仿真、控制改动、调参或改写正式表。

- [主图：三行两列、所有实际道车辆速度，300dpi PNG](seed91_all_lanes_speed_spacetime.png) / [SVG](seed91_all_lanes_speed_spacetime.svg)
- [补图：2000/91实际lane2速度，300dpi PNG](seed91_2000_actual_lane2_speed_spacetime.png) / [SVG](seed91_2000_actual_lane2_speed_spacetime.svg)
- [完整runmap及逐例原件SHA](runmap.json)、[全部来源SHA](source_sha256.json)、[分箱协议](binning_protocol.json)、[验证](validation.json)、[视觉QA](visual_qa.json)
- [生成脚本快照](make_final91_spacetime_source.py)；根脚本为相邻`make_final91_spacetime.py`。

时间横轴[100,600)s，位置纵轴[0,1200)m；统一10s×25m分箱，全部区间左闭右开。每个bin均速为该bin实际车辆样本的速度和除以样本数，逐车逐帧统计，不插值、不补虚拟车辆、不先对道或帧均分权重。六panel统一0–33.3m/s色标；无样本bin均速为空，图中为白。640m为准备区起点，1000m为终止道末端。

8份`*_bins.csv`包含每bin时间/空间上下界、实际样本数、速度和、均速。主图6份合计14400行，lane2补图2份4800行；每例5000个窗口帧，六例合计30000帧，流式读取后只保留50×48计数/速度和数组，不缓存车辆轨迹。全部82个来源SHA复核、19200个CSV bin及均速恒等关系通过；原始速度和与bin速度和最大绝对差5.59e−9m/s（补偿求和校验）。

补图的实际lane2以原trip lane_events的SUMO车道索引翻转逐帧重放，不使用目标道或意图；车身横跨两道时按原索引归属。全道聚合会把少量终止道停车与其他继续道速度混合，补图保留了这一层信息。位置恰1000m落在[1000,1025)m的bin，色块覆盖该bin不表示车辆连续占据整段25m，也不表示终止道延长。

图注建议：固定seed91的测得速度时空分布。行对应三流量，列为NOA/D1，全部panel用同一速度色标和同一分箱。该代表展示同时呈现末端等待与640m附近的重组速度代价；lane2空白表示无实际样本，不能当作高速度。1500/91和1750/91的主道路DID为反向值，仍按事前固定种子保留；本图没有直路基准，不能直接推断DID或替代五种子正式主效应、燃油和双方post5表。

PNG主图3104×2977、补图3104×1420，实际DPI299.9994；SVG保留矢量色块和可编辑文字。两图已逐张视检，图例/图注/色标没有重叠或裁切。

v1首次在输出任何CSV/图之前，独立总速度直接累加的舍入误差触发校验断言；原操作日志保留在`results/operations/20261103T152415028932Z_midflow-final91-seed91-speed-spacetime_5781f3e7`，空v1目录未覆盖。改用标准补偿求和作总和校验，在新v2完整运行通过；空间/时间bin、样本、速度和及均速定义均未改。成功操作为`20261103T152612905085Z_midflow-final91-seed91-speed-spacetime-v2_de49b8c2`。

# 普通 HDV 的缩道拥堵核查

在本地 SUMO 0.32.0 中，用同一批 781 辆普通 HDV 比较路网。直路没有 800–1000 m 的低速积聚。MATLAB 项目的合流路网出现 8279.1 辆·秒的低速积聚，物理终止道对照出现 9536.7 辆·秒。两种缩道路网均在 600 秒内留下约 190–200 辆未到达，排空后全车完成。这组实验诊断的是固定需求下的道路合流损失。

## 论文与本地入口

- Cai 2024 第 2286 页 Fig. 4 写明上游三道 1000 m、下游两道 200 m。第 2287 页 Fig. 5(b) 的需求标签是 1500 辆/(道·h)。在 0% MPR 面板，低速区从断面附近往上游蔓延，到 600 s 接近入口。100% MPR 面板的广泛低速区消失。图中是局部时空平均速度，只能从中判读拥堵形态。0% 和 100% 两端同时改变车辆构成和编队控制。论文只提供这一观察，没有公布共同车型的纯 NOA 对照，也没有给出这两组的完成数、断面流量及整段旅行时间数值。论文公布 MATLAB R2023b 和 SUMO 0.32.0。现有材料尚未建立本地源码与 Cai 发表版本的对应关系。[Cai 2024 PDF](/D:/yanjiu1/keyan1/docs/Cai%20et%20al_2024_Multi-lane%20Formation%20Control%20in%20Mixed%20Traffic%20Environment.pdf)
- `mainmain.m` 最终生效的是 `Tflow=0.042`，每 0.1 s 分别为 2、1、0 三道各抽一次。期望请求为每道 1512 辆/h、全路 4536 辆/h。精确每道 1500 需用概率 `1500×0.1/3600=0.041666…`。出发口前车约束可延迟实际插入，脚本仅循环 600 s。[mainmain 流量](/D:/matlab_huipu_2000/mainmain.m:37) · [步长](/D:/matlab_huipu_2000/mainmain.m:71) · [请求](/D:/matlab_huipu_2000/mainmain.m:289) · [600 秒循环](/D:/matlab_huipu_2000/mainmain.m:152)
- `RUN_20220530.m` 的实际入口传入 30%–80% ICV 渗透率、0.5 普通 HDV 概率和一组奖励响应概率。`RUN.m` 前后调用 `mainmain` 和 `mainmain_REF`，前者依赖工作区变量。`mainmain_REF` 使用 `New_Vehicle` 的 `CAV_L`、30 m/s、IDM `tau=0.45 s`，与本次普通 HDV 分支不同。历史 `RUN_result_draw_1.m` 的 1500 横坐标对应流量数组中的 `.042`。原始 `Parameter.mat` 当前保留 `PRate=.8`、`hdvNormalProb=.5`、`runm=.1824255`、`Tflow=.042` 和 `simulation_step=.1`，根 `tripinfo.xml` 没有行程条目。抽查 `.60.50.5.mat` 有 725 个请求记录，按 `vehicleTypeRecord` 计 412 ICV、159 奖励 ICV、82 激进 HDV、72 普通 HDV，677 个 `vehicleState` 记录被标为已完成。普通 HDV 在混合场景中的记录受到周边车型和控制共同影响。未找到带全普通 HDV 参数和明确来源的原始轨迹。[混合入口](/D:/matlab_huipu_2000/RUN_20220530.m:1) · [RUN](/D:/matlab_huipu_2000/RUN.m:1) · [REF](/D:/matlab_huipu_2000/mainmain_REF.m:109) · [REF vType](/D:/matlab_huipu_2000/New_Vehicle.m:9) · [历史图横轴](/D:/matlab_huipu_2000/RUN_result_draw_1.m:25) · [留存实验](/D:/matlab_huipu_2000/202312072133_result_mixed_0.60.50.5.mat)
- 本地生成器和实际 `cross.net.xml` 写了两段各三条实体车道。路由 `P1P3` 在 x=1000 仅有 0→0、1→1、2→1 三条连接，2→1 在网络中为低优先级。下游车道 2 无直接入口。一辆车可以在上游原生换道，也可以随内部连接并入下游 1 道。此处是三个上游车流竞争两股下游直接通路。[起终点](/D:/matlab_huipu_2000/New_Road.m:10) · [车道生成](/D:/matlab_huipu_2000/New_Edge.m:10) · [网络车道](/D:/matlab_huipu_2000/traci_tls/data/cross.net.xml:31) · [实际连接](/D:/matlab_huipu_2000/traci_tls/data/cross.net.xml:50)
- 普通 `CAV_HDV` 使用 IDM，`tau=0.65 s`、`minGap=2 m`、车长 4 m、加速 3 m/s²、减速 10 m/s²、应急减速 30 m/s²、`delta=4`、`stepping=0.1 s`。换道 `lcSpeedGain=0.3`、`lcCooperative=0.5`、`lcImpatience=0`。入场请求以 28.8 m/s 开始，设置 `speedMode=31` 和 `laneChangeMode=0`。车辆进入活跃集后，普通 HDV 执行分支将 `laneChangeMode` 切至原生 1621 并跳过编队速度与换道命令。激进随机命令只进入 `Aggressive` 分支。普通 HDV 可原生主动换道，本地路网限速 41.66 m/s，回放实际有车以 41.66 m/s 离场。原始普通 HDV 工况与本项目现行 NOA 的速度上限、道路连接及执行版本均需分别核对。[普通 vType](/D:/matlab_huipu_2000/traci_tls/data/cross.rou.xml:4) · [插入模式](/D:/matlab_huipu_2000/mainmain.m:321) · [活跃模式](/D:/matlab_huipu_2000/mainmain.m:786) · [有计划时的 HDV 分支](/D:/matlab_huipu_2000/mainmain.m:827) · [激进分支](/D:/matlab_huipu_2000/mainmain.m:234) · [TraCI 换道模式](https://sumo.dlr.de/docs/TraCI/Change_Vehicle_State.html#lane_change_mode_0xb6)

## 同需求路网诊断

用 SUMO 0.32.0 和配套 TraCI 运行全普通 `CAV_HDV`。三个场景共用 `cross.rou.xml`、每步 `0.042`、随机种子 8、车道请求顺序 2/1/0。采用独立于 MATLAB 控制器的 Python 随机数流，以固定需求跨路网配对。请求数为 0/1/2 道 241/264/276，实际总请求强度为 4686 辆/h。运行需求 600 s 后排空，最多 900 s。使用旧版 TraCI 加车参数 `depart=-3, pos=0, speed=28.8`，待插入时设换道模式 0，首次以活跃车出现时恢复 1621。开启 `lanechange.duration=1`，与原入口 GUI 调用一致。使用原始 `cross.net.xml` 对照旧连接。另用同版 `netconvert` 各构建一个物理下游两道且无 `2→1` 连接的终止道场景，以及一个 0→0、1→1、2→2 的直路场景。物理路网重建后的车道几何也随连接调整。全过程未执行 MATLAB 入口或 SNOPT。

| 路网 | 600 s 插入 / 到达 | 排空 s | 全部完成者平均行程 s | 平均入口等待 s | x=1000 断面流量 辆/h | 800–1000 m 低速 辆·s | 区间低速车辆峰值 | 2→1 换道发生在 ≥950 m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 原本地内部合流 | 754 / 593 | 753.7 | 100.618 | 4.010 | 3852.0 | 8279.1 | 32 | 112 / 302 |
| 物理终止道 | 751 / 581 | 769.7 | 109.411 | 4.584 | 3765.6 | 9536.7 | 36 | 125 / 321 |
| 三道直路 | 781 / 740 | 632.2 | 32.922 | 0.258 | 4701.6 | 0 | 0 | — |

断面流量用 100–600 s 内 x=1000 的穿越次数计算。低速范围为前 600 s 内 800≤x<1000 m 且速度低于 5 m/s，逐车逐步积分。换道统计是上游 `seg1_2→seg1_1` 的车道索引变化事件，可重复计同车，也不计内部连接直接并入。两种缩道的低速积分各有约 77% 发生在 1 道。最低速度带中观测到的最上游位置分别为约 56 m 和 55.5 m。下游 2 道仅在直路场景中被使用，观测到 287 辆。三场景各有 781 个完成行程，都没有遥移，SUMO 错误日志为空。数据对应这一条固定需求带，尚无多种子方差或限速、跟驰参数、SUMO 版本的独立消融。[原始日志](/D:/yanjiu1/keyan1/results/operations/20261117T170909079840Z_nov18_matlab_verified_f8ee53d4/stdout.log) · [回放脚本](/D:/yanjiu1/keyan1/tmp/nov18_matlab/ordinary_hdv_replay.py) · [固定需求](/D:/yanjiu1/keyan1/tmp/nov18_matlab/verified/local.demand.json)

回放脚本复制到新目录后，可从工作区分别执行 `python -B <replay.py> local`、`python -B <replay.py> physical_drop`、`python -B <replay.py> straight`。三条需求账本 SHA-256 均为 `787474d811e31452c1fbf93b48114e1aa946cf88b2433b008c47b7b57a947c7f`。首轮已输出行程，旧版 `<tripinfo>` 使用 `waitSteps` 导致汇总脚本退出，表中取修正后退出码 0 的独立重跑。

## 对局部 NOA 和编队的机制对应

在实验的两个缩道路网，三道同时有来车，1 道要吸收终止道来车，流入高于持续出流。1 道低速占比、末端换道数和上游低速传播同时出现。保持同样的车辆和来车，直路消除了局部低速并在 600 s 内多完成 147 或 159 辆。普通 HDV 已具有主动换道，合流拥堵仍可由可接受空隙与道路出流约束产生。该实验没有分别识别跟驰、车道选择和路权对容量下降的贡献。

局部 NOA 应保留对受阻车辆的安全主动换道。看见终止道后，终止道车辆可提早在相邻道选择当前可辨的真实前后车空隙，按相对速度调整并入时机。相邻保留道仅对实际可见的合流竞争调速，为必要合流先让出眼前可用间隔。视野内的拥挤、空隙消失或纵向安全门失效时，先取消该次可选换道，下一次仍按实测前后车与占用走廊重新判断。远处的车道终点、参与者车型和意图均未用作触发量。

若要识别编队变换贡献，使用共同需求和共同物理条件，先冻结纯 NOA 的主动换道和安全逻辑。以本地可见的前后车、终止标记与前后向预测为条件，分别检验合流前形成可持续空隙和并入后恢复交错。放行时间、末端换道位置、低速车秒、断面流量、发车等待及未完成数一起报告，使局部少停车与全程效率可分别复算。

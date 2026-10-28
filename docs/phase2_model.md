# 阶段2：连续动力学、单车验证与同步约定

研究根目录：`D:\yanjiu1\keyan1`。本实现遵循研究规格 §7 和阶段2要求；不是 Cai 2024 完整动力学的复现，也不是量产车型标定。所有模型数值、数值容差和工况快照均随运行保存。

## 状态和信息边界

`models/vehicle.py` 的冻结状态为 `(time_s, X, Y, ψ, vx, vy, r, a_drive, δ)`，位置取车身几何中心与质心重合的假设参考点，航向连续展开、逆时针为正。输入仅为加速度命令和前轮转角命令。该模块不读取 TraCI、道路、邻车、类型或编队计划。

本阶段的 `bench_command` 只读取自车状态、时钟及预先给定的单车参考；它不读取自车全局 x 触发动作。路网几何和全局坐标只供仿真初始化、SUMO 映射及隔离评估使用。这里还没有 `ControlInput` 驱动的 NOA 决策器、有限范围观测适配器或多车调度器。

## 连续方程与模型限制

```text
X_dot = vx cosψ − vy sinψ
Y_dot = vx sinψ + vy cosψ
ψ_dot = r
vx_dot = a_long
a_drive_dot = clip((a_target−a_drive)/τa, −Jmax, Jmax)
δ_dot = clip((δ_target−δ)/τδ, −δrate_max, δrate_max)

αf = δ − (vy+lf*r)/max(vx,v_blend_start)
αr = −(vy−lr*r)/max(vx,v_blend_start)
Fy_front_raw = Cf αf; Fy_rear_raw = Cr αr
vy_dot_dynamic = (Fy_front_raw+Fy_rear_raw)/m − vx*r
r_dot_dynamic = (lf*Fy_front_raw−lr*Fy_rear_raw)/Iz
```

采用整轴刚度 Cf=Cr=80000 N/rad；质量1500 kg、惯量2500 kg·m²、轴距2.7 m、lf=lr=1.35 m、车宽1.8 m均是通用开发假设。车长4 m、车道宽3.3 m的来源沿用前期核验；没有将某个品牌车型伪称为原文数据。

纵向 `a_long` 是规格所定义的 `vx_dot`，不含完整车体纵向方程的 `vy*r` 耦合项；静态轴荷、不建模载荷转移、空气阻力、轮胎纵向滑移或非线性轮胎。这是小侧偏的简化车辆模型，不能由本阶段结果推出极限操稳或实车安全。`a_drive` 为执行器等效状态；`a_long` 再受加速度、附着及非负速度/最高纵向速度约束。

低速目标为 `r_k=vx*tanδ/(lf+lr)`、`vy_k=lr*r_k`，用0.1 s松弛产生目标导数；vx≤1 m/s用低速分支，vx≥3 m/s用动态分支，中间使用 `w=z²(3−2z)` 融合。该低速模型是带动态松弛的近似，不是直接设置理想位置或横摆。

**融合后统一执行附着约束**：先由融合所需 `ay_req=vy_dot_req+vx*r`、`r_dot_req` 解等效轴力，再对每轴独立投影：

```text
Fzf = m*g*lr/L; Fzr = m*g*lf/L
Fxf = m*a_long*lr/L; Fxr = m*a_long*lf/L
Fyf_req = (m*ay_req*lr + Iz*r_dot_req)/L
Fyr_req = (m*ay_req*lf − Iz*r_dot_req)/L
|Fyi| <= sqrt(max(0,(μ*Fzi)² − Fxi²))
ay = (Fyf+Fyr)/m
vy_dot = ay − vx*r; r_dot = (lf*Fyf−lr*Fyr)/Iz
```

这样低速松弛也使用同一附着预算。旧实现绕过该预算的反例及修复见 `phase2_dynamics_review.md`；默认μ=0.9未改变。日志中的 `fy_*_requested_N` 是投影前请求，`fy_*_N` 是实际用于积分的力，`tire_saturated` 表示请求被截断。高速侧偏绝对值超过0.1 rad会记录有效区间告警；低速等效力不能解释成标定的线性轮胎实测力。

命令转角同时受±40°和速度相关目标包络约束：

```text
ay_available = min(2, sqrt(max(0,(μg)²−a_long²)))
|δ_target| <= min(40° in rad, atan2(L*ay_available, vx²))
```

目标限幅不能保证每个暂态实际 ay 都小于2 m/s²，所以验收另行检查实际 `ay`、轴力、转角速率、执行器jerk及侧偏。停车处 `a_long` 从制动切换为零，实际纵向jerk可能大于执行器jerk上限；两者分列记录，不能将执行器平滑误写成全过程实际jerk≤2。后续舒适性研究需要处理该接触/停车约束的非光滑性。

## 时间离散与跟踪工况

RK4积分默认0.01 s，积分细化0.005 s；默认命令保持/同步周期0.1 s，控制细化0.05 s。物理状态只从积分结果接续。`validate_integrated_step` 用冻结初态与命令重算所有子步作一致性检查，重算结果不回写车辆、不累加物理时间；恒速解析式与执行器解析式另行验证积分正确性。

固定五个小工况：

| 工况 | CG初值 (x,y,vx) | 时长 | 命令/参考 |
|---|---|---:|---|
| constant_speed | (100,1.65,28.8) | 10 s | 零加速度、零转角 |
| acceleration_stop_restart | (100,1.65,5) | 14 s | t=0/2/7/9 s起依次+2/−3/0/+2 m/s² |
| constant_steering | (100,1.65,10) | 3 s | 0.01 rad固定转角命令 |
| lane_change | (100,1.65,28.8) | 10 s | 前5 s从y=1.65平滑到4.95 m，后5 s保持 |
| edge_crossing | (900,1.65,28.8) | 7 s | 直行跨x=1000，持续在保留车道 |

换道参考 `y=y0+(y1−y0)(10u³−15u⁴+6u⁵)`，u截断于[0,1]。位置、横向速度和横向加速度端点连续；参考jerk在起止点有跳变，通过连续转向执行器响应。5 s仅是该测试参考时长，论文5 s仍是结构切换周期。

首版用运动学转角前馈与世界坐标PD，峰值误差0.652939 m，未通过原定0.35 m门槛，证据保留。最终采用已声明二自由度模型的解析低频逆前馈：若 `H(s)=ay(s)/δ(s)=(n2*s²+n1*s+n0)/(s²+d1*s+d0)`，则 `G=n0/d0`、`τplant=d1/d0−n1/n0`，

```text
δcmd = [ay_ref + kp*(y_ref−y) + kd*(ydot_ref−ydot)
        + (τplant+τsteer)*jerk_ref] / G
```

系数由线性单轨A/B矩阵解析求得，固定28.8 m/s参考工况得到G=307.2 (m/s²)/rad、τplant≈0.470039 s；τsteer=0.15 s、kp=0.6、kd=1.5均保持原值，没有新增拟合增益。该跟踪律用于固定高速测试参考，尚不是全速度NOA横向控制器。

同命令积分细化严格重用每条0.1 s加速度/转角命令；控制细化则在0.05 s重新计算相同跟踪律。比较双方所有共同积分时点，不能只比较终点。保留基线、积分细化、控制细化三套全部状态、命令和诊断。

## 固定验收值与登记

活动参数统一从 `configs/phase2.json` 读取并进入 `parameter_registry.csv`。本次将首版代码中的16个既有验收数值原值移入配置，没有放宽门槛；基础39项phase2参数及来源随运行存储。

| 检查 | 门槛 |
|---|---|
| 换道全过程峰值参考误差 / 10 s终态车道误差 | ≤0.35 / 0.1 m |
| 积分步长减半位置 / 航向差 | ≤0.02 m / 0.002 rad |
| 控制同步步长减半位置 / 航向差 | ≤0.15 m / 0.02 rad |
| SUMO位置 / 速度 / 航向读回误差 | 各≤1e−6（对应SI单位） |
| SUMO物理时刻 / 区间加速度读回误差 | ≤1e−9 s / 1e−6 m/s² |
| 数值重放每个字段差 | ≤1e−10（对应字段SI单位） |
| 恒速解析位置 / 速度误差 | ≤1e−7 m / 1e−9 m/s |
| 直行未请求航向 / yaw变化 | ≤1e−9 rad / 1e−9 rad/s |
| 恒转角终态转角 / yaw理论稳态误差 | ≤1e−5 rad / 相对5% |
| 停车段速度 / 启动最低增速 / 再启动终速 | ≤1e−6 m/s / ≥1 m/s / ≥1 m/s |
| 换道终态航向 / yaw | ≤0.02 rad / 0.02 rad/s |

另外，轴力比较容差1e−7 N、速率比较容差1e−8 SI、实际横向加速度比较容差1e−6 m/s²；子步时点1e−9 s、总时长1e−8 s仅为浮点匹配容差。测试必须无道路越界、轴力限额违规、执行器jerk/转向速率违规、有效区间告警，且SUMO不报告碰撞或传送。常规单车工况内的通过不证明拥挤混行安全。

## SUMO同步的可检验语义

SUMO返回前保险杠中心，导航角北为0°、顺时针为正；本工程用：

```text
front = CG + length/2 * (cosψ,sinψ)
sumo_angle_deg = (90 − ψ*180/π) modulo 360
sumo_speed = hypot(vx,vy)
```

初始化先插入静止车辆，再同步规定初态，排除这两个初始化步，并显式保存 `sumo_time_offset_s`（默认0.2 s，控制细化0.1 s）。此后 `physical_time = sumo_time−offset`。每个正常同步区间先核验当前读回，再验证已积分子步，排队提交终态速度与 `moveToXY`，仅调用一次 `simulationStep()`，最后读回终态。SUMO内部普通位移更新被指定积分终点覆盖，不作为下一步模型初态。[官方命令时序](https://sumo.dlr.de/docs/TraCI/Change_Vehicle_State.html#application-order-of-traci-commands-and-simulation-step)

`speedMode=0`、`laneChangeMode=0`用于单车外部控制测试；`keepRoute=3`保留路线与精确XY。自己的车身检测独立运行，不依赖SUMO自动安全调整来证明安全。测试保存实际版本、命令行、路段/车道、逐区间读回与事件。

SUMO `getAcceleration` 是步间速度变化的加速度，核验对象为 `(norm(v_final)−norm(v_initial))/sync_dt`；模型 `a_long=vx_dot`、`a_lateral=vy_dot+vx*r` 和执行器状态另外保存。初态设置的加速度不参与正常物理区间验收。[官方读回定义](https://sumo.dlr.de/docs/TraCI/Vehicle_Value_Retrieval.html)

此桥仅用于阶段2单车。后续多车不能逐车调用此对象而各推进一次SUMO；必须由统一调度器收集各车独立动作、统一积分/提交、每周期只推进一次，再逐车核验。

## 独立几何、失败与重放

旋转矩形SAT检测接触/重叠；按每个积分子步的线性位置/航向插值进行保守递归扫掠。中点分离距离超过顶点运动上界时可排除碰撞；无法在最大深度12排除时标记潜在碰撞。道路包络由当前net提取，对跨x=1000的整个车身裁剪检查，而不是只看质心。相同方法检测步间旋转越界。

检测承诺限于子步姿态插值包络。它不是任意非线性未采样路径的连续时间安全证明，保守告警也不能自动删去。故障注入覆盖端点均无碰撞但中途相交、端点均在路内但旋转中途越界、车身跨终止车道、瞬移、重复积分及缺失子步。

每次尝试先创建唯一运行目录并标记running/passed=false，再读配置/校验前置条件。异常（包括初始化与中断）写failed、traceback；科学门槛未通过是completed/passed=false，仍保存cases/faults和完整哈希，进程退出码非零。旧成功运行不会被覆盖。

运行保存完整源文件快照、配置和输入哈希、明确初态/命令、每个子步状态和诊断、真实SUMO读回。`phase2-replay`用该运行冻结参数与命令逐字段重算，并校验全部证据哈希；它不重新运行SUMO，也不表示原科学门槛必然通过。`source_gate_passed`与重放`passed`分别报告；当前代码若变化会列出差异，原源快照仍保留。

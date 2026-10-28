# 阶段2模型与几何独立审查

审查日期：2026-09-10。只读取 `D:\yanjiu1\keyan1` 内实际文件；未读取、复制或导入父目录研究代码，未启动 SUMO。初始审查对象均为工作区文件，SHA-256 保存在 `tmp/review_dynamics/evidence.json`。桥接、实验日志与整体阶段验收由主代理另行完成。

## 规格符合性

已核对主规格 §7 与阶段2、`phase2_entry.md`、`phase2_implementation_plan.md` 和两份配置。高速方程采用整轴 Cf/Cr，纵向 `a_long` 按规格定义为 `vx_dot`；存在加速度滞后/jerk 约束、转角滞后/速率限制、RK4 子步，以及速度 1–3 m/s 的平滑融合。模型入口仅接收自车状态和动作，未发现通信、邻车真值、车型或全局调度输入。车身以 CG 为中心，SUMO 转换采用半车长前移和 `90°−ψ`。

这些符合性不等于完整阶段2通过；本审查范围内发现下述附着约束问题，修复前应阻止把低速融合宣称为受摩擦约束的动力学。

## P1：低速融合绕过已饱和轮胎力

修复前位置：`models/vehicle.py:83–85`。第 78 行先截断动态轮胎力，随后第 83–84 行直接混入不受限的低速 `vy/r` 松弛导数；实际侧向加速度和横摆加速度因此不再由日志中的 `fy_front_N/fy_rear_N` 支撑。

最小复现使用默认参数和被 `advance` 接受的状态：`vx=.5 m/s, steering=.08 rad, a_drive=-8.829 m/s²`，其余状态为零。`observe` 输出：

| 量 | 修复前结果 |
|---|---:|
| μg | 8.829 m/s² |
| a_long | −8.829 m/s² |
| a_lateral | 0.200427761770 m/s² |
| hypot(a_long, a_lateral) | 8.831274669474 m/s² |
| 前/后轴侧向力 | 0 / 0 N |
| outside_linear_tire_regime | false |

以 `Actuation(-8.829,.08)` 积分 0.01 s 后产生 `vy=0.001682495018 m/s` 和 `yaw_rate=0.001246292606 rad/s`，尽管全部轮胎附着已用于纵向制动。此例前侧偏诊断为 .08 rad，未超预设 .1 rad 阈值，不能归因于大侧偏区外使用。

另有从 `vx=28.8`、其余状态全零开始的固定命令 `Actuation(-10,.3)`，在 t=5.28 s 出现合加速度 / μg = 1.007578893863。该较强案例已进入侧偏告警区，单独保留，不作为上述小侧偏复现的替代。

原测试 `tests/test_phase2_model.py:63–74` 仅在高速检查已截断的轴力；低速测试 `:76–87` 只检查有限性、连续性与静止稳定性，因此 11 项原有模型/几何测试全部通过仍未暴露该问题。

## 有界修复设计与验证步骤

主代理已明确授权修复 `models/vehicle.py` 和 `tests/test_phase2_model.py`：先计算融合所需的 `ay_req=vy_dot_req+vx*r` 与 `r_dot_req`，再解等效轴力

```text
Fy_front_req = (m*ay_req*lr + Iz*r_dot_req) / (lf+lr)
Fy_rear_req  = (m*ay_req*lf - Iz*r_dot_req) / (lf+lr)
```

两轴各自按现有纵向负荷和摩擦圆限幅，然后用实际轴力回算 `vy_dot` 和 `r_dot`。加速度、转角执行器及质量、刚度、阈值均不更改。先添加覆盖低速与融合区的合加速度约束、力/导数一致性以及可达制动转向轨迹测试，保存修复前失败证据，再实施统一投影并保存通过证据。

实际修复与验证结果见本文末节。

## 其他已运行核验

- 原有 11 项模型/几何测试通过，完整输出在 `tmp/review_dynamics/evidence.json`。
- 15 m/s、0.01 rad 恒转角，10 s 后与对称线性模型的独立解析稳态比较，yaw 和 vy 误差均小于 4e-16；dt=.01/.005 的位置差约 4.5e-12 m。该检查验证高速整轴刚度及数值积分，不能替代父任务的换道和跨 edge 工况。
- 固定种子 71024，独立顶点法 SAT 对 300 组旋转碰撞扫掠、101 个时刻/组进行抽查，未发现漏报，有 1 组检测器保守告警而离散抽查未命中。
- 对瓶颈附近 300 组道路扫掠、101 个时刻/组，独立采样车身边缘并检查台阶路界，未发现漏报。日志在 `tmp/review_dynamics/geometry_evidence.json`。
- 未发现 `models/geometry.py` 与 `safety/geometry.py` 中需要修复的重大问题；本次未修改这两个文件。

几何抽查只针对函数承诺的线性插值子步姿态。有限样本不能证明任意非线性连续轨迹绝不漏报；既有检测器文档也明确排除了这种证明。

复现入口（在 keyan1 内运行）：

```powershell
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S 'tmp\review_dynamics\reproduce.py'
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S 'tmp\review_dynamics\geometry_probe.py'
```

两个脚本显式只将 keyan1 加入 `sys.path`，输出仅在本项目 `tmp/review_dynamics`。`reproduce.py` 对已存在证据拒绝覆盖；上述初始命令是本次首次运行的记录，修复后的实际调用增加 `after_fix_evidence.json` 参数。修复前 `evidence.json` 已原样保留。

## 修复结果

已修改 `models/vehicle.py:83–104` 与 `tests/test_phase2_model.py:89–119`，未改几何、配置或其他代理负责的实现。

- 新增 3 项行为测试，覆盖 0.5/1.5/2.5/3 m/s 全制动的附着预算、融合区侧向力/横摆力矩与状态导数的一致性，以及从无侧向运动初态开始的制动转向轨迹在 dt=.01/.005 下的附着约束。
- `red_tests.json`：14 项测试运行，8 个子案例按预期断言失败，0 个运行错误；包括两种步长分别在 t=4.47/4.465 s 触发可达轨迹超限。
- `green_tests.json`：实现统一轴力投影后 14 项全部通过。
- `after_fix_evidence.json`：最小复现现为 `ay=0, yaw_accel=0, hypot(ax,ay)=8.829`，两轴请求侧向力约 287.788/12.853 N，实际力均为零，0.01 s 后 `y/heading/vy/yaw_rate` 均保持零。
- 相同 120 条默认参数、每条 8 s 的模型命令扫描未再出现合加速度超过 `μg*(1+1e-10)` 的案例。该扫描检查动力学附着，不作为道路安全或 NOA 策略结果。
- 修复后高速解析稳态与两步长比较维持前述误差水平。

诊断语义现在一致：`fy_front_N/fy_rear_N` 在所有速度区间均为实际进入导数的轴力；新增 `fy_front_requested_N/fy_rear_requested_N` 为投影前的融合请求；`tire_saturated` 表示该请求超过各轴可用附着。过去这个布尔值只比较原始线性轮胎力，不能描述低速松弛是否受限。

该修复关闭本次 P1 问题，并未校准车辆或证明全部工况有效：固定静载荷/纵向力分配、纵向 `ax=vx_dot`、忽略若干高阶耦合项的简化仍按原规格保留；线性胎仍以 .1 rad 作为告警阈值。1–3 m/s 融合与 ≤1 m/s 松弛产生的请求力是模型等效量，不能称为实测轮胎力。实际附着约束现在对这部分等效力同样生效；轨迹跟踪、SUMO 同步及完整阶段2门槛仍需主代理的独立验收。

本次先红后绿命令（日志禁止覆盖）：

```powershell
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S 'tmp\review_dynamics\test_runner.py' red
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S 'tmp\review_dynamics\test_runner.py' green
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S 'tmp\review_dynamics\reproduce.py' after_fix_evidence.json
```

## 补充审查：最终单车工况与模型前馈

本节独立审查 `experiments/phase2_cases.py`、`experiments/offline.py`，并只读核对 `experiments/phase2.py` 的聚合门槛与 `results/phase2/preflight/offline_final_summary.json`。没有修改实现、配置或活动结果，没有执行 verify、完整 phase2 或 SUMO。纯内存复算的脚本与证据为 `tmp/review_dynamics/bench_math_probe.py`、`bench_math_evidence.json`，包含此次审查源码 SHA-256。结论：在当前明确的固定单车试验范围内，未发现阻断验收的规格或代码问题。

### 前馈推导核对

`phase2_cases.py:70` 的 helper 与现有高速、小侧偏、未饱和 2-DOF 方程一致。令状态为 `[vy,r]`、输入为实际转角 δ、速度为常数 V；横向加速度输出满足 `ay=vy_dot+V*r`。若状态矩阵为 A、输入矩阵为 `[b1,b2]ᵀ`，由状态消元可得：

```text
H(s) = ay(s)/δ(s) = (n2*s²+n1*s+n0)/(s²+d1*s+d0)
d0 = a11*a22-a12*a21
d1 = -(a11+a22)
n2 = b1
n1 = -a22*b1+(a12+V)*b2
n0 = V*(a21*b1-a11*b2)
K = n0/d0
τ_model = d1/d0-n1/n0
```

因此 `H(s)=K*(1−τ_model*s+O(s²))`，串联一阶转向执行器后，低频参考逆前馈为 `[ay_ref+(τ_model+τ_steer)*jerk_ref]/K`。代码把 PD 的加速度校正加在这一参考前馈上，并未声称对 PD 反馈项或整个非线性模型进行精确逆运算。单位核对成立：K 的单位是 `(m/s²)/rad`，τ 是 s。

独立通过实际 `VehicleModel.observe` 在 V=28.8 m/s 附近做数值线性化，再求 `C(sI−A)⁻¹B+D`，而非复制 helper 的系数公式，得到：

| 量 | 独立核算 | 当前 helper |
|---|---:|---:|
| DC gain K | 307.2 | 307.19999999999993 |
| τ_model (s) | 0.470038580373 | 0.470038580247 |
| τ_model+τ_steer (s) | — | 0.620038580247 |

原 `kp=.6, kd=1.5` 与速度增益 `.8` 未变；前馈参数来自已声明质量、惯量、轴位置、整轴刚度和执行器 τ，没有新增拟合或自由调参量。冻结模型参数在执行时覆盖 case 的参考物理量，`bench_command` 不重新读配置。

该推导限于当前固定高速工作点，低频展开不是全频段精确逆模型，也不覆盖低速融合、轮胎饱和或任意变化速度。实际换道最大航向约 .04979 rad、最大侧向加速度约 .94988 m/s²，侧偏告警与轴力饱和样本均为零，支持此次工况处于所声明近似范围内；不支持把 helper 直接当作任意工况 NOA 控制器。

### 工况、时刻和固定门槛

- `cases()` 明确提供恒速、加速停车重启、恒转角、换道、跨 edge 五项。全状态初值完整、可序列化；`x=100/900` 只选取试验位置。`bench_command` 的转向/驱动仅使用自车状态、时钟和预先给定参考；`x=100` 与 `x=1100` 的独立动作比较完全相同。道路 `x=1000` 只出现在独立评估或跨 edge 完成判据中。
- `reference_at` 使用 5 s quintic，端点位置/速度/加速度连续，即 C2；jerk 在参考开始和结束可以跳变，不能称为 jerk 连续轨迹。执行器保证实际转角与运动状态按动力学推进。浮点时间在参考段边界归一到 12 位，未见一个额外控制周期的切换偏差。
- 换道峰值误差在完整 0–10 s 的所有积分样本上计算；终端 `.1 m`、航向/yaw 门槛作用于 10 s 试验末端，不应描述成“5 s 完全稳定”。独立复算额外确认 t=5 s 的位置误差为 .044697511598 m；t=10 s 位置误差 .028358551556 m。
- 积分减半保持原 `.1 s` 命令序列，只把 `.01` 改为 `.005`；控制减半用 `.05 s` 重新执行同一跟踪律，保持积分 `.01 s`。`compare_trajectories` 检查同起止时间和每个较粗积分时刻，不按数组索引或仅比较端点；本次换道两种对照均比较 1001 个相同时间点。
- 完整运行的聚合门槛 `phase2.py:251–255` 要求三个变体的工况、几何和重放判定均通过，以及积分差 ≤.02 m/.002 rad、控制差 ≤.15 m/.02 rad；基准通过不能覆盖变体失败。换道阈值仍为最大 .35 m、末端 .1 m。本次没有调整这些值。
- 独立复算与已保存摘要一致：换道峰值 .159551242353 m；积分减半位置/航向差约 5.1244e−10 m/3.3260e−10 rad；控制减半差 .038032005686 m/.001758999541 rad。纯内存的零转角坏跟踪和截断历史负例均被评估器判失败。已保存摘要中五项及各自两个 refinement 均为通过，最大积分位置差来自停车工况，约 1.68094e−5 m。

离线 `_body_inside_road` 仅检查采样姿态，完整运行另外执行 `audit_geometry` 的子步保守扫掠，因此不把采样道路判定当成完整扫掠证明。恒转角稳态 yaw 公式含标准欠转向项，与本次对称轴参数的解析结果一致。首版跟踪失败证据不属于本次被改写的对象；本补充审查没有覆盖或删除历史结果。

# J/JT：全体车辆的局部相对位置耦合及物理邻接修正

2026-11-03。父基线为444行E，SHA `04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274`。本单元只生成独立441行候选，不改E、生产、核心原tests或E迁移patch。H仅改队首配对的真实demo不足以支持全体形成；这里增加body的实际跨道耦合，仍须另外验收真实几何。

## 共同局部机制

固定物理相位为三道0/15/0m，存续两道0/15m，`_fill`直接复用 `_phase`。共同pair_lanes继续按原E判断，仅用于既有误差归一化。

对真实可见的相邻道车i、j，令 `φ_i=physical_phase(i,3)`，`dx=x_j−x_i`：

```text
J:  e_ij = dx + φ_j - φ_i
JT: e_ij = dx + (φ_j - φ_i) * (5.5 + HEADWAY*(v_i+v_j)/2)/30
```

JT相对J只差后一式的对称速度伸缩因子，不修改自由fill的巡航30/15模板。共同速度v下，它使跨道目标为 `D(v)/2`，其中同道CTH目标 `D(v)=5.5+HEADWAY*v`。

不再要求跨道对象是head，不再因本车已有实际前车提前返回。每车只在相邻物理车道、纵向±50m内选真实车；按 `abs(e)`、`abs(dx)`、有符号e及原物理几何键排序，只保留当拍反向也选中本车的边。track只用于跟踪等同性，不排序。

**第二排序项的必要反例。** 两串纵向30m间隔且逐行并列时，某外道车对中道同x车的误差+15与对其后30m车的误差−15绝对值相同；只以有符号e破平局会偏选后车，反向却选同x车，导致本应纠正并列的body没有互选边。优先更小真实abs(dx)使同x对实际互选。该反例已专门测试。

相位和为 `S_i=sum(e_ij/max(1,pair_lanes−1))`，`phase_speed=clip(0.3*S_i,−2,+2)`。有真实前车时保留 `_front_following` 的target/reference，速度仅增加 `0.2*phase_speed` 后夹在0至MAX_SPEED。无前车head继续原 `_request(ego,ego.x+phase_speed/0.3,CRUISE)`。有前车/后车关系或新增实际互选边时，本车formation_state=1；NOA仍直接用原front-following并报0。正在横移、gap接近及必要并入分支仍按E优先级覆盖此速度，最终硬safe_speed保留。

## 两个不能混淆的合同

1. JT的10m/s低速平衡只约束有真实前车的body：同道D(v)、跨道D(v)/2时相位误差为0、body输出10。自由head即使误差0仍请求 `10+0.2*(28.8−10)=13.76`，继续回到巡航；不能为让自由head低速平衡而另改控制。
2. 每条互选边的e交换反对称，JT平均速度因子也对称；节点clip、不同邻接数量以及执行任务覆盖以后，整组速度修正不承诺零和。该系统不是直接单积分一致性模型。

## 初版J/JT的准备区单边图及新身份

初版沿用了E的 `_following` 邻道枚举 `lane<lanes`。准备区中道实际车传入desired lanes=2，终止道实际车传入3，因而中道不枚举仍存在的lane2，而终止道却可在自己的局部计算中“重算出”反向互选，形成单边的假互选。

专门的body反例：lane1与lane2同x700，各有同道前车x730；对lane1调用 `_following(...,2,640)`、对lane2调用 `(...,3,640)`。初版lane1相位修正0、lane2为+.4m/s；实际共同边要求分别−.4、+.4。

J2/JT2分别在固定旧J/JT SHA上只把该一行枚举改为 `0 <= lane < 3`。3是已知道路的物理输入槽数，不是全局交通观测；缺少实际lane2车便没有候选，±50m边界仍保留。pair_lanes与归一化不变。

| 说明标签 | 实际目录/原protocol名称 | SHA256 |
| --- | --- | --- |
| J0，初版已知单边图 | local_phase_coupling；原批仍名J | dd0b7f466de943976af8fe44e1f5b89dfbafe5ea8e86f6f242fcea7a22f75e53 |
| JT0，初版已知单边图 | time_scaled_phase_coupling；原批仍名JT | 443e082742d1400ad03b4381e91cdace35cde522c48b6f11efd375ff89af287e |
| J2，物理邻接 | local_phase_coupling_physical | 895c263f471772482551ea695bc8071e28ad076753cc093762f09a3a43a15689 |
| JT2，物理邻接 | time_scaled_phase_coupling_physical | b415daca538202594a1b12fc768ed3a60a9c30a2f37221625ef1bf3be331df48 |

旧源、旧build、patch/meta及原12合同保留，未覆盖；原批 `20261103_J_JT_screen180_16`、operation `20261103T043322162601Z_staggered-J-JT-local-body-screen16_0c64c65b` 的protocol名称/hash未改。父代理另以fresh批 `20261103_J2_JT2_screen180_16` 运行物理邻接版，本文件不先报告其结果。

## 原文依据与能局部替代的信息

[Meere等2023，官方PDF](https://research.tue.nl/files/322278322/1-s2.0-S2405896323008261-main.pdf)，正文p.5574 §2–3与p.5575 §3.1：式(3)–(6)定义邻车相对位置/目标误差，式(7)为 `u_i=k_c*sum_j w_ji*(p_j−p_i−D_ji)`。邻车相对位置可由LIDAR/radar/camera观测，但论文还明确用V2V交换各车自己的车道位置估计，并设置无向邻接图。

J/JT借的是**每个agent均对实际邻边相对位置误差求和**。本项目可见边的dx、y与相对速度由当前局部观测提供；它不能替代不可见车辆的位置、邻车私有车道估计或共享图。动态互选、CTH叠加与限幅不满足原单积分/可实现图条件，不继承其收敛证明，也不移植其噪声死区。

[Zheng等2021正式原文](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/cth2.12139)，§3.1式(10)–(12)、Assumption 2及Remark 2：其规划速度来自距离势函数的负梯度；Remark 2明确邻车位置经DSRC，边距离由Lidar/radar/camera观测，Assumption 2要求刚性图及目标附近的刚性初态。J的有符号纵向误差不是该论文的距离平方梯度，只借局部邻边耦合层。有限视野实测位置可以提供本车当前边输入，不能据此宣称获得DSRC图或随机来车全局形成保证。

上述具体页段已由官方PDF/出版社原文检索解析核读，不按“distributed”字样推断无通信。全局评价真实几何是允许的，控制仍只使用本车、局部实车及本车既有记忆。

## 冻结与静态验证

- 原12合同在E上48个预期断言/子断言失败，operation `20261103T043034227094Z_J-JT-local-coupling-red_a96e8971`；初版构建 `20261103T043205735682Z_J-JT-local-coupling-build_54c2a125` 及12项绿 `20261103T043206755875Z_J-JT-local-coupling-green_f5a7a198` 均退出0。此绿只覆盖当时12合同，未覆盖后来发现的准备区单边图。
- 单边图反例最初加入临时13项套件时确实失败，operation `20261103T043444627585Z_J-JT-preparation-adjacency-red_875ddf83`。随后按父要求恢复原12合同，把新反例独立放入 `tests/test_physical_phase_adjacency.py`；未修改已冻源及旧protocol。
- 独立新4项合同在旧J/JT上2个预期失败，`20261103T043713139697Z_J2-JT2-physical-adjacency-red_90df9e8d`。
- J2/JT2构建 `20261103T043802446530Z_J2-JT2-physical-adjacency-build_89637c23` 退出0；AST仅_following变化，反向替换精确恢复各固定旧父源。
- 新4项与原12项联合：`20261103T043803219979Z_J2-JT2-physical-and-original-contracts-green_2f3c2c7d`，**16项、101子测试通过**。其中每版600个随机NOA完整Command/Memory对E相同；新4项还检查lane2缺失时两版对各旧父源的300场景×三模式精确等价。

静态通过不代表已形成24/45车完整交错。后续必须检查原实际轨迹的同道CTH、跨道15m巡航错位、完整层与持续时间；保留未形成、末端余车、安全失败与交通负效益，不能用0/1或TT代替几何验收。

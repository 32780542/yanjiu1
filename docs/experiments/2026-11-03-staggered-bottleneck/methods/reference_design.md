# 局部交错空隙与3→2交接：参考与独立候选

2026-11-03。基线固定为 `177f7a32088fb69efcc94d9acb72863e7e00e787` 的511行 `native_rules.py`。本文件是设计与源码阅读记录，不是交通性能结论。只用前200m/后100m实测邻车、本车地图/自身记忆；track只用于跟踪等同性，不用于优先排序。没有成员标记、车型真值、他车意图、全局槽位或全组调度。

## 实读MATLAB所得

本轮直接读取 `D:/matlab_huipu_2000` 的活跃 `formationControl.m`、`formationControlNormal.m`、`singleVehicleCalculate.m`，及 `pathRelativeCalculate.m`、`getRelativeDistance.m`、`assign.m`、`BrysonDenhamContinuous.m`、`BrysonDenhamEvents.m`、`trajectory_planning.m`；另核 `mainmain.m` 的配置、调用及执行片段、道路生成、备用控制入口。未运行MATLAB或SNOPT；未把lib/nlp依赖当成研究方法。完整旧调用链核查见[2026-10-29核查](../../../2026-10-29-MATLAB车辆控制调用链核查.md)。

| 实际机制及源码锚点 | 能借的局部含义 | 不可照搬的部分 |
| --- | --- | --- |
| `formationControlNormal.m:21–60`：同道30m，相邻道15m错位 | 横移利用实际错位形成的空隙，不能只追整齐层数 | 根据全组人数一次生成整套目标 |
| `formationControlNormal.m:82–178`：联合assign、coordinateMap逐相冲突与等待 | 释放一个实际占用，另一车再进入；静态末态可行还不够 | 全组目标交换、以循环索引决定后车等待、共同阶段表 |
| `pathRelativeCalculate.m:35–55`：先作可兼容纵横移动，再补余下轴向移动 | 横移与纵向相对速度应相容 | 这是已集中分配后的路径，不能声称是局部图算法 |
| `singleVehicleCalculate.m:16–17,63–66`及两个Bryson回调：固定5s阶段、末速vF、最小加速度平方积分 | 不仅看当前位置，还看进入时的速度和调整代价 | 不移植求解器、全组路径或33.33m/s追赶优势 |

`getRelativeDistance.m:12`的加权式被下一行覆盖，实际是 `deltaX²+deltaY²`。主入口每50步/5s重算；只执行第一阶段速度及换道。`New_Edge.m`两段实体均三道，原程序不能直接充当本项目实体3→2同工况对照。`applySmoothSpeedControl.m`虽定义舒适限幅，但不在此活跃调用链。

## 原文核对及证据边界

- [Cai等作者预印本](https://arxiv.org/pdf/2103.10287)，§III-A/Fig.4明确以交错留空便利换道；§III-B是整组一对一分配；§III-C/IV是相对路径与分阶段执行；式(14)给位置/速度递推，式(15)以加速度平方为代价并约束阶段末位置及末速。它支持关注过渡冲突与速度协调，不证明下述局部候选。期刊书目信息另核[正式论文](https://ietresearch.onlinelibrary.wiley.com/doi/abs/10.1049/itr2.12249)。
- [Rupp等2018出版社摘要](https://www.sciencedirect.com/science/article/abs/pii/S2405896318307808)说明无通信合流及拓扑选择。正文PDF本轮访问403，不能报告滑模公式、感知半径或具体拓扑定理。[作者本人官方海报](https://tugraz.elsevierpure.com/ws/portalfiles/portal/11137142/SummerSchool.pdf)直接列出按车道、相对位置、相对速度选择前驱，并将速度适配与横移分开；海报不是论文正文。
- [UPC原始学位论文](https://upcommons.upc.edu/server/api/core/bitstreams/b296e62e-415d-4235-88c0-e21e6743e9f2/content)的搜索索引预览§5.2.1式(14)给 `f_i=(x_0-x_i)+k(v_0-v_i)`，按正负最近者区分前后关系。这是Rupp参与指导的另一原始资料，本轮全文访问也403；只作为短时相对运动的参考，不能归为Rupp2018已读正文。

本轮不再提出已独立试验的切换松弛R/TR。下面三项各自只改变一条几何或机会选择假设。

## A：实际空隙的1秒可行区间投影

**假设。** 车已位于可用交错空隙内时，无须再追F/R中点。局部输入是实际目标道前车F、后车R的当前位置/速度及本车速度；沿用实际gap跟踪。

令C=8m、T=1s、d=x目标−x本车。要在恒速外推下从现在至T均保持F/R顺序及C车头距，允许本车目标位置区间为

```text
low  = x_R + C + max(0, (v_R-v_ego)T)
high = x_F - C + min(0, (v_F-v_ego)T)
target = clip(x_ego, low, high),  当 low <= high
```

区间为空或只有单侧邻车时沿用原中点/单侧规则；速度参考仍是原F/R均速，安全clear与safe_speed保持。该区间是恒速名义几何，不是对邻车未来动作的承诺。父代理候选只对organized分支启用，NOA保留原目标。

**差异/预期。** 基线始终以 `(x_F+x_R)/2` 为双侧目标；A让安全空隙内的车直接横移，减少无必要居中加减速。它不改变当前3→2交接、相位或同道CTH。入口 `_merge_target`，父候选目录 `candidates/gap_projection`。

## C：有效腾位交接（本轮独立实现范围）

**假设。** 只为眼前确实阻挡终止道头车M、且现在能进入左道实际空隙的中道车H发起腾位。基线 `_make_room` 的options只有局部counts与x窗口，没有“能腾”和“腾了有用”的筛选；被左道堵住的H也会进入prepare_room并追左道gap。

完整保留原局部ending头车、anchor、90m/60m窗口、counts不平衡条件和 `max(x)` 几何排序。仅给原options加三个判据：

```text
before = clear(M, current_observed_cars, lane=1)
eligible(H) = (not before)
              and clear(H, current_observed_cars, lane=0)
              and clear(M, current_observed_cars without H, lane=1)
helper = original_max_x(eligible original_options)  # 空集则None
```

`clear`沿用当前实测/1s走廊检查。这里的“without H”只用于评估H离开中道后释放的走廊；它不是把H提前从实际安全检查删除。执行器仍按实测横向占用检查M何时真正能进入，不能把H被选中等同于已完成横移。无需新增Memory、共享阶段或新CF门槛。

**怎样利用交错空隙。** 若H已经处于左道实际交错缺口、它又是M当前唯一走廊阻挡者，先由H用现成空隙左移，再由M观察中道真实释放后进入。若M本来就能并入，C避免为局部计数平衡额外先搬一辆H。若移走H仍被另一实车阻挡，不启动无效腾位。

**与Cai的准确关系。** 借的是“过渡时先解除真实占用冲突”，三条判据由现有代码及局部几何自行推导。没有复制其全组图、目标或最优/安全证明。它可能放弃需要先纵向调位才腾得出的机会；这正是必须记录的代价，不能预先称成功。

入口仅 `_make_room` 的options。独立目录 `candidates/effective_handoff`；与A/D分别消融，第一次不叠加。

## D：存续车道保持原交错相位

**假设。** 从三道变成两道后，存续lane0/1本来的0/15m已经是合法交错；不必仅因车道总数减一把两者相位翻为15/0。

当前 `phase(lane,n)=15*((n-1-lane) mod 2)`：n=3时lane0/1=0/15；n=2时=15/0。因此同一实际队首对的相对相位误差会跳30m。D改为

```text
phase(lane,n) = 15*(lane mod 2)
```

并让 `_fill` 内phase复用同一定义，防止跟随目标和补位几何相矛盾。三道全不变，存续两道继续0/15；不增加空间渐变、切换时长或全局基准。

**差异/预期。** 避免无障碍的存续车道头车为重新翻转交错次序相互追赶/制动，保留原可用空隙。它解决相位标签翻转，不等同于先前J/K的空间渐变或速度导数补偿；也不保证任意随机车流自动形成更大队形。该候选由几何直接推出，文献不提供该特定代码修正的证明。父代理实现入口 `_phase` 与 `_fill`。

## 共同验收边界

30m同道巡航间隔被插成15m+15m时，8m横移clear可通过，但CTH的巡航平衡仍要求每对约30m。上述方法不能消除实体3→2所需的空间伸长或车流守恒，只研究减少额外组织动作与相位冲突。

C先以窄范围测试验证：头车本来可入不腾位、helper左道受阻不选、移走helper仍受阻不选、存在有效腾位时保留原选择、ID重标/观测顺序及范围外车辆不改变决策、NOA物理命令和记忆不变。静态通过之后仍须由父代理冻结源码跑同输入交通筛查；本文件不报告没有运行的交通数据。

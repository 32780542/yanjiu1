# 阶段4补齐验收：独立NOA基线

2026-09-11；唯一研究根目录 `D:\yanjiu1\keyan1`。接续“继续完成研究规格阶段4”中断前已经完成的控制修复与真实SUMO实验，本次完成新一轮核验、补充包封存、独立重放、文档及交付清单。

**阶段4在已登记小案例和数值门槛内通过，M1完成，可进入阶段5小规模交错机制研究。** 固定完整真实SUMO运行的14个普通案例全部通过；补充3个场景的6个采样变体驾驶门槛及3项采样比较全部通过。预声明严重急刹压力案例仍发生碰撞并保留，不计为普通驾驶成功。当前没有编队、交通效率改善、能耗改善或实车安全结论。

- [固定完整运行](D:/yanjiu1/keyan1/results/phase4/runs/20260910T232224392627Z_ab0de887/validation.json)：`20260910T232224392627Z_ab0de887`。
- [本次完整重放](D:/yanjiu1/keyan1/results/phase4/replays/20260911T120126895260Z_f9ce3be5/validation.json)：`20260911T120126895260Z_f9ce3be5`。
- [固定补充采样运行](D:/yanjiu1/keyan1/results/phase4/completion_20260911/sampling_runs/20260910T232224409038Z_4712f90d/validation.json)：`20260910T232224409038Z_4712f90d`；封存后的标准重放、前后文件核对见[收尾独立审查](D:/yanjiu1/keyan1/docs/phase4_closure_review.md)。
- [本次141项测试](D:/yanjiu1/keyan1/results/phase4/closure_20260911/tests.log)、[基础核验](D:/yanjiu1/keyan1/results/phase4/closure_20260911/verify.log)、[逐子步重算摘要](D:/yanjiu1/keyan1/results/phase4/closure_20260911/summary.json)、[修复前后PNG](D:/yanjiu1/keyan1/results/phase4/completion_20260911/figures/phase4_completion.png)与[SVG](D:/yanjiu1/keyan1/results/phase4/completion_20260911/figures/phase4_completion.svg)。

## 原五项失败的关闭证据

旧失败基线为 `20260910T185443571873Z_3776ab63`，原269份封存证据没有改变。[旧验收报告](D:/yanjiu1/keyan1/docs/archive/before_phase4_closure_20260911/docs/phase4_acceptance.md)中的9/14通过结论保留为历史事实，不能用于描述当前固定版本。以下数值由相同工况与相同评估器得到；没有修改普通/压力归类或放宽门槛。

| 原失败项 | 旧结果 | 当前固定结果 |
|---|---|---|
| 停车再起步 | 实际jerk峰值49.999 m/s³ | 18.53 s首次达到实际零速，随后重新起步；30 s末速度9.690 m/s；实际jerk约2.000 m/s³ |
| 无空隙终止车道 | 16 s末仍为1.477 m/s | 14.83 s首次达到实际零速；16 s末x=993.132 m、v=0，保持在原道路硬界内 |
| 稀疏队列后并道 | 未完成，跟踪最大2.259 m，实际jerk100.470 m/s³ | 7.08 s完成2→1车道变更；12 s末x=1088.769 m、y=4.960 m；跟踪最大0.082111 m、P95 0.081211 m，实际jerk约2 |
| 可见邻车切入 | 实际加速度最低−5.206 m/s²，舒适失败 | 最低−2.999766 m/s²，原−3舒适界内；跟踪最大0.102597 m，实际jerk约2 |
| 普通换道采样减半 | 最大同刻位置差1.739220 m | 0.009580175 m，低于原0.15 m容差；航向差0.000521704 rad，低于0.02 rad |

jerk使用原积分子步的**实际加速度差分**，不是执行器jerk；约2的末位浮点误差按原 `phase4_numeric_slack=1e-6` 判断。停车0.005 s积分对照也保留在[独立复算日志](D:/yanjiu1/keyan1/results/phase4/completion_20260911/evidence_review/stop_metrics_final.log)，没有将有限数值检查扩大成连续时间有界jerk证明。

## 完整与补充驾驶结果

| 固定普通案例 | 综合门槛 |
|---|---|
| 巡航速度阶跃、车道保持、慢前车跟驰 | 3/3通过 |
| 停车再起步、普通换道含采样对照、连续两次换道 | 3/3通过 |
| 目标车道高速后车、可见切入 | 2/2通过 |
| 有空隙并道、稀疏队列后并道、无空隙停车 | 3/3通过 |
| 两车独立NOA、跨edge、参考对象退出感知范围 | 3/3通过 |

完整套件包含15个案例、16个真实SUMO变体（含压力失败与正常换道半采样），共2,222次SUMO物理推进、2,322个受控车决策区间、90,060个车辆积分子步。普通案例的任务、跟踪、舒适性及独立车身/道路/硬包络审计全部通过。初始化警告0；物理区间1条SUMO碰撞警告来自压力案例。

| 控制/感知0.1→0.05 s，积分保持0.01 s | 同刻最大位置差（m） | 最大航向差（rad） | 结果 |
|---|---:|---:|---|
| 普通换道（正式门槛） | 0.009580175 | 0.000521704 | 通过 |
| 可见切入（补充） | 0.021306738 | 0.001028201 | 通过 |
| 有空隙并道（补充） | 0.006364426 | 0.000216408 | 通过 |
| 无空隙停车（补充） | 0.024415468 | 0 | 通过 |

后三项补充共6个真实SUMO变体、1,410次物理推进、102,000个车辆子步，各自驾驶门槛均通过，初始化与物理警告均为0。无空隙半采样在15.06 s到实际零速，仍满足原16 s时限。稀疏队列后并道的0.015864 m采样差另有离线回归与独立因果探针支持，不冒充此补充包中的第四项真实SUMO对照。

普通换道两组跟踪最大误差分别0.071059/0.065529 m，P95分别0.070937/0.065419 m，均满足原0.5/0.3 m门槛。固定原控制命令、仅将积分0.01→0.005 s时，最大位置差1.038×10⁻⁶ m、航向差6.427×10⁻¹⁰ rad，满足0.02 m/0.002 rad容差；两辆车的6,000个细化子步重放误差为0。这与重新运行控制器的采样对照分别判断，不称完整收敛证明。

## 实现修复与参数

相对旧失败版本，新增 `tests/test_phase4_completion.py`；修改 `noa/controller.py`、`noa/prediction.py`、`simulation/noa_clock.py`、`configs/phase4.json`、`tests/test_phase4_controller.py`。完整运行冻结77份代码/配置；本次收尾未修改该冻结版本的生产代码、配置和测试。

修复包括：保留有符号的本车制动初态、以连续速度约束处理停车接近、提前释放低速制动；使并道候选使用的纵向请求与实际执行一致；将世界横向反馈转换为法向加速度时扣除纵向加速度分量；统一贝塞尔起点/中点/终点的浮点等时刻归属；新参考在既有0.5 s行为节拍启动，连续反馈使用当前可见状态的半周期近似。完整推导及限制见[方法依据](D:/yanjiu1/keyan1/docs/phase4_completion_methods.md)。

参数登记当前264项。相对旧失败版本：新增响应预算0.3 s、停止速度增益1/s、终末弱制动0.005 m/s²、舒适停车位置预留3 m；停止捕获速度1→3 m/s；旧0.5 m/s²保持制动参数由终末弱制动机制替代。它们是本研究未标定开发设置，不是外部论文或品牌车辆标定值。原模型、车辆硬界、感知范围、舒适阈值、工况与评估代码保持原字节。

## 证据封存与独立审查

本次新运行的141项完整测试在97.402 s通过；基础核验通过，四档需求计划数仍为588/717/830/976。阶段3固定运行 `20260910T163533938451Z_2dcd59f7` [本次重放](D:/yanjiu1/keyan1/results/phase3/replays/20260911T120207532541Z_21a47adb/validation.json)通过，其242份证据未改变。

完整阶段4固定重放复算16变体、90,060个车辆子步及6,000个细化子步，最大数值差0；1,000次反事实比较一致，移除可见邻车后85次动作变化保留非空洞正例；9类篡改拒绝。封存270份文件哈希一致，当前源码与冻结源码无差异。重放不重启SUMO，只核对原实跑读回并重建决策、记忆和物理过程。

补充生产入口当时没有整包封存；本次明确采用**运行结束后的追加封存**。独立审查于2026-09-10 23:28:33.535982 UTC记录的156个既有文件，在本次封存前全部相同。封存仅修改 `metadata.json` 的来源/时间信息，新增 `sealer_snapshot.py` 与 `evidence_hashes.json`；轨迹、动作、初态、指标、故障注入与结果均未改变。现有157个受哈希保护文件，清单自身不自哈希。不能追溯声称原生产开始时就有此保护。

补充包自带逐案例模型、道路、初态、策略和代码快照；完整网络/参数登记等输入快照引用相同冻结版本普通运行的 `input_snapshot/`，见[共享输入逐文件映射](D:/yanjiu1/keyan1/results/phase4/closure_20260911/summary.json)中的 `shared_inputs`。没有把补充包描述为最初就自带完整输入快照。

此前[机动审查](D:/yanjiu1/keyan1/docs/phase4_completion_maneuver_review.md)与[证据审查](D:/yanjiu1/keyan1/docs/phase4_completion_evidence_review.md)保留原时点结论；最后一项封存缺口及标准整包重放由[本次收尾审查](D:/yanjiu1/keyan1/docs/phase4_closure_review.md)关闭。预备筛选的 `diagnostics.reason/lead_gap_m` 不一定代表最终机动请求的领车来源，是已登记的非阻塞诊断限制；应结合实际动作和最终预测字段解释。

旧首次运行、旧9/14版本、初次14/14但补充未通过的中间版本、未封存历史补充、所有失败/中断探针均保留。新[交付清单](D:/yanjiu1/keyan1/results/phase4/closure_20260911/delivery_manifest.json)独立保存，旧交付清单不回写。

## 明确保留的失败与外推边界

严重急刹压力案例在t=2.2 s、22个物理区间后终止，独立扫掠在2.10–2.20 s检出11个碰撞子步；实际减速度到−4.4 m/s²，舒适性亦失败。成功重放该前缀不消除碰撞。

邻车横向预测仍假设已测惯性横向速度持续、额外横向加速度界为0；无法覆盖任意突然横向动作。已执行参考失效后保持参考并制动不保证总能避碰，独立审查的真实阻挡反例仍碰撞。制动距离筛选仅针对当前立即下发指定制动命令的时钟语义，不是任意延迟后再制动的可达上界。

终末弱制动在速度投影到0时仍有约0.005 m/s²实际加速度小跳变，数值jerk结论限定于原协议与已检查步长。直路、有限范围理想观测、简化运动学、固定小案例均是适用范围。基线提供任务/平顺性/风险记录；正式需求下的系统通行效率、能耗和交错增益尚未评估。

## 复核与后续入口

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S run.py verify
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S run.py test
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S run.py phase4-replay --run-dir results/phase4/runs/20260910T232224392627Z_ab0de887
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S run.py phase4-replay --run-dir results/phase4/completion_20260911/sampling_runs/20260910T232224409038Z_4712f90d
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S results/phase4/closure_20260911/finalize.py verify
```

重新执行 `run.py phase4` 创建新尝试，不覆盖固定结果；本轮沿用已完成的真实SUMO实跑，并以源码一致性、全套测试和新重放核对，无需把重复生成同一轨迹当作额外研究证据。下一入口为[阶段5局部交错形成与保持](D:/yanjiu1/keyan1/docs/phase5_entry.md)，本轮仅交付入口，不提前实施阶段5或运行正式收益矩阵。既有phase01工作区未提交、未推送，未安装依赖、未复制父目录废案。

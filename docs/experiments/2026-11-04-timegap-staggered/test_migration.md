# C8历史与C12实际安装测试迁移

2026-11-04。最初生产C8的迁移与状态红绿记录保留在下文；root随后安装C12，当前合同及最新执行见末节。本单元只编辑`variants/phase5g_pure_formation/tests`与本文；不改规则、engine、README，不操作Git，不运行旧阶段整套。按writing-plans记录当前单元，执行顺序如下。

## 直接依赖盘点

15个文件直接调用当前native_rules：`test_braking_cost_fill`、`test_chain_transform`、`test_common_pair`、`test_ending_pair_scope`、`test_formation_state`、`test_global_reference`、`test_head_group_rules`、`test_local_formation_balance`、`test_local_staggered_rules`、`test_native_rules`、`test_native_sumo`、`test_own_lane_execution`、`test_physical_following`、`test_time_headway`、`test_user_timegap`。

`test_native_comparison`、`test_bottleneck_attribution`只把该文件列为磁盘源快照，不要求旧算法接口，保留。`archived_rules_source.py`仅服务旧common-pair与冻结P等价测试。

## 迁移步骤与范围

- [x] 通过`run_logged.py`记录受影响组的迁移前实际失败，不修改生产以迎合旧接口。
- [x] 删除7个已撤销算法专属文件的50个用例：braking-cost fill、A chain transform、common pair、ending pair scope、head-group、local formation balance、local staggered rules。旧D1/A反例与历史实现仍由既有版本历史和研究证据保留，不伪装成当前C8合同。
- [x] 重写`test_native_rules`为C8合同；迁移`test_physical_following`、`test_time_headway`，保留`test_user_timegap`。
- [x] 更新`test_own_lane_execution`的自身pending与真实旧fixture用途；撤销旧自动1→2行为要求，保留原物理执行延迟、严格完成和邻车不泄露pending。
- [x] `test_formation_state`保留直接0/1统计与真实SUMO落盘，删除仅证明历史P控制等价的用例及无消费者的archive helper。
- [x] 顺序运行实际安装的native合同组、native_sumo、global reference、formation_state、own_lane、native_comparison、bottleneck attribution。真实SUMO最多一个job，日志走`run_logged.py`。

本单元为既有生产实现迁移测试，不写生产修复。若当前合同暴露实际缺陷，保留失败并提交root判断；不会用重命名、跳过或仅断言实现细节来消除失败。

## 当前测试合同与数量

| 当前模块 | 测试数 | 覆盖职责 |
| --- | ---: | --- |
| test_native_rules | 20 | 近50m建链、远200m维持与真实前驱替换/释放；200m道路边界、前200/后100观测裁剪、实际运动跟进、不读取邻车pending、formation不自由换道、2→1→0单向接入、真实F−D与后侧D、半D误差不增、ID重标/顺序不变 |
| test_physical_following | 8 | 共用制动、跨线双道占用、相对速度8m走廊、低速entry-D≥16、真实前车优先、低速远孔假停车最小反例 |
| test_time_headway | 7 | 精确h=.85、D(v)、巡航间距29.98m、同前车动态跟驰 |
| test_user_timegap | 8 | 用户时距/相位/可见缩道/反应式NOA合同；原文件保留未改 |
| test_formation_state | 18 | 实际已选200m跟驰/真实slot关系=1、NOA=0、关系消失、直接0/1统计、真实SUMO落盘；保留旧C8五输入，分别验证仍等价与有意改变的行为 |
| test_own_lane_execution | 10 | 真实旧pending race、严格完成/超时、自身pending与邻车信息隔离、真实native适配器 |
| test_native_sumo | 17 | 原生需求/道路/执行/共用safe_speed/失败与碰撞保存/真实短测 |
| test_global_reference | 15 | 独立集中参考保持原合同，未因C8改动 |
| test_native_comparison | 31 | 真实磁盘记录复算、0/1状态完整性、配对与不完整运行保留 |
| test_bottleneck_attribution | 14 | 实际越线/暴露积分/删失与DID输入比较 |
| **受影响安装组** | **148** | 当前C12测试定义总数；C8统一状态版当时为144项 |
| test_native_recovery（另跑） | 15 | 独立磁盘恢复评价器，未修改 |
| 根tests/test_native_gui_entry.py（另跑） | 9 | 根入口参数、GUI连接生命周期与check，不修改root测试 |

`run_native_contracts.py`只将真实variant与tests路径放到导入入口，并按显式模块列表顺序运行；没有旧阶段全量发现或并行SUMO。

C8迁移当时受影响安装组的明确入口（当时144项；该次补状态后未再次执行整组）：

```powershell
python -X utf8 -B scripts/run_logged.py --label c8_native_contracts --timeout 240 -- python -X utf8 -B variants/phase5g_pure_formation/tests/run_native_contracts.py test_native_rules test_physical_following test_time_headway test_user_timegap test_formation_state test_own_lane_execution test_native_sumo test_global_reference test_native_comparison test_bottleneck_attribution
```

C8统一状态版最后实际执行的窄范围状态入口（当时16项，含原5个固定控制/Memory场景）：

```powershell
python -X utf8 -B scripts/run_logged.py --label c8_unified_relation_flag_green --timeout 90 -- python -X utf8 -B variants/phase5g_pure_formation/tests/run_native_contracts.py test_formation_state
```

旧算法测试退出的是当前安装回归，不是删除科学失败证据：D1 Φ/响应成本/640m层、A前驱追色、固定30/15m历史H等价不再是C8接口。旧实现与反例保留在已有06c504/2a49a13历史及对应实验目录，本单元未操作Git。

原`own_lane_request_race.json`继续使用，但其历史自动1→2不再当作C8必须产生的动作；测试显式注入本车已经提交的请求，验证真实延迟、横移和严格完成。完成后若道路仍不可见，不凭旧动作推断缩道；新观察到道路后才再检验必要2→1。

## 实际执行与状态语义纠正

全部命令经`python -X utf8 -B scripts/run_logged.py --label ... --timeout ... -- <命令>`落盘，真实SUMO按单job顺序执行。

| 操作/日志目录（results/operations下） | 实际结果 |
| --- | --- |
| `20261103T190651822425Z_c8_native_migration_before_fb7fafb0` | 原测试对当前C8：224项，64失败、20错误；旧gap/joining/_fill、640先验与固定间距等不再成立 |
| `20261103T191003461687Z_c8_native_contract_first_cb79a91e` | 新核心65项，1失败：选中远前车却formation_state=0 |
| `20261103T191055551829Z_c8_native_installed_regression_a37756e0` | 142项安装组通过；当时含一个错误的旧状态断言，见下文，不将其用作正确状态语义的证据 |
| `20261103T191156275759Z_c8_native_recovery_disk_7984e767` | 15项磁盘恢复评价通过 |
| `20261103T191157214273Z_c8_root_gui_entry_tests_ea9d0a64` | 根GUI入口9项通过 |
| `20261103T191200348693Z_c8_root_entry_check_86938b86` | `runrun.py --check`退出0 |
| `20261103T191223706141Z_c8_root_headless20_smoke_c3f69795` | 根入口真实20秒来车：30请求/30发车/30完成，drained、碰撞0、传送0 |
| `20261103T191312332416Z_c8_selected_front_flag_red_6bbd2288` | 恢复用户合同后，远前车关系1的测试实际红；50.01/200m两个子断言为0≠1 |
| `20261103T191453136949Z_c8_selected_front_flag_green_b0759df5` | root仅补linked后，flag相关15项全绿，含3秒真实SUMO落盘与5个归档控制输出对照 |
| `20261103T193745129998Z_c8_real_slot_anchor_flag_red_9d44edc0` | far-front仍绿；新增真实slot关系的两个子例state0≠1，运动/Memory断言均已通过 |
| `20261103T193942312667Z_c8_unified_relation_flag_green_29572fc4` | root统一非NOA关系出口后，最终flag16项全绿；原5场景非state控制与Memory对照全部相等 |

首轮失败曾被错误地按旧50m相位图范围解释，将已选择的200m真实跟驰关系期望改成0，得到上述142项通过。root纠正了用户合同：**已有实际关系即输出1，允许仍在调距；50m不能否认已主动选中的200m真实CTH关系。** 测试已恢复期望1并先记录红。root随后只补远孔分支`linked=1`，速度、车道、target、reference和Memory均不改变。本单元没有改生产。

第一次15项按远孔状态补正版实际磁盘执行，最终16项按统一关系出口版执行；其余控制/物理/磁盘检查复用前述结果，按root要求不重复整组或smoke。因此没有声称“当前144项在状态补正后重新全跑”。5个固定对照输入来自冻结的旧C8归档，覆盖低速远孔、带phase的远孔、正常跟驰、NOA和真实左slot；当前磁盘的非state Command与自身Memory逐项相等。小型JSON夹具自包含，运行不依赖tmp归档路径或旧D1接口。

根headless结果位于`tmp/staggered_bottleneck/20261104_C8_root_smoke/20261103T191224176087Z_lane_drop_transform_s1_7813ba`。该smoke在状态补正前运行，只复用运动/安全/排空结果，不将旧participation值当作新状态版结果。GUI实际窗口由root另行验证，本单元未打开或修改GUI。

## C8迁移当时的结论

C8当前测试接口已完成迁移；共用安全、本车执行反馈、局部信息边界和真实磁盘统计保留。测试暴露的200m关系漏报已交root并由其作纯状态补正，相关红绿与不改变控制的对照证据已保存。没有改驾驶规则以迎合旧测试，也没有重跑旧阶段整套。随后新增的真实slot关系遗漏见下节。

## 后续统一“实际选定引用即有关系”的合同

新增边界：lane1本车x900/v28.8，仅有lane0的实际P在x960，无同道或虚拟前车。全新Memory不会主动发起补位；但已有自身`Memory(lane_target=0,front=1)`或自身pending=0时，会继续真实slot：lane0、target930.02、reference1、speed30.6012，Memory不变。这种已选定并实际跟驰的关系也必须报告1。

`20261103T193745129998Z_c8_real_slot_anchor_flag_red_9d44edc0`实际运行两个方法：原far-front方法通过；新slot方法的held-plan、own-pending两个子例只在state 0≠1处失败，运动输出和Memory断言均先通过。该边界说明仅在远孔分支补linked还不够，合同应覆盖最终所有非NOA真实reference。新增测试使当前flag模块16项、受影响组144项。

root已从原C8安装统一出口版：最终非NOA flag为`int(linked or reference is not None)`，远孔分支恢复原二元赋值，NOA早返回仍0。实际磁盘317行，单文件SHA与root冻结标识`279e676a1de7b542cc3074523cff6a4ef151710662e57e113ebb5a5aa8d8377c`一致。最终仅运行`test_formation_state`：16项、1.323 s、退出0；包括far-front、held-slot、own-pending、真实SUMO状态落盘与原5场景的控制/Memory不变对照。未重跑整组、根smoke或旧阶段。本单元没有编辑生产，当前没有未处理的flag测试失败。

## C12关系生命周期迁移

root安装C12后，普通纵向关系的合同有意改变：真实前驱在近50m内先建立关系；已有关系可在前200m内继续使用当前真实前驱，即使新前驱替换了旧track；无真实前驱或失见则释放。fresh80不会主动建链，`Memory.front`保存普通已选主引用，仍不能读邻车私有状态。真实已选关系的0/1语义不变，NOA仍为0。本次只迁移三个测试文件，不修改生产、引擎或历史夹具。

- `test_native_rules`新增两个生命周期方法，分别覆盖50m/50.01m/80m/200m边界，以及实际前驱替换、旧前驱仍在别道可见、200.01m失见、空观测释放和fresh80返回不重建。formation与transform均运行，并直接断言动态D与正常跟驰请求。
- 两个低速远孔反例现在明确给本车已建立的Memory；继续验证C6松弛基准合成错误不会将远孔闭合变成假停车，不再要求fresh远车主动追赶。
- 原C8五输入JSON完整保留。NOA与真实slot仍比较完整非state控制及Memory；近距正常跟驰保持控制，但明确要求普通主引用写入Memory；两个fresh远孔输入改为新合同的明确数学断言，并保留旧reference与旧速度作为方法变更证据。旧C8“5场景完全等价”的绿测仅对当时C8状态修正版有效，不延伸到C12。
- far-front状态用例改为已有关系且新前驱track不同，验证实际选定的200m关系仍报告1。真实slot、NOA、关系消失与直接0/1统计继续保留。

`20261103T204014440914Z_c12_pure_chain_contracts_c6ffb65b`经`run_logged.py`执行纯规则及无SUMO状态/夹具组：**60项，0.012 s，退出0**。静态发现当前10模块共148项。`test_user_timegap`保留未改。该纯组没有启动SUMO；收到root空1槽通知后，完整受影响组按单job实际运行一次。

当前完整组实际入口：

```powershell
python -X utf8 -B scripts/run_logged.py --label c12_native_installed_regression --timeout 240 -- python -X utf8 -B variants/phase5g_pure_formation/tests/run_native_contracts.py test_native_rules test_physical_following test_time_headway test_user_timegap test_formation_state test_own_lane_execution test_native_sumo test_global_reference test_native_comparison test_bottleneck_attribution
```

`20261103T205751291328Z_c12_native_installed_regression_1ce11d3c`实际结果：**148项，16.150 s，全部通过，退出0**（wrapper 16.89 s）。覆盖已安装C12规则、新关系生命周期、真实SUMO状态落盘、本车pending/横移执行、共用安全、真实磁盘比较与归因。未修改源或引擎，没有跳过失败，没有重跑旧阶段、根smoke或GUI。进程已结束，并已通知root释放仿真槽。

root随后另跑最终安装版实际GUI：`20261103T205840996769Z_C12-final-live-GUI_af56d19a`，20秒需求，30请求/发车/完成，gui=true、drained、碰撞0/瞬移0，实际仿真到61.2秒，耗时33.623秒。Windows窗口列表实际返回`native.net.xml - SUMO 1.27.1`；一次截图调用因参数形状不符未成功，窗口结束后没有仅为截图重跑。此前C8界面的43.3秒运行截图仍是界面证据；最终C12以实际GUI进程、窗口识别和落盘结果为据。

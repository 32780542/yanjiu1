# 阶段5B：正式R5六个竞争失败前缀的SUMO/模型几何差异

2026-09-13，只读诊断。正式来源固定为 `variants/phase5_r5_completed/results/phase5_r5/runs/20260912T222655136582Z_203b85c8`，相对路径均以 `D:/yanjiu1/keyan1` 为根。

**现有证据支持的触发机制是：两车的前保险杠先映射到同一SUMO车道，默认非sublane碰撞检查按车道纵向占用判定重叠，模型则检查具有实际质心、航向和宽度的二维车身扫掠。** 六个失败末端仍有1.0413–1.3000m的模型车身横向投影间隙，不能由此删除SUMO失败、称其为false positive，或外推后续轨迹安全。本轮没有重新运行车辆、修改桥接、控制器、参数、旧source/config/results，或启动阶段6。

## 保存的证据和范围

逐值证据保存在[summary.json](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_evidence_20260913T0410/summary.json)、[六行CSV](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_evidence_20260913T0410/rows.csv)和[每例最后六帧](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_evidence_20260913T0410/tail_details.json)。尾帧包含所有四车的原初态、末态、动作、原SUMO读回、车身角点，以及按冻结桥接代码推导的待提交`moveToXY`参数；后者不是新增的TraCI线级日志。

提取共读取并保存88个输入的SHA256，读取前后不变；其中57项逐项绑定到原code/evidence/input清单，九个所读运行源码与封存快照字节相同。原evidence manifest SHA256仍为`3bdd28573d5fca50656869b4c745836535a61924b202c88001e4a0fd7c294b76`，原code manifest仍为`fcc7226e0d17fb85ce9f1e56e2b6e2dca1e71544b3e5f4ce253cf3984adaddd7`。详见[输入哈希](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_evidence_20260913T0410/input_hashes.json)与[绑定验证](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_verification_20260913T0413/verification.json)。这不是再次执行17变体的标准语义重放。

六例所有已保存姿态区间包含失败尾的10个0.01s子步。使用封存`BodyPose`与`swept_collision`，仅重算这些姿态的全部车对，共13020次扫掠，碰撞仍为0。没有再积分、再决策或继续失败后的轨迹。另用独立的世界y轴投影间隙与角点运动上界，逐子步检查left/right线性插值扫掠；最小间隙下界仍为1.0248891057790854m。此下界只覆盖保存子步的线性姿态插值，不证明任意未采样真实非线性运动。

## 六个失败尾段的实际数值

表中物理时刻四舍五入到0.1s；机器精度原值保存在CSV/JSON中。首次同道均为`upstream_1`，当时collision reports=0；失败读回均为2，teleport starts=0。原日志只定位`right`与`left`，并非四车都实际参与碰撞。

|变体|首次同道：物理/native s|失败末端：物理/native s|日志time s / stage|失败末端左右前保险杠y m|左右质心y m|末端车身y轴间隙 m|
|---|---|---|---|---|---|---|
|competing off|2.7 / 2.9|2.8 / 3.0|2.90 / move|3.528454635 / 6.371545365|2.823707471 / 7.076292529|1.158543769|
|competing on|4.6 / 4.8|4.7 / 4.9|4.80 / move|3.463659252 / 6.436340748|2.724744227 / 7.175255773|1.300035772|
|same_private_state off|2.7 / 2.9|2.8 / 3.0|2.90 / move|3.528454635 / 6.371545365|2.823707471 / 7.076292529|1.158543769|
|same_private_state on|4.2 / 4.4|4.3 / 4.5|4.40 / move|3.598232689 / 6.301767311|2.830977016 / 7.069022984|1.041256615|
|quantized_private_states off|2.7 / 2.9|2.8 / 3.0|2.90 / move|3.528454635 / 6.371545365|2.823707471 / 7.076292529|1.158543769|
|quantized_private_states on|4.2 / 4.4|4.3 / 4.5|4.40 / move|3.598232689 / 6.301767311|2.830977016 / 7.069022984|1.041256615|

以competing-off为例，物理t=2.6的前保险杠y为3.2036887580/6.6963112420，读回分别是`upstream_0/2`；t=2.7变为3.3639698099/6.5360301901，两车均读回`upstream_1`。这个网络的中道中心y=4.95、宽3.3，横向边界为3.30和6.60。t=2.7时两质心仍在2.7308543857/7.1691456143，未到中道边界。末端t=2.8两车前保险杠x完全相同，均为268.71386286089637m；航向为±0.360106155524829rad。四米长车的前保险杠相对质心偏移，足以使原生车道归属早于模型质心归属变化。

全部末端的坐标/航向审计没有新增误差失败，原错误只有`SUMO collision or teleport reported`。`ExternalBridge.readback`取的是simulation层面的全局碰撞计数，再将相同非零计数附在每车报告中，因此两辆lead的`passed=false`不是它们参与碰撞的证据。运行仍按现有失败规则终止，没有修正SUMO读回或回写本车动作。[桥接源码](D:/yanjiu1/keyan1/variants/phase5_r5_completed/simulation/external_bridge.py:80)

## 可由代码和官方版本源支持的机制

1. **实际入口是phase4_bootstrap。** R5经`experiments.phase5`调用该入口。`experiments/phase3.py`虽有早期bootstrap，不能据此假定本包车型使用默认2.5m minGap。本包实际routes为`external_noa`、length=4、width=1.8、minGap=0.0；正式命令为SUMO1.27.1、step=0.1、collision.action=warn，未传`lateral-resolution`或`lanechange.duration`。其余三个桥接参数为speedMode=0、laneChangeMode=0、keepRoute=3。[实际初始化](D:/yanjiu1/keyan1/variants/phase5_r5_completed/experiments/phase4_bootstrap.py:20)

2. **二维姿态保留与车道归属同时存在。** 冻结桥将质心转换为前保险杠，调用`moveToXY('',-1,x,y,angle,keepRoute=3)`。官方说明该坐标对应前保险杠中心；bit1保留精确横向位置，bit0保留路线。版本源`Vehicle::moveToXY`在keepRoute分支调用`moveToXYMap_matchingRoutePosition`；`findCloserLane`按车道形状和宽度计算映射距离。这与本包3.30/6.60边界后的同车道读回一致。keepRoute=3没有启用sublane碰撞模型。[官方moveToXY说明](https://sumo.dlr.de/docs/TraCI/Change_Vehicle_State.html#move_to_xy_0xb4)、[v1_27_1 Vehicle.cpp](https://github.com/eclipse-sumo/sumo/blob/v1_27_1/src/libsumo/Vehicle.cpp)、[v1_27_1 Helper.cpp](https://github.com/eclipse-sumo/sumo/blob/v1_27_1/src/libsumo/Helper.cpp)

3. **SUMO默认检查的量不同。** 版本源默认lateral-resolution=-1、lanechange.duration=0，`gSublane=(duration>0 || resolution>0)`。`MSLane::detectCollisions`在非sublane路径比较同车道的纵向相邻车辆；`detectCollisionBetween`计算victimBack−colliderPos−minGapFactor×minGap，只有gSublane为真时才按横向间隙排除。这里minGap=0，等纵向前位置、length=4给出−4m，与六日志的gap=-4.00一致。该分支不是保存模型的带航向二维矩形SAT/扫掠，也不是路口shape overlap检查。本例远离路口、lane为upstream_1，不是junction stage。[v1_27_1 MSFrame.cpp](https://github.com/eclipse-sumo/sumo/blob/v1_27_1/src/microsim/MSFrame.cpp)、[v1_27_1 MSLane.cpp](https://github.com/eclipse-sumo/sumo/blob/v1_27_1/src/microsim/MSLane.cpp)

4. **时钟与stage须分开。** 本包bootstrap已保存两个排除的初始化步，native读回=物理末端+0.2s。官方版本源在`myStep`执行`move`碰撞检查，随后完成remote control，再把myStep增加DELTA_T。因此off的warning time=2.90是导致native读回3.00的那个原生步的起点，不能把它称为模型t=2.90的碰撞。本包失败物理区间实际为[2.7,2.8]。[v1_27_1 MSNet.cpp](https://github.com/eclipse-sumo/sumo/blob/v1_27_1/src/microsim/MSNet.cpp)

5. **同道后隔一步才报警，有明确源码候选机制。** 首次remote插入原本空的中道时，`incorporateVehicle→gotActive`把它放入changed-state集合；`MSEdgeControl::detectCollisions`遍历active lanes和单独登记的inactive检查集合，而`patchActiveLanes`在下一原生步events检查之后、move检查之前才把changed-state车道加入active列表。四车初态与首次同道前的保存读回均没有中道占用，故该路径与“首次同道无报警、下一move报警”完全相符。但本包没有保存SUMO内部active/inactive集合或阶段内状态，该一拍延迟仍标为源码支持的推断，而非已完成native断点复现。[v1_27_1 MSEdgeControl.cpp](https://github.com/eclipse-sumo/sumo/blob/v1_27_1/src/microsim/MSEdgeControl.cpp)、[v1_27_1 MSVehicle.cpp](https://github.com/eclipse-sumo/sumo/blob/v1_27_1/src/microsim/MSVehicle.cpp)

供逐行复核的本地版本源分别位于[tmp/phase5b_sumo_diagnosis_sources](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_sources/manifest.json)和[extra](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_sources_extra/manifest.json)。关键本地行：MSLane 1826、1999、2032；MSFrame 383、492、1183；Vehicle 1744、1788；Helper 1710、1757、1874；MSNet 867、880、938、961；MSVehicle 858、890、906、913、965；MSEdgeControl 118、340、358。这些文件来自官方`v1_27_1`标签，下载字节和URL已保存；标签ref对象也已留存。已安装发行目录未提供`src`目录，故源码级解释使用官方版本源；本次也保存了所用安装路径sumo.exe的哈希。版本字符串/文件哈希不等同于对其编译过程的独立验证。

## 仍未知处及最小原生重放设计（尚未执行）

现存记录能证明终点读回、事件计数和模型保存子步；它没有保存move阶段碰撞瞬间的native lane position/lateral position、车辆容器顺序或active-lane集合，也没有TraCI线级录制或SUMO状态存档。不能用事后末端读回替代全部阶段内原生姿态。源码能够解释触发结构和−4m数值，延迟路径需要以下新证据才能升级为直接复现。

后续最小对照应先登记为独立的桥接语义诊断，和R5本地规则变更分开，所有输出放新目录：

|对照|唯一变化/输入|预先要求的记录与判别|
|---|---|---|
|A 原载体记录重放|四车、原net/routes/binary/命令/排序/完整失败前缀；按已保存末态直接提交同序setSpeed与moveToXY，使用原初始化，不调用策略或积分器|保存逐次队列参数和原native时钟；每步记录车道、纵向位置、横向位置、实际pose、速度、collision IDs/事件、teleport；必须先复现原日志pair/lane/gap/stage和时间关系，否则停止解释对照|
|B 两车最小化|从A仅去除始终在外侧且远离的两辆lead，保留left/right完整保存命令和原选项|验证同道映射与−4m触发是否仍成立；不能把去除lead当作策略反事实，因为不再调用控制器|
|C 车道判定语义对照|在已复现的B上仅启用一个预登记的正lateral-resolution值，例如0.1m；其余姿态指令、step、minGap、warn全部相同|检验同车道且横向分离的保存前缀是否免于该纵向触发。改变SUMO语义的结果只用于解释该判定分支，不回填原包、不证明模型以外的真实安全，也不把此选项作为R5修复|
|D 保留真实重叠阳性控制|在同一独立两车夹具给出预先构造的二维车身重叠末态；分别用B/C的判定模式|两种模式都应保留相应碰撞事件；防止把不报警误读成所有检查被关闭|

A应先保留四车完整前缀，因为初始空道与车道激活历史可能影响stage；不能直接从失败末端开始后声称复现原时间。对于一拍延迟，优先在官方同版本debug构建记录首次中道插入前后的`myChangedStateLanes/myActiveLanes/myInactiveCheckCollisions`和events/move/remoteControl阶段，再核对A。若暂不构建，不需要借此修改生产桥或R5控制器，延迟解释继续保持推断级别。启用sublane仍不等于本模型带航向扫掠，应继续并列报告两种检查。

本轮只声明上述设计，不执行A–D，也不要求本地R5规则单元变更SUMO设置。R5到期仍同步尝试、对称/量化冲突的策略问题与这里的载体碰撞语义属于不同问题；原六项SUMO失败、未完成和全窗口null继续保留。

## 可复放诊断与日志

[提取脚本快照](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_evidence_20260913T0410/script_snapshot.py)SHA256为`d862b7d3d8f247003693899379aeec8e1953999b51831216dc54c4bbfae3ab0d`。参数`--output-dir`必须是全新的`D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_*`目录；不会覆盖已有尝试。冻结官方引用输入须仍在上述本地下载目录。

```powershell
& 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' scripts/run_logged.py --label phase5b_sumo_diagnosis_readonly_replay --timeout 300 -- 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe' -I -B -S 'D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_evidence_20260913T0410/script_snapshot.py' --output-dir 'D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_new_attempt'
```

本次summary SHA256为`06d81dbb795691625d816830168ad5863414ccea62c38285b2dbc8e6ec860d83`，尾帧JSON为`e3cdb4a73bec63044548f363e7227650a8768306213acc7ea38065145075fe2d`，其余输出由[产物清单](D:/yanjiu1/keyan1/tmp/phase5b_sumo_diagnosis_evidence_20260913T0410/output_manifest.json)绑定。以下`results/operations`均为本轮新建的外部限时命令日志，四项exit=0；它们只运行下载、提取、绑定脚本。

|日志目录|操作|elapsed s|
|---|---|---|
|20260913T040240727239Z_phase5b_sumo_diagnosis_official_sources_11ca910b|六个指定官方源文件|10.735|
|20260913T040503541543Z_phase5b_sumo_diagnosis_stage_sources_1e50c93f|车道激活/跟车参数指定源与标签ref|6.765|
|20260913T040906337953Z_phase5b_sumo_diagnosis_extract_159a08b3|六前缀姿态提取与保存子步几何复核|1.234|
|20260913T041049023672Z_phase5b_sumo_diagnosis_verify_830a5581|88输入不变、57原包绑定及5产物哈希核验|0.172|

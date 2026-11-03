# C10：接收与接入使用同一实际形成提案

候选`20261104_forward_gap_C10_200/300/native_rules.py`，位于`tmp/staggered_bottleneck/candidates/`，各319行。独立从C9替换预接收关系，并删除道1选择的拥挤代理门。

## 同一提案

known情况下，道0车对严格前方道1 peer预接收时，必须实际看见peer的同道前车F1，以及peer在道0的前车P0，且P0−peer至少为D_entry(peer.speed)。随后用本车可见快照、只移除本车receiver，调用原`_vacancy(peer, snapshot_without_receiver, 0)`：同一个P0−D目标必须通过原半D误差进步及其他实车约束。最后仍验证peer当前/1 s原8 m走廊。

这样只在receiver自身是后侧D空间缺口时开隙；没有F1的自由头车、没有P0、或不能提出合法形成slot的peer不再被长期虚拟预留。删除C9的无前车空段回退，不增加新的无前车例外。未知路仍只接收已经实际向0横移的peer；实际运动接收及原物理安全检查保持。

源端道1在transform已触发后，直接检查同一个真实`_vacancy`提案，删除`crowded`的距离/速度代理门。有合法slot就可准备，在实际走廊安全后横移；不再出现receiver为几何可接入车留隙、源车却仅因不拥挤而永不采用提案的分歧。

C8单向动作、最多两次实际横移的道序解释、相位、entry尺度及低速远孔修复均不改；不读peer意图/pending/记忆，没有新flag、计时或人数。

## 行为红绿

`stage/test_forward_C10.py`新增3组，复用11组仍适用的前版行为，共14组。

- 自由头部无F1、无P0、或几何提案不合法：不预留；已经实际横移的peer仍可接收。
- 前侧32 m已有、后侧仅receiver不足：先跟peer打开后侧；后侧达到D后，peer采用同一个P0−D slot。后侧3.5 m仍拒绝。
- 源车不满足旧crowded代理但实际提案合法：先纵向准备，预测走廊满足后执行。

冻结C9先有4个失败记录；C10两候选各14组通过。只有`_queue_front`、`_decide`改变，`_vacancy`本身未改；200/300只差ROAD_PREVIEW。旧C9无F1/无P0预接收正例按本次规格替换，没有为其保留回退。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C10.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C10_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C10.py -v
```

未运行仿真。完整交错、自由头部相位及交通代价由root复验；冻结后不修改同名源。

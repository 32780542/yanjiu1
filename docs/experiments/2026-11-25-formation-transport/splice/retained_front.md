# 单车保留已有跟驰参考和未完成横移

在群权候选 `ffd33854` 上，只有单车原命令同时满足 `command.reference is None` 和 `command.lane is None` 时才采用可见锚点。该修正保留已有的物理纵向目标和正在执行的横向动作。两源码根的唯一差异为 `noa/native_rules.py` 的一个条件。修正版本的该文件 SHA-256 为 `2337ae74b26352e0e3cc98deb29471935bf6c93b34a9139628196ce3cc61f917`。

本车位置 100 m、车速 20 m/s 时，已保留的同道真实前车由另一辆 180 m 处的同速车接替。其原跟驰目标为 157.5 m，原速度命令为 23.45 m/s。旧群权把目标和速度改成了 128.75 m 与 20.5 m/s；修正候选在 formation/transform 两种模式均恢复原值。另一微例中，单车已向车道 1 横移，纵向参考为空，可见远处另车。修正候选完整保留原执行命令，速度为 28.8 m/s。无跟驰参考且无横移的单车仍会追赶可见的前车群。

2.8 km 上游的独立 24 个稀疏初态，修正候选与旧群权在全程 0.1 s 采样的物理轨迹全部相同。两端整队为 20/24，下游为 24/24，20 个整队样本变换均取理论跨道总数及单车最大值下界，累计 180/180 次。两道初始的四个配平失败仍在。2.8 km、260 m 同速盲区对照中，基线、旧群权、修正候选全轨迹完全一致，上游空档保持 260 m，两端可配对的最大组为 12 辆。

紧凑的 24 个初态分别在 1.6 和 2.8 km 对照。两种长度均为两端整队 22/24、下游整队 24/24，两次失败同为 2→3 的 24 车种子 8722、8723。48 组逐帧轨迹均与旧群权及未加锚点的基线相同。合计包括上述工况与演示的 [81 个配对](retained_pairs.csv)，修正候选与旧群权的全轨迹每组均相同，全部车辆正常驶毕，零碰撞、零传送，最高实测速度 33.3 m/s。CSV 的 `*_same_full_trace` 在此表专指与旧群权比较。单车语义修复的直接证据来自前述微例，批量跑车验证其在这些固定车组上保留原有表现。

短演示按原 0.7 s 发车表，逐 ID 核对实际首次出现的时间、位置、速度与加速度。长演示沿用 GUI 的 24 辆车在 20–526 m 同时发车。两候选的全部八个演示均追踪出相同物理轨迹，并在两端形成全部相同车辆的交错构型。

| 路网 | 短 12 辆上/下游保持 (s) | 长 24 辆上/下游保持 (s) | 变换实际/下界，短、长 |
|---|---:|---:|---:|
| 3→2 | 33.3 / 28.9 | 41.4 / 20.2 | 6/6，12/12 |
| 4→3 | 35.3 / 31.0 | 37.4 / 26.8 | 6/6，12/12 |
| 2→3 | 34.6 / 28.1 | 44.0 / 14.1 | 6/6，12/12 |
| 3→4 | 33.3 / 31.0 | 41.4 / 26.9 | 6/6，12/12 |

沿用 8721–8723 的同一组种子，`probe.py --models retained_front` 从 `e186b8a` 重新构建修正候选。源码加载路径、实际路网和首帧由每一仿真子进程核对。产生群权与修正版本的完整新对照可执行以下命令，使用尚未存在的输出目录。

```powershell
$spliceProbe = 'docs/experiments/2026-11-25-formation-transport/splice/probe.py'
python $spliceProbe --out tmp/verify-retained-random --models base group retained_front --profiles long compact --seeds 8721 8722 8723 --lengths 2800
python $spliceProbe --out tmp/verify-retained-compact --models base group retained_front --profiles compact --seeds 8721 8722 8723 --lengths 1600
python $spliceProbe --out tmp/verify-retained-blind --models group retained_front --roads 3to2 --profiles split260 --counts 24 --lengths 2800
python $spliceProbe --out tmp/verify-retained-short --models group retained_front --profiles demo12 --seeds 20 --counts 12 --lengths 1600
python $spliceProbe --out tmp/verify-retained-chain --models group retained_front --profiles chain24 --seeds 20 --counts 24 --lengths 2800
```

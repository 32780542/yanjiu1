# 事后时距敏感性与NOA远前车补充基线

**记录位置：** 本页保留源冻结与纯规则验证；后续真实试验已完成，见[时距结果](../posthoc_headway_summary.md)与[扩展NOA结果](../posthoc_NOAfront200_summary.md)。

以下六源从已锁定的C12各自独立派生，均为316行。它们用于事后参数／机制检验，不用于重新选择主方法或主参数，也不替换正式核心协议中的C12与主NOA。此处只做纯规则验证，没有运行SUMO。

## 精确改动

**时距敏感性：** `sensitivity_h075`仅把`HEADWAY = .85`改为`.75`；`sensitivity_h100`仅改为`1.00`。每个文件中的NOA与transform共用同一个h。D(v)、跨道半D及接入尺度中依赖D的部分自然随h变化，其他增益、换道规则、信息范围和物理参数均保持父本。巡航28.8 m/s时，D分别为27.10 m和34.30 m。

**补充NOA：** `NOA_front200`仅把`_reactive`首个跟驰调用从`_front_following(ego, rows)`改为`_front_following(ego, rows, distance=200.)`。文件名末尾的200／300表示道路预警范围，NOA跟驰车辆范围在两者中均为200 m。NOA的当前gap合流、主动超车、道路知识、物理约束和默认状态0均保持原样。没有启用跨道phase、虚拟接收或slot，也不保存前驱链；它每步直接选择当前实际前车。此文件的formation／transform路径完全不变。

该补充基线使尚无前驱记忆的NOA也能追赶80 m等远处真实前车，用于检查主方法收益中有多少来自远前车追赶。它与主C12不同：C12普通纵向链须先近距建立，再于200 m内保持；NOA补充基线在200 m内直接建立当步跟驰。

## 冻结源

共同目录：`D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates/`。以下目录内均为`native_rules.py`，冻结后不覆盖。

| 候选目录 | SHA256 |
|---|---|
| `20261104_sensitivity_h075_200` | `94a8e128b05e4db75342143a6c13f7f8a6848d07ec4c9ead5bed72dc8404c748` |
| `20261104_sensitivity_h075_300` | `a2b51fb0e6c9c7ae48b9536c5c0595c97c86c8d63ade5cdd4e04126050e8b6f5` |
| `20261104_sensitivity_h100_200` | `9e46dc061173a0a8d5f7f6ae7649acaf3d5a32c7f9fd9ab6aa12a8b93a392831` |
| `20261104_sensitivity_h100_300` | `e9613649a6a0d54f663ee1513865bcb72893f7b284972f6f4e545807d53dc937` |
| `20261104_NOA_front200_200` | `f1d6fcc037cd6c76b4aeaec5aac71d6eeb4a18341cf3fc243aa28659f7c51de7` |
| `20261104_NOA_front200_300` | `25ec21255e70e79459191f25dde2f73cd7066e62862197166d32ef9c11e14db5` |

## 纯规则断言

[test_posthoc_controls.py](test_posthoc_controls.py)共5项测试，覆盖两种道路预警范围：

1. h=.75、h=1.00分别给出正确巡航D，并在无跨道关系的同一真实前车快照中，让NOA与transform使用相同纵向目标及速度请求。
2. NOA补充基线在fresh 80 m真实前车场景中选到该前车并主动追赶，状态仍为0、前驱记忆仍为空。
3. 只有相邻道相位伙伴、可虚拟接收ending、存在真实slot三类快照均不会在NOA中启用相位／虚拟／slot横移。
4. 逐字核对全部六源与父本的唯一指定改动；对普通远前车、接收ending和本车pending三个快照，核对补充基线文件的transform完整Command及Memory与主C12一致。

前三个改动行为先在原C12上得到预期失败，再在新源上通过；完整5项已通过。复核命令：

```powershell
python docs/experiments/2026-11-04-timegap-staggered/stage/test_posthoc_controls.py
```

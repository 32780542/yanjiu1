# 共同请求上限28.8 m/s的速度机制检验

**记录位置：** 本页保留共同上限源的冻结与检验口径；36条真实试验已完成，见[实际结果](../posthoc_speedcap288_summary.md)。

从最终C12的200／300 m版本各自派生一个候选，只把第5行

```python
CRUISE, MAX_SPEED = 28.8, 33.3
```

改为

```python
CRUISE, MAX_SPEED = 28.8, 28.8
```

NOA与transform都使用同一候选文件，巡航速度仍为28.8 m/s，h仍为.85 s。这个常量限制共同速度请求，也进入共用`safe_speed`的初始上界；跟驰、phase、换道、入口和停止距离公式均未改。`native_sumo.py`没有修改，SUMO物理`maxSpeed`仍为33.3 m/s，不能把本检验描述为改了SUMO物理最高速度。

本检验回答：当两种方法的请求都不能超过巡航速度时，C12是否仍能减少瓶颈延误。正式结果中较短的旅行时间可能部分来自接入／追赶阶段超过巡航的速度预算，统一请求上限可以检查这部分机制。结果尚未运行，不预设收益保留或消失；正式主版本继续使用33.3 m/s上限，不据此重新选择主结果。

## 冻结源

两份均为316行，与对应最终C12的字节差集严格只有上述常量。

| 文件 | SHA256 |
|---|---|
| [speedcap288_200](D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates/20261104_speedcap288_200/native_rules.py) | `6cc79e4ab72040f8fd1e334b202cd9053aa4ce5652cf9a3025906f244b2a85b0` |
| [speedcap288_300](D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates/20261104_speedcap288_300/native_rules.py) | `3d6c2012a5a2764a564b6d40b22c762e8904877819aca3da7b22dc2b41dff947` |

## 纯规则验证与运行范围

[test_speedcap_mechanism.py](test_speedcap_mechanism.py)先在C12父本的远位置请求上得到预期失败：其`_request`可输出33.3 m/s。新源的同一请求通过28.8 m/s上限断言；两种preview、三种mode、三档本车速度与三种邻车快照共54个完整Command全部≤28.8，NOA状态全部为0。测试同时确认源码唯一常量差，已通过；没有运行SUMO。

```powershell
python docs/experiments/2026-11-04-timegap-staggered/stage/test_speedcap_mechanism.py
```

root／runner计划运行36例事后机制补充：201／202两seed、1500／1750／2000三档流量、NOA／transform、需求600 s、出口1200 m；两种信息情景的缩道共24例，另加200 m情景直路12例。该安排与正式确认结果分开，不用于调参挑主结果。此文仅交付冻结源与纯规则验证，结果由后续实际运行记录。

# C7：修正远孔相位合成的自由巡航基准

候选`20261104_forward_gap_C7_200/300/native_rules.py`，位于`tmp/staggered_bottleneck/candidates/`，各320行。仅从C6替换远孔合成中的一个表达式，不改变模式、几何、换道、NOA或物理安全规则。

## 实际错误

没有50 m内真实前车时，`local[0]`直接返回CRUISE=28.8，而`formed[0]`已经经过`_request`，包含本车速度与0.2松弛。两者直接相减并不是纯相位：本车静止且无相位误差时，formed约5.76，旧差值却为−23.04。

既有C6轨迹t40的`formed_l1_r03`正是这种控制器假停滞：x900.951、v0，200 m前车反馈15.65475，formed6.04094，旧式结果−7.10431被截成0，物理safe cap仍为33.3。这不是物理不可行或需要新增形成门。

C7在同一“50 m无前车、200 m有前车”分支改为

\[
v_{cmd}=v_{physical,200}+
\bigl(v_{formed}-\operatorname{request}(ego,x_{ego},CRUISE)\bigr),
\]

再保留原输出范围和安全包装。自由巡航基准也经过同一个`_request`松弛，所以只提取相位增量。

## 红绿行为

`stage/test_forward_C7.py`在v=0/10/28.8及正负相位下调用实际`decide`：

- 冻结C6：v0两符号均误停0；v10只请求2.53/2.83，而正确为17.57/17.87；巡航两符号正常。
- C7：六个子例均按200 m真实前车反馈加纯相位增量，且继续向远孔前车推进。

两项新测试复用C6六组，共8组，两候选均通过；精确文本比较确认仅该基准表达式改变，200/300仅ROAD_PREVIEW不同。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C7.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C7_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C7.py -v
```

本子任务未运行仿真。旧源与旧失败保留，C7冻结后由root重跑实测，不再为远孔停滞增加门槛。

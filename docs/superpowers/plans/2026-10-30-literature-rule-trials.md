# 文献建议独立试验实施计划

**目标：**分别验证固定时距、补位制动代价和合流参考恢复，采用有实际帮助的简洁改动，并以用户GitHub仓库管理版本。

**依据：**`docs/research/2026-10-30-literature-review/文献结论与方法建议.md`已由用户授权执行，具体工况见`docs/experiments/2026-10-30-rule-trials/protocol.md`。在用户指定主目录工作；候选试算源放在ignored `tmp/literature_trials`，不另存仓库副本。

## 1. 登记与基线

- 保存协议、计划及检查点，创建线上研究分支。
- 核对`native_rules.py`、`native_sumo.py`和CLI基线SHA；只运行受影响的规则/执行测试，不重做旧P100。
- 试验脚本放在`docs/experiments/2026-10-30-rule-trials`，参数、源码身份和每次失败都留记录。

## 2. T：固定时距

先写`T/test_time_headway.py`，载入指定规则文件，测试以下行为：

```python
spacing = 4 + 1.5 + (30 - 4 - 1.5) / 28.8 * speed
# 同速、上述间距时应保持该速度；原固定30米在低速反例上失败。
assert requested_speed == speed
# 同一实际前车下，NOA与编队的基础跟驰相同，NOA状态仍为0。
assert noa.speed == formation.speed
assert noa.formation_state == 0
```

记录预期失败后，提取共用真实前车跟驰，距离用`LENGTH+STANDSTILL+HEADWAY*ego.speed`；跨道队首仅供编队。通用`_request`不变。候选先写到`tmp/literature_trials/T/native_rules.py`，通过测试后保存差异并提交线上候选分支。

## 3. M：补位制动代价

独立完成`M/rules.patch`和行为测试。测试安全几何相同但后车高速接近时，候选成本高于同速可补位；形成收益仍可接受等速换道；必要合流及NOA不变。只在`_fill`及小型公开跟驰预测函数内实现，不改其他动作。父端复核再跑实际车流。

## 4. R：参考恢复

独立完成`R/rules.patch`和行为测试。测试真实横移完成后组织参考连续过渡、逐步恢复原目标、参考丢失后正确重置，安全速度仍按当帧前车计算。复用本车记忆和横移完成，不读他车状态；保持NOA不变。

## 5. 实际SUMO试验

用一个小型运行脚本从Git/候选冻结六个必要源文件及工具配置，执行现有`native_sumo.run_case`，每工况独立目录。批次manifest记录`candidate,stage,flow,seed,scenario,mode,run_dir`，不修改既有记录器或请求生成方式。

车串试验在SUMO中使用相同领车速度输入和同一初始位置，禁止换道；同参数先比较base/T的实际速度。随机筛查按protocol固定48工况执行。无错误则不重复跑相同工况。

## 6. 分析与组合

分析脚本独立核对源文件摘要、共同参数、请求和0/1累计，输出case与paired CSV/JSON，失败不删。机制、交通及关系保持共同支持的项才组合；不把新NOA的纵向收益归给编队。组合完成后用新种子11–15按协议验证，不根据结果再选择种子。

## 7. 最终采用和交接

把有效改动写回`variants/phase5g_pure_formation/noa/native_rules.py`，删除试验开关及无用分支。运行受影响规则、原生执行、直接状态统计和根GUI入口测试，以及`python -B runrun.py --check`。新增必要测试进入正式tests，实验数据留在docs目录。

更新README、现行规则说明、本轮对照报告及`docs/phase5_checkpoint.md`，保存所有候选的结论。独立核验公开压缩数据及Git索引字节，再推送用户远端`yanjiu1/main`并核对远端SHA。输出明确的采用项、未采用项、实测效果和适用范围。

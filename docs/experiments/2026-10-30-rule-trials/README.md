# 文献规则的独立试验

本轮从Git基线`8ed11d9`分别研究单前车固定时距T、自由补位制动代价M、合流参考恢复R；再检查第二前车T2和组合TM/TR。80例筛查与8次纵向车串运行已完成，TM进入五流量、新种子11–15的250例独立验证。当前生产规则为TM，SHA256`65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317`。

## 阅读入口

- [试验协议](protocol.md)和[独立验证协议](heldout_protocol.md)：问题、工况、对照及选择顺序。
- [T](T/method.md)、[M](M/method.md)、[R](R/method.md)、[T2](T2/method.md)、[TM](TM/method.md)、[TR](TR/method.md)：逐项方法、补丁和行为测试。
- [筛查分析](analysis/review_screen48.md)：收益、代价及跟驰/组织作用的区分。
- [车串实测图](figures/string_response.png)、[SVG](figures/string_response.svg)及[原绘图数值](figures/string_values.csv)。图中T与生产TM使用相同纵向跟驰。
- [紧凑离线证据](evidence/README.md)：原输入、结果、车辆记录、源码、逐帧0/1和越线样本及独立复核工具。

参与率和连续1时长直接来自本车输出，不加入完整层识别；人数指全路参与总数。原版、新NOA、单独时距编队和最终组合分别列出，跟驰的改善与补位的增量分别比较。

## 重建候选

```powershell
python -I -B -S docs/experiments/2026-10-30-rule-trials/prepare_candidates.py
```

输出到`tmp/literature_trials/reproduce/<UTC时间戳>`，给出六个标识的完整源码路径和SHA256。T/M/R取固定Git基线后应用补丁，T2/TM/TR取重建T后应用补丁；各候选只有一份小型规则文件，不复制工作区，也不改索引、分支或生产源码。需要包含基线提交的Git克隆。一次逐字节验证见[重建记录](prepare_candidates_verification.json)。

重跑时将输出的源码路径传给`run_trials.py --candidate NAME=路径`。例如base与TM的两道路对照：

```powershell
python -B docs/experiments/2026-10-30-rule-trials/run_trials.py --candidate base TM=重建目录/TM/noa/native_rules.py --all-modes --stage replicate --flows 500 750 1000 1250 1500 --seeds 11 12 13 14 15 --duration 600 --max-time 900 --jobs 4
```

每次创建独立批次，运行器保存实际六份源码、请求和物理参数。`analysis/analyze_trials.py`核对原件并生成逐工况、配对及越线表；`summarize_trials.py`汇总正式250例的五种策略。完整数据口径、归因和最终采用结论将随独立验证结果更新。

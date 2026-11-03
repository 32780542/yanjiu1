# C10b：无主前驱时保护旧fallback分支

候选`20261104_forward_gap_C10b_200/300/native_rules.py`，位于`tmp/staggered_bottleneck/candidates/`，各319行。C10原件保留，仅在`useful`末分支访问`front.lane`前增加`front is not None`。

删除crowded代理后，本车可能没有真实/虚拟主前驱，但公共相位形成仍给出非空target，相邻道也存在真实slot。若slot没有超过该target，旧末分支会解引用None。本轮C10连续流11/12因此实现异常；这些不是交通效果反例，修复后须以原12例重跑。

新增实际行为：本车1道x900、相邻道0前车x920/后车x840，无同道或虚拟前驱；真实slot存在而相位target非空。冻结C10实测在278行抛`AttributeError: None.lane`，C10b保持原相位形成、不发起不符合前移条件的换道。虚拟ending前驱确实存在时，原末分支行为不变。

`stage/test_forward_C10b.py`新增此例，复用C10的14组，总计15组，两候选均通过。精确文本比较确认只增加该None保护；200/300仅ROAD_PREVIEW不同。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C10b.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C10b_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C10b.py -v
```

本子任务未运行仿真，冻结后不修改同名源。

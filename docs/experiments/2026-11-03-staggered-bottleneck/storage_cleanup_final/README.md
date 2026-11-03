# 最终本地存储清理：仅本轮八个成功2250案例

本单元在研究结束后按父明确授权执行，只清理`20261103_long1800_L4/M4/N4/Q4`中drained、safe、sealed的2250每道流量、seed41/42案例。没有新仿真、Git或source修改。实际清理8例、16个positions/events文件，释放477,616,342字节（455.490MiB）。未满足严格条件者原样保留，跳过0例。

| 方法 | 流量 | seed | 清理文件 | 释放字节 |
|---|---:|---:|---:|---:|
| L | 2250 | 41 | 2 | 55,254,315 |
| L | 2250 | 42 | 2 | 62,765,747 |
| M | 2250 | 41 | 2 | 56,564,110 |
| M | 2250 | 42 | 2 | 57,363,068 |
| N | 2250 | 41 | 2 | 61,821,208 |
| N | 2250 | 42 | 2 | 71,693,186 |
| Q | 2250 | 41 | 2 | 54,287,242 |
| Q | 2250 | 42 | 2 | 57,867,466 |

前提逐项核验：iteration3对应四个完整原计划包仍在本地，包SHA与PUBLIC_MANIFEST及原verification一致；已有原字节比较=true、隔离验证无原仓库读取、无original paths依赖，两成功/两timeout的原四例矩阵均保留。父确认包已发布于研究树`06081e2`，本单元没有运行Git去改变或重复发布。

每个清理案例先用既有`seal_case.verify(check_originals=True)`验证紧凑原件及全部ledger；两个raw同时匹配原seal及iteration3索引的字节/SHA。随后直接调用原`prune_raw`，核验batch ownership marker、解析绝对路径位于指定batch/cases/run、原SHA且非symlink；只unlink已列出的positions.jsonl.gz和events.jsonl.gz，不递归删除。清理后离线封存验证仍通过。

八个2500 timeout案例的16个raw共813,903,124字节，操作前后逐文件存在/字节/SHA完全一致；没有解析、改写或补造partial raw。选定2250 seed42 NoA/S双源的4个完整positions/events也逐文件前后哈希一致。较早阶段原件未列为删除目标。

iteration3的72项manifest绑定文件（56包/索引/说明文件、8相关报告、8工具）以及PUBLIC_MANIFEST自身，操作前后SHA全部一致；四批原protocol/manifest也一致。旧README及unfinalized_and_raw_index仍描述当时32 raw/1,291,519,466字节的封存快照，刻意不回写历史。当前状态以本补记及JSON为准。

[完整前置条件、包与原始文件索引](preflight.json)、[逐例精确前后/释放量/失败raw复核](cleanup_result.json)、[执行工具](cleanup.py)。原证据：[iteration3完整矩阵](../evidence_iteration3/README.md)、[旧只读索引](../evidence_iteration3/unfinalized_and_raw_index.json)。主报告引用由root另行补入，本单元不改旧报告。

执行操作`20261103T091236808868Z_final-storage-long1800-success-only_2781531b`返回0，耗时48.485秒。[独立只读复核](independent_verification.json)另行重核16个授权成功raw确实不存在、16个失败raw和4个指定NoA/S raw仍在且SHA相同、72项manifest绑定文件及四个完整包不变；[独立复核工具](verify_cleanup.py)不导入seal/prune方法。

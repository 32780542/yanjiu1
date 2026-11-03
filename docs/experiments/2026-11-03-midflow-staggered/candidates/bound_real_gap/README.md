# GP：绑定真实gap的原始候选，源已冻结

源码：`tmp/staggered_bottleneck/candidates/midflow_bound_real_gap/native_rules.py`，514行，SHA256 `3e2a722f997713e6ad504bce22d741c39d58b1ad6808765a5b9b8d62a68a1007`。

从冻结Git S构建，仅增加可见真实pair规划/守卫并接入目的lane1执行。见[构建前设计](design.md)、[构建脚本](build.py)、[差异](native_rules.patch)、[来源](source.json)。8项合同通过：`results/operations/20261103T112757034045Z_midflow-GP-green-fixed_8cc92899`。

初稿曾在没有名义CTH资源时改变已启动横移的原S分支，红灯后修正；初稿patch单独保留为`initial_native_rules.patch`，失败日志`results/operations/20261103T112637650487Z_midflow-GP-active-fallback-red_524d2d26`。未运行交通仿真；交给父任务的runner独立试验不由本构建任务执行。

本版只检查新横移进入同pair且原8m可用，没有要求当前CTH兼容；固定最大剩余时域与道路界还会排除需要正相对位移的gap。[GP2修订](../bound_real_gap_v2/README.md)在独立源中处理这些问题，原GP不再改动。

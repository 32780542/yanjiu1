# LT：L加对称时距相位，独立于PD和N

固定父L `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`。新源SHA `8a773793ccba5eb5e0ecae7f1b02083a8571d7e77f5a1f5f5f78b13eb6596593`，460行，仅_pair_error增加一行：

```text
scale = (5.5 + HEADWAY*(v_ego+v_peer)/2) / GAP
e = peer.x - ego.x + (physical_phase(peer,3)-physical_phase(ego,3))*scale
```

实现先计算scale再乘已有phase，使巡航scale精确1；不增加速度判断分支。数学上是先前JT2的同一对称时距公式，保留共同pair_lanes归一化与物理邻接；此处父L还含实际witness孔修复和fast计算。见[build](build.py)、[patch](native_rules.patch)、[身份](source.json)，AST只_pair_error变化，反向精确恢复L。

## 几何与范围

共同速度v下，真实CTH同道目标D(v)=5.5+HEADWAY*v；相邻中心物理相位差±15乘D(v)/30，得到跨道±D(v)/2。因而有实际front的body在同道D(v)、跨道D(v)/2时两部分误差都为0。平均速度对称，交换ego/peer误差反对称。

这里只建立低速body平衡，不让自由head固定低速：head仍按原_request回CRUISE，10m/s无相位误差时输出13.76。没有移植文献图/V2V收敛证明；异速闭环、完整群形成及交通收益需实际验收。

_fill仍巡航30/15模板，L witness仍用原物理相位和front−GAP、2m证明，CTH目标仍D(v_ego)。安全、Memory、NOA默认50m及所有执行优先级未改；不叠PD/N/S。

## 先红后绿

[六项合同](../../tests/test_local_time_scaled_phase.py)覆盖低速两/三道全部body的D(v)/D(v)/2平衡、低速head仍回巡航、不同速度均值相位/双向反对称、重标/远车、本车L witness仍使用巡航证明，以及300已存局部state完整NoA/Memory hex exact。将这300组速度统一CRUISE后，再对三模式共900完整Command/Memory与L逐位一致。

- L红：`20261103T071238158810Z_LT-symmetric-headway-phase-red_c5ed49eb`，exit1，11个失败主/子断言。
- 构建：`20261103T071320096599Z_LT-symmetric-headway-phase-build_69261579`，exit0。
- LT绿：`20261103T071341464068Z_LT-symmetric-headway-phase-green_8f02e0d9`，exit0，6项/15子测试通过，15:14前交父源。

原225+J2 patch的四个旧固定15m公式冲突已经另做[最小LT迁移](../../implementation/LT_test_migration.md)，225项/37子测试全过。未改原tests或生产，没有运行交通或Git；父统一短筛/长路几何和600秒验证。

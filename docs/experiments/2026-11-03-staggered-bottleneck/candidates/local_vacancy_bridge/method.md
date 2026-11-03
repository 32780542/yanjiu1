# L：相邻道实车证明的单格空位桥接

父代理批准设计，基于固定J2fast `03ce8f468bdce13b9db82b7122eeeeb3d688128f3c3c5bb9dd34ab62df28c6a6`，不叠加K、不改已有源或生产，暂不跑交通。

规则只在正常50m范围内没有实际front时，寻找60m内最近实际占道front。必须另有实际相邻道实车witness处于ego与front之间，其投影 `witness.x+physical_phase(witness,3)−physical_phase(ego,3)` 距 `front.x−GAP` 不超过原层容差2m，才把这个真实front交给既有CTH。此后相位耦合、硬安全及执行优先级完全照旧。NOA/cf_speed仍默认50m，目标公式不复制。

设计审查：目标处若已有同道车，原50m跟驰会先选它，L不会触发；60m内也只能用最近front，不能跳过它去匹配更远witness。无相邻实车、只有同道计数、错位、非相邻道、front>60均不能证明缺格。局部几何不能识别“同群成员”，因此L只定义为单巡航空格修复，不声称知道群号或成员归属。证明用巡航30m，真实CTH目标仍随本车速度缩放，不能把几何证据混成固定跟驰距离。

- [x] 专项合同在固定J2fast上先出现预期失败。
- [x] 最小独立build只改_front_following可选范围和_following的条件fallback。
- [x] 新源专项绿；NOA/CF/safety、重标/远车、近front优先保留，记录hash和原件不变。

## 具体公式与局部边界

令原50m跟驰结果为F50。若F50已有实际front，直接保持，不运行L。否则用同一_front_following函数、可选distance=2*GAP取得F60；只有F60的最近真实front f存在，且某个当前实测w满足

```text
abs(w.lane - ego.lane) == 1
ego.x < w.x < f.x
abs(w.x + phi(w,3) - phi(ego,3) - (f.x - GAP)) <= 2.0
```

才把following置为F60。phi为原_physical_phase；所有后续互选相位/target/reference/CTH/安全和横移优先级原样继续。f仍由原几何排序选最近实际占道车，不复制目标公式，也不从w推造虚拟front。

这里f只读60m内已经被本地观测到的实车；w的相位差在[−15,+15]，且f−ego在(50,60]，由上述误差界可得w−ego在(3,47]m，因此几何witness本身也处于原50m邻域内。控制不读取全局车辆、层号、车群大小、成员标记或邻车意图；track仅把F60返回的实际reference关联回当前实车，不排序。

前车>60m，即使w看起来对齐也不能追；60m内若最近front不被证明，不能跳到更远front。它可能把当前局部几何相连的车辆耦合起来，无法凭这些观测判定其先前是否属于不同群，故不能宣称得到全局完整群证明。

## 已知实际缺格及合同的几何推导

父诊断的t52.8三车位置，取三位小数后为ego lane1 x1674.374、front lane1 x1733.167、witness lane0 x1718.228。真实同道gap约58.793m超过原50m；w投影到ego车道为1703.228m，front−30为1703.167m，只差.061m，明确证明一个巡航目标空格。本专项是该三车简化回归，不声称重放了原完整帧。

简洁ego100 lane1/front160 lane1/witness145 lane0也满足证明，L绑定真实front160，巡航CTH目标130。**这一例没有额外互选相位速度**：w对ego/front的绝对相位误差均30，但到front实际距离15m、到ego45m，原第二键使w选择front而非ego。因此ego速度是原_request的30.6m/s，不是31；L并未修改互选图来制造额外+.4。

首次合同错误地假定这里仍有+.4，在新源上出现1项失败；调查上述几何后只修正该测试的错误预期，源始终未变。修正合同重新在J2fast上失败、在L上通过，失败日志完整保留。这不构成L对所有速度/负荷更快的保证：低速时真实CTH仍按D(v)取目标，witness证明保持巡航GAP，性能须独立验收。

## 冻结身份与验证

新 `tmp/staggered_bottleneck/candidates/local_vacancy_bridge/native_rules.py`，SHA `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`，459行/有效+9。只改变_front_following的可选distance和_following的条件fallback；[build.py](build.py)证明AST仅这两函数变、反向精确恢复固定J2fast。见[native_rules.patch](native_rules.patch)和[source.json](source.json)。NoA与cf_speed的_front_following调用不传distance，继续原50m；停止位置和所有安全常数均未改。

[专项14项](../../tests/test_local_vacancy_bridge.py)覆盖：60m/实际58m绑定、容差内外、没有witness/同道数量/非相邻lane不触发、>60不追、原≤50优先、最近扩展front不被远front跳过、低速D(v)目标、ID重标/倒序/远车、原硬安全仍覆盖，以及600个已存有效局部state的完整NoA Command/Memory与cf_speed/safe_speed精确等价。另与原12耦合+4物理邻接合同联合，**30项、106子测试通过**。

- 初始红：`20261103T054747755793Z_L-local-vacancy-bridge-red_f9c258e9`，exit1；5个主测试与2个子断言预期失败。
- 构建：`20261103T054903069487Z_L-local-vacancy-bridge-build_1a6fc6f9`，exit0。
- 初次联合绿尝试：`20261103T054924290308Z_L-vacancy-and-inherited-phase-contracts-green_c91d76d5`，exit1；29通过、106子测试通过，唯一失败为上述错误+.4预期；源未改。
- 几何修正后重新红：`20261103T055042332203Z_L-local-vacancy-corrected-contract-red_7c9a5341`，exit1；相同5主项与2子断言在J2fast失败。
- 最终联合绿：`20261103T055058724110Z_L-vacancy-and-phase-corrected-contract-green_46b73541`，exit0，30项及106子测试通过。

没有跑交通、安装生产或Git提交。原J2fast、J2、E和生产源保持原hash；不会把K结果或J2fast正式批写成L验证。下一入口是父独立L筛查，之后再决定是否需要正式225项迁移。

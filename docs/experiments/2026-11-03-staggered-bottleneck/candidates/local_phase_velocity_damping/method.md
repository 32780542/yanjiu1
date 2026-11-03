# M：实际互选边的相对速度阻尼

固定父L `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`，不叠NoA60或N。每条既有实际跨道互选边把原 `difference/n` 改为 `(difference+(peer.speed−ego.speed)/POSITION_GAIN)/n`，后续POSITION_GAIN、±2限幅及.2响应全部保持。相当于 `u_phase=sum(.3*e+v_peer−v_ego)/n`。

这是自行推导的局部PD项，使用当前可见相对速度；不继承文献图收敛或V2V证明。原相位误差交换反对称、共同n相同，相对速度也交换反对称，因此未限幅边项反对称。同速原平衡不变；不同节点的clip、自由head巡航回归与实际front CTH仍不构成整组零和。

不改邻接、真实前车、L witness、模板、gain、CTH、安全、横移、Memory或NoA。先专项红绿，再原样运行L30合同，逐项报告新速度规则与旧断言的实质差异，不修改旧tests来抹平。

新源 `tmp/staggered_bottleneck/candidates/local_phase_velocity_damping/native_rules.py`，SHA `a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762`，459行。只替换_following既有error累加的一式，[build](build.py)验证AST仅_following变化、反向精确恢复L；见[patch](native_rules.patch)和[身份](source.json)。

## 合同与原L30兼容性

[M九项](../../tests/test_local_phase_velocity_damping.py)覆盖未限幅边反对称、相对速度两种符号、原2m/s限幅、两/三道全体同速30/15平衡、接近小位置误差时减小P修正、真实front target/reference、重标/倒序/远车、硬安全，以及600个已存局部state的完整NoA Command/Memory、cf_speed、safe_speed精确不变。先在L上出现3主项+5子断言的预期失败，M为9项/20子测试全过。

原L30项原样审计为 **28项通过、2项失败、106子测试通过**，没有改这些旧tests：

1. `test_original_hard_safe_cap_still_overrides_the_bridge`：原ego33.3、witness28.8使M阻尼项为−4.5m/s，raw action从旧P驱动降到27.7693125，低于安全上限27.9332591。旧“该帧必须超过cap再被截断”的前提失效，不能把不再触cap当安全回归。M新合同另用相同几何、witness33.3使相对速度0，明确验证raw action>cap且最终仍精确由原cap覆盖。
2. `test_without_actual_lane_two_both_policies_are_exactly_their_frozen_parent`：这是J2仅修一行物理枚举时的历史精确增量合同，要求没有lane2就与旧J0所有异速控制相同。M有意增加PD，不能继续承诺此等价；首个失败速度6.9415061对6.2741019，但真实target1017.7511130、reference7、状态和Memory完全相同。未修改/重绑J0历史源，也没有把随机比较数值换成M输出。

后者不是把全部旧L合同宽泛改为新数值的授权；当前相位/几何/CTH/安全/NoA合同仍分别保留，异速新控制由明确PD公式验证。是否改善实际编队/抑制加减速仍需父独立筛查，不能由静态PD称收敛。

## 操作

- L上专项红：`20261103T061633627761Z_M-relative-velocity-contract-red_ebf0e1bf`，exit1，3主项和5子断言失败。
- 最小构建：`20261103T061655424172Z_M-relative-velocity-source-build_6708f10f`，exit0。
- M专项绿：`20261103T061719059146Z_M-relative-velocity-contract-green_d6f03cc5`，exit0，9/20。
- 原L30审计：`20261103T061719074281Z_M-inherited-L30-unmodified-contract-audit_47f2f05a`，exit1，28/2/106，以上两项原因保留。

未跑仿真、未改L/NoA60/生产或原tests，无Git提交。M与后续N都从L独立分叉，不能混成一个增量。

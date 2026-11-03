# S：真实前车CTH方向优先

固定父L `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`，不叠M/PD、N或LT。新源SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`，461行，仅_following有实际front的原分支增加两行：

```text
if phase_speed * (following.speed - ego.speed) < 0:
    phase_speed = 0
```

随后原body速度 `following.speed+.2*phase_speed`、0/MAX夹紧、真实target/ref以及最终硬safe_speed均保持。无新阈值、参数、memory或neighbor flags；CF恰好0时乘积0不拦截，head没有actual front时不走新条件。[build](build.py)验证AST仅_following改变、反向精确恢复L；见[patch](native_rules.patch)、[身份](source.json)。

## 可证行为及代价

本规则只保证相位不反向抵消当前真实front CTH的速度修正，不保证相位恢复更快或完整形成收敛。同向修正仍叠加，可能更强加/减速；抑制反向修正也可能失去需要的相位恢复。零点不加滞回，切换行为保留，不以额外状态/门槛补救。

明确两道合同：ego lane1 x100、front124同速28.8，peer lane0 x125.5与ego互选e10.5；CF28.44、L叠+.4变28.84，S精确28.44。反向ego lane0 x100、front136、peer lane1 x75，CF29.16、L叠−.4变28.76，S精确29.16。真实target/reference不变。安全仍单独限制实际动作，S不是绕过安全来满足几何。

## TDD

[七项合同](../../tests/test_cth_priority_phase.py)检查上述两个反向冲突、正负同向及CF0时整个L following精确保留、head精确、重标/远车/真实reference、原停止安全硬cap和300已存局部state完整NoA/Memory/safe hex exact。

- L红：`20261103T072007007512Z_S-CTH-priority-phase-red_3e13776c`，exit1，2失败/5通过/5子通过。
- 构建：`20261103T072133419586Z_S-CTH-priority-phase-build_612fabc8`，exit0。
- S绿：`20261103T072150658037Z_S-CTH-priority-phase-green_b906ad80`，exit0，7项/5子测试全过，15:22前交父源。

原225+J2 patch审计为223通过/2个body旧相位叠加预期冲突/37子通过，真实CTH目标/ref、安全、NoA未见新增失败；[两项最小迁移](../../implementation/S_test_migration.md)内存核验后225项/37子全过，不改原tests。未运行交通/改生产或Git，父统一short/geometry后选择。

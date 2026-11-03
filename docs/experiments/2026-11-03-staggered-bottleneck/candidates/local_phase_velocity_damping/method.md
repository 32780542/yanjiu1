# M：实际互选边的相对速度阻尼

固定父L `e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a`，不叠NoA60或N。每条既有实际跨道互选边把原 `difference/n` 改为 `(difference+(peer.speed−ego.speed)/POSITION_GAIN)/n`，后续POSITION_GAIN、±2限幅及.2响应全部保持。相当于 `u_phase=sum(.3*e+v_peer−v_ego)/n`。

这是自行推导的局部PD项，使用当前可见相对速度；不继承文献图收敛或V2V证明。原相位误差交换反对称、共同n相同，相对速度也交换反对称，因此未限幅边项反对称。同速原平衡不变；不同节点的clip、自由head巡航回归与实际front CTH仍不构成整组零和。

不改邻接、真实前车、L witness、模板、gain、CTH、安全、横移、Memory或NoA。先专项红绿，再原样运行L30合同，逐项报告新速度规则与旧断言的实质差异，不修改旧tests来抹平。

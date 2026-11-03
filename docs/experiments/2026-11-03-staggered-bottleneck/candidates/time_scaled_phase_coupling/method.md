# 初版JT：仅速度伸缩增量，保留旧身份

该目录保持原JT identity，SHA `443e082742d1400ad03b4381e91cdace35cde522c48b6f11efd375ff89af287e`，441行。相对原J只把physical phase差乘 `D((v_i+v_j)/2)/30`，其它代码相同。

与原J一样保留已知准备区单边图，不覆盖旧build/patch/meta或原protocol。修正在独立 `time_scaled_phase_coupling_physical`。低速10m/s平衡仅约束有实际前车的body，head仍回CRUISE。

完整原文、合同及身份见[共同方法记录](../../methods/J_JT_local_coupling.md)。

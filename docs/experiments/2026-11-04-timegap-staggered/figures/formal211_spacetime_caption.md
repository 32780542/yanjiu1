# 固定正式seed211的瓶颈速度时空图

来源表：`docs\experiments\2026-11-04-timegap-staggered\data\formal600_main\per_case.csv`。预先固定seed211、2000 veh/h/lane，仅取C12_200/300的NoA与transform四例，未按结果选例。

图按两行200/300 m道路可见范围、两列NoA/C12排列，时间为`[100,600)` s、位置为`[0,1200)` m。每个25m×10s bin合并全车道的真实速度观测，以速度总和除以车辆观测样本数；每次车辆采样各计一次。这是车辆观测加权的均速，不能直接当作道路容量、吞吐量或独立车辆统计。

**所有面板共用0–33.3 m/s色标。灰色是样本数为0的缺测bin，均速留空，既不按0计也不解释为畅通。**实线为1000m缩道位置；虚线分别为800/700m开始可见道路的位置，仅标道路信息边界，不是强制准备区。positions第四列是纵向加速度，本图只读取x与speed。

PNG为300 dpi，另存矢量SVG；实际使用字体为`Microsoft YaHei`。图的9600个bin完整保存在同名`_bins.csv`，含速度和、样本数、均速、边界和源run。

| 面板 | case | 时间帧 | 时间窗内车辆观测 | 纳入时空窗的车辆观测 | 空bin / 2400 |
| --- | --- | ---: | ---: | ---: | ---: |
| a | C12_200 / noa | 5000 | 461833 | 461833 | 0 |
| b | C12_200 / transform | 5000 | 380027 | 380027 | 0 |
| c | C12_300 / noa | 5000 | 454972 | 454972 | 0 |
| d | C12_300 / transform | 5000 | 368082 | 368082 | 0 |

四例共1,664,914个车辆观测、9600个bin，其中空bin合计0个。图例保留灰色缺测编码；时空均值会平滑单车短时速度，不能据某个bin均速不为0推断其中没有车辆短暂停车。

## 四条原始case身份

- `C12_200 / noa / lane_drop / flow2000 / seed211`：`D:\yanjiu1\keyan1\tmp\staggered_bottleneck\20261104_formal600_main_drop_211_215_r01\cases\C12_200_2000_211_lane_drop_noa\20261103T205018566669Z_lane_drop_noa_s211_c11f71`。
- `C12_200 / transform / lane_drop / flow2000 / seed211`：`D:\yanjiu1\keyan1\tmp\staggered_bottleneck\20261104_formal600_main_drop_211_215_r01\cases\C12_200_2000_211_lane_drop_transform\20261103T205215547641Z_lane_drop_transform_s211_820956`。
- `C12_300 / noa / lane_drop / flow2000 / seed211`：`D:\yanjiu1\keyan1\tmp\staggered_bottleneck\20261104_formal600_main_drop_211_215_r01\cases\C12_300_2000_211_lane_drop_noa\20261103T211903521959Z_lane_drop_noa_s211_21900f`。
- `C12_300 / transform / lane_drop / flow2000 / seed211`：`D:\yanjiu1\keyan1\tmp\staggered_bottleneck\20261104_formal600_main_drop_211_215_r01\cases\C12_300_2000_211_lane_drop_transform\20261103T212050786499Z_lane_drop_transform_s211_67744a`。

## 复现

工具[../tools/plot_spacetime.py](../tools/plot_spacetime.py)自包含，仅依赖Python、NumPy、Matplotlib和上述四条本机原始轨迹。图与bin表可随仓库保存；完整全路raw不全量入Git。没有读取旧数据、启动SUMO、修改控制器或新增评价门。

```powershell
python -X utf8 -B scripts/run_logged.py --label formal211_spacetime --timeout 300 -- python -X utf8 -B docs/experiments/2026-11-04-timegap-staggered/tools/plot_spacetime.py
```

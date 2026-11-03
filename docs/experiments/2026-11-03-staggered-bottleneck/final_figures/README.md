# 锁定 S 的正式结果与瓶颈时空可视化

正式表完整为160例：8种每道流量×两种道路×5个新种子61–65×NoA/S；160例均安全排空，80对全部可比。S在种子61批开始前锁定，规则SHA `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`。这里仅从现有结果作图，没有新增仿真、控制或成功门槛。

- [系统时间均值、全部5个种子原值与配对改善](system_time_and_paired_improvement.png)，[SVG](system_time_and_paired_improvement.svg)。上排细点是全部原值，连线是种子等权均值；下排细点为各同种子改善，菱形为均值之比 `100×(NoA均值−S均值)/NoA均值`，不把五个百分比平均冒充均值之比。两种道路分图且纵轴尺度不同，需按刻度读数。
- [独立燃油代价图](fuel_cost_paired.png)，[SVG](fuel_cost_paired.svg)。差值为S−NoA，正数代表燃油增加；所有正差和种子离散均保留，未由系统时间改善推断节油。
- [2250每道流量、seed42、1800秒需求的真实速度时空图](long1800_2250_seed42_speed_raster.png)，[SVG](long1800_2250_seed42_speed_raster.svg)。相同实际arrival/物理/执行设置及非规则源码，唯一政策差异为NoA与锁定S。原input的mode和controller来源字段按设计不同，没有错误要求整个input字节相同。

3→2在2250/2500每道流量的系统时间均值分别从59.3490/84.2606秒降至49.9637/72.1779秒，改善15.8138%/14.3397%，每档5/5种子改善；燃油分别增加3.9079/4.8132 g/km。低流量3→2改善较小，500档仅2/5种子改善，均值改善0.0242%。直路改善范围0.1264%–1.1828%，不能把直路小幅改善等同于瓶颈降拥堵。

时空图使用原完整positions中的全部0.1秒实际样本，仅取`100≤t<1800`、`500≤x<1000`；每个20米×5秒格聚合三个实际车道上观测到的所有车辆速度样本的算术均值。它是车辆样本加权速度，不是流量或密度。无样本格为NaN/灰色，不填零、不插值、不平滑；两图统一0–32 m/s色标。原记录未裁切或修改，每源窗口17000帧。虚线640米标准备区起点，1000米为3→2瓶颈。图显示这一指定输入中NoA的低速积聚在空间及时间上更广；它是单种子描述性可视化，不作新统计门槛或全工况因果证明。

[每格样本数、速度和及均速](speed_raster_cells.csv)及两份同名NPZ保留可复算数据；[来源与哈希](provenance.json)列正式CSV、规则、原positions、seal、需求及绘图技能源码SHA。[原轨迹与封存区域账本抽核](raw_ledger_spotchecks.csv)在100/600/1000/1799.9秒共8帧逐项核验800≤x<1000的车辆数、低速数和速度和，全部一致。[source_tables](source_tables/flow_means.csv)是正式源表的字节副本，原CSV未改。全部PNG为300dpi，SVG保留可编辑文字；三张PNG已经目检，标签、零线、色标与所有实际散点均清晰。

所选NoA/S原positions.gz分别66,114,791/56,509,625字节，单文件已超过20MB，因此不伪称有完整小于20MB审查包；这两例完整raw保留本地，准确路径、字节数及SHA见provenance。另六个同批成功案例经独立审核、完整compact/ledger分包、逐文件验证及父明确授权后，仅清理positions/events；[精确清单](../long_window_NOA_S1800/evidence_profiles/pruning_verification.json)保留，旧L及其他批raw未动。[最终图与来源核验](final_verification.json)列全部300dpi/SVG/数据哈希检查。

绘图工具为[make_final_figures.py](../tools/make_final_figures.py)，复用academic-figures的Nature样式。首尝试错误地断言整个input相同，在S的mode/controller字段差异处停止；原图和失败工具完整保留于[attempt1](../final_figures_attempt1/failed_tool.py)，operation `20261103T081648719868Z_final61-academic-figures_4cacc879`。按实际合同改为逐字段核验相同arrival、物理、执行及所有非规则源码后，独立新目录重试通过：`20261103T081739359549Z_final61-academic-figures-retry2_d27a6763`。没有更改数据或运行仿真。

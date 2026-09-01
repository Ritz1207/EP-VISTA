# 数据来源与引用

本文件记录当前随项目保留的数据来源，不是第三方授权书。软件的BibTeX、GB/T 7714—2025和MLA格式见[软件引用说明](../CITATION.md)，机器可读元数据见[CITATION.cff](../CITATION.cff)，模型与依赖引用见[第三方说明](../licenses/THIRD_PARTY_NOTICES.md)。

## 历史空间天气

随附文件：data/space_weather/space_weather_20250320_10002h_3h.csv，及同目录来源manifest。文件原样保留，拟随项目公开内容一起审查；没有替换成合成数据。

- 原始来源：[CelesTrak Space Weather Data](https://celestrak.org/SpaceData/)，原表为[SW-All.csv](https://celestrak.org/SpaceData/SW-All.csv)。
- 字段定义和上游提供方：[CelesTrak格式说明](https://celestrak.org/SpaceData/SpaceWx-format.php)。CelesTrak汇集多个提供方的数据，不能把所有观测都归为CelesTrak自行测量。
- 本地原表快照文件名：SW-All_20260827.csv。
- 原表SHA-256：CF390D31F53830A1443B828018D694136CF18706BCB99EFA7908FF83E130A7E3。在线SW-All.csv会更新，不应期待今天下载的文件与该快照哈希相同。
- 整理后记录3335行，首条2025-03-20T00:00:00Z，末条2026-05-10T18:00:00Z，间隔3小时；7行保留插值/预测质量标记。它是本地历史输入整理表，不是NRL大气密度数据库或实时预报。
- F10.7使用前一日值和中心81日均值；Ap包含日平均、当前及历史分量，字段定义见[数据使用说明](DATA_GUIDE.md)。

推荐在实际使用该数据的论文中说明：空间天气输入由CelesTrak SW-All快照整理，注明快照文件名、覆盖范围及F10.7/Ap处理方式，并按实际使用的上游产品要求补充引用。Kp/Ap相关文献可参考 Matzka et al. (2021), The geomagnetic Kp index and derived indices of geomagnetic activity, [DOI](https://doi.org/10.1029/2020SW002641)。

## 推进器性能与默认质量

统一文件：data/thrusters/thrusters.csv。该文件当前10条记录已确认为EP-VISTA V1.0正式公开基准；性能来源与质量来源是两个独立字段，不能相互代替。`user_input`表示记录形成方式，不表示该记录属于需要排除的个人项目。

| ID | V1.0记录的性能来源 | 来源定位 | 默认结构质量来源 |
|---|---|---|---|
| ENG_ABEP20 | 当前VLEO方案工程输入 | 工程假设，不是文献设备 | 未知 |
| Hall_01 | NASA Technical Reports Server | NTRS文档链接 | ResearchGate资料，3 kg |
| Hall_02 | AIAA JPP 2016 | DOI页面 | 同类6 kW级推力器整机估计，15 kg |
| Ion_01 | NEXT-C status report | 报告PDF | 同一报告，13 kg |
| Customized_01、Customized_02、Customized_03 | 用户输入的公开基准记录 | 无外部定位 | 用户输入，分别为1.8、1.4、1.4 kg |
| Hall_03 | Busek BHT-200产品页 | 产品页 | 同一产品页，1.1 kg |
| Hall_04 | Safran PPS-1350-S数据表 | 数据表PDF | 同一数据表，4.8 kg |
| Ion_02 | QinetiQ T5资料页 | Satsearch产品页 | 同一资料页，2 kg |

以上是V1.0公开基准记录及其证据线索，不是完整书目核验。部分来源还缺作者、完整题名、报告号或DOI；本次未猜填。后续应根据对应原文补全，保留CSV的source、locator和verification_status。`pending_human_verification`与`user_input`均不能据此声称已通过设备鉴定或第三方权利审查。

近似质量不是上述性能文献中的测量结论。是否包含PPU、储箱等配套部件仍须确认；未知质量保留为空，不改成0。数值预测、图读、推导与实测也应分别标注，不混作同等级证据。

## 新增资料的署名与范围

型号库新增/编辑表单提供性能来源、来源位置、性能备注、质量来源及质量计入范围。收录自己的记录时请如实填写。提交外部资料时，除学术来源外还应说明适用的使用和再分发依据；公开可下载、写了引用与获得许可不是同一件事。

历史数据现按作者要求保留，但本地整理和引用补充不等于已完成所有第三方权利核查。本次不执行外部发布，不改变NRL模型，也不宣称取得了额外NRL授权。

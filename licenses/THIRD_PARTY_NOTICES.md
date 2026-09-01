# 第三方软件、模型和数据说明

发布策略为仅提供EP-VISTA自研源码及必要文档、配置和经核查的数据；Python环境、第三方包与模型由使用者另行安装，不随本项目分发。自研程序的AGPL及 [窄范围附加许可](../ADDITIONAL_PERMISSION.md) 不替代第三方许可；当前随目录保留的数据仍有公开前核查事项。

## NRLMSIS 2.0

`pymsis==0.12.0`的Python封装是MIT（Copyright (c) 2020, Regents of the University of Colorado），其调用的NRLMSIS 2.0模型另有学术非商业许可，并列有修改、复制和传播限制。条款提及MSIS商标和美国专利10,641,925。完整原文保留在 [MSIS2_LICENSE](MSIS2_LICENSE)，来源为 [pymsis v0.12.0](https://github.com/SWxTREC/pymsis/blob/v0.12.0/MSIS2_LICENSE)。

仅公开自研接口代码，与分发模型源码/二进制不是同一行为，不能一概认为都需要新增NRL许可。作者已依据AGPL第7条提供 [ADDITIONAL_PERMISSION.md](../ADDITIONAL_PERMISSION.md)：仅针对自研代码与**未修改NRLMSIS 2.0经pymsis 0.12.0**的源码分发和互操作放宽指定AGPL条件。该例外不是一般闭源库例外，也不是模型捆绑发行许可，更不授予NRL模型的任何权利。

当前程序直接依赖pymsis/NRLMSIS完成计算，不是可切换的可选模型。依赖声明不是把第三方源码或二进制收入本项目仓库；但使用者从其他渠道取得的pymsis安装包可能含模型二进制，不能因此把整个包当作纯MIT授权。模型使用、修改、支持数据和组合发行必须按原文分别核对；超出已有许可的用途需取得对应授权。本项目未改换模型或取得额外NRL授权，不能承诺完整运行环境自由商用。

[pymsis官方文档](https://swxtrec.github.io/pymsis/)明确提示MSIS2商用应联系NRL；有关授权范围宜向 [NRL技术转移办公室](https://www.nrl.navy.mil/Doing-Business/Technology-Transfer/)或其知识产权法律顾问核实。引用论文或购买EP-VISTA作者的商业许可不能代替NRL权利。

## 其他运行依赖

| 依赖 | 固定版本 | 许可线索 |
|---|---|---|
| Python | 3.11系列 | Python Software Foundation许可及附带声明 |
| NumPy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0（包元数据） |
| Matplotlib | 3.11.1 | Matplotlib/PSF风格许可、历史与内嵌组件声明 |
| PySide6-Essentials | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only；按实际组件和所选条款核查 |

保留各自安装包附带的完整许可证。若以后再分发环境包、EXE或容器，须清点所有二进制及其源码提供义务；本次未做此类打包。[Qt for Python许可说明](https://doc.qt.io/qtforpython-6/licenses.html)。

附加许可仅放宽EP-VISTA作者可控制的指定AGPL条件；不代替PySide6/Qt、pymsis或其他第三方著作权人的许可，不自动把例外扩展到新的第三方贡献或依赖。

## 数据与结果

- 空间天气文件来自 [CelesTrak Space Data](https://celestrak.org/SpaceData/)的SW-All.csv整理；同目录manifest保留原始文件哈希、覆盖范围与7行插值/预测标记统计。保持原件，不把它当作真实预报。
- `data/thrusters/thrusters.csv`统一包含性能与默认结构质量；性能来源、质量来源及计入范围分别保存。质量为用户提供的近似算例值，不等于经鉴定设备数据，`pending_human_verification`也不是许可审核结论。历史天气与推进器来源集中记录在[数据来源与引用](../docs/DATA_SOURCES.md)；真实数据按作者要求保留，不替换为合成数据。
- 完整性能证据CSV、数据说明和冻结基准已在目录外原始快照归档，未销毁；当前数值数据的公开/再分发权利仍须逐项核查。示例配置的自研表达采用AGPL，不代表其引用数据被重新授权。
- 数值事实、数据库汇编、模型输出和受保护的图表/文档应区分处理。本说明不限制公共领域事实或法定允许使用，也不保证所有计算输出均无第三方限制。

## 科研引用

- Lucas, G. (2022), pymsis [Computer software], [DOI](https://doi.org/10.5281/zenodo.5348502)，按上游要求致谢SWx TREC。
- Emmert et al. (2020), NRLMSIS 2.0: A whole-atmosphere empirical model of temperature and neutral species densities, [DOI](https://doi.org/10.1029/2020EA001321)；[NASA模型页](https://ccmc.gsfc.nasa.gov/models/NRLMSIS~2.0/)。
- 空间天气按CelesTrak与原始提供方要求引用；Kp/Ap相关引用可参见 [Matzka et al. (2021)](https://doi.org/10.1029/2020SW002641)。

## 随附许可证原文核对

2026-08-31从上游获取，仅统一LF及末尾换行；SHA-256：

- `../LICENSE`：`0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`；[GNU原文](https://www.gnu.org/licenses/agpl-3.0.txt)。
- `CC-BY-SA-4.0.txt`：`23ee78c8bae49cf08ea2f0c84945c66b987ebe4520881fb51b3dad4fb43d07c2`；[CC原文](https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt)。
- `MSIS2_LICENSE`：`79ec3c0d79e48d3740b6da55ff6314dee59f6e6794a53e28f9d85afc1140fef4`。

本说明不是法律意见、第三方授权书或商业可用性保证。自研作品授权范围见 [NOTICE.md](NOTICE.md)。

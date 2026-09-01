# 如何引用EP-VISTA

下列格式对应当前软件元数据：公开作者署名Ritz，软件正式版本V1.0，正式发布日期为2026-09-01。中文全称为“超低轨道电推进系统方案权衡分析平台”，英文全称为“Electric Propulsion for VLEO Integrated System Trade Analysis”，简称EP-VISTA。正式仓库为[GitHub上的Ritz1207/EP-VISTA](https://github.com/Ritz1207/EP-VISTA)，V1.0固定版本地址为[releases/tag/V1.0](https://github.com/Ritz1207/EP-VISTA/releases/tag/V1.0)。当前尚未取得DOI，因此不填写不存在的标识；取得后应同步更新本文件和[CITATION.cff](CITATION.cff)，但不改写已经公开的V1.0标签。

引用EP-VISTA不能代替对实际使用的NRLMSIS、pymsis及数据来源的引用；相应信息见[第三方说明](licenses/THIRD_PARTY_NOTICES.md)和[数据来源与引用](docs/DATA_SOURCES.md)。引用建议不构成软件许可的附加限制。

## BibTeX

```bibtex
@software{ritz_ep_vista_v1_0,
  author  = {Ritz},
  title   = {{EP-VISTA}: Electric Propulsion for VLEO Integrated System Trade Analysis},
  version = {V1.0},
  year    = {2026},
  url     = {https://github.com/Ritz1207/EP-VISTA/releases/tag/V1.0}
}
```

其中2026同时是版权年份和V1.0发布年份；精确发布日期由`CITATION.cff`的`date-released`字段记录。GitHub也会依据CFF元数据生成`@software`类型的BibTeX。

## GB/T 7714—2025

> RITZ. EP-VISTA: Electric Propulsion for VLEO Integrated System Trade Analysis[CP/OL]. V1.0版. 2026-09-01[引用日期]. https://github.com/Ritz1207/EP-VISTA/releases/tag/V1.0.

正式版本按联机计算机程序`[CP/OL]`著录；使用时请把`[引用日期]`替换为实际访问日期。[GB/T 7714—2025](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=C6CE52E55AC09B9C79A20AEA77CEDD14)已经于2026年7月1日实施，取代GB/T 7714—2015。

## MLA

> Ritz. *EP-VISTA: Electric Propulsion for VLEO Integrated System Trade Analysis*. Version V1.0, 1 Sept. 2026, GitHub, https://github.com/Ritz1207/EP-VISTA/releases/tag/V1.0.

MLA格式中软件标题应使用斜体；如具体使用场景要求访问日期，请按实际访问日补充。

## 格式依据

- [Citation File Format 1.2.0规范](https://github.com/citation-file-format/citation-file-format/blob/main/schema-guide.md)：CFF保存机器可读的软件引用元数据。
- [GitHub引用文件说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)：GitHub依据CFF生成APA和`@software` BibTeX。
- [GB/T 7714—2025国家标准信息](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=C6CE52E55AC09B9C79A20AEA77CEDD14)：当前现行国标及实施日期。
- [MLA Style Center的软件源代码引用说明](https://style.mla.org/citing-source-code/)：作者、版本等软件引用元素。

## DOI取得后需要补充

- 在`CITATION.cff`中填写真实DOI，并在三种人工格式中同步补充。
- DOI取得后的更新只追加到`main`，不改写已经公开的`V1.0`标签。
- GB/T 7714—2025中的`[引用日期]`仍由实际引用者填写。
- 不要把临时本机路径、预览仓库地址或尚未注册的DOI写入引用。

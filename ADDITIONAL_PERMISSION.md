# EP-VISTA NRLMSIS 2.0 Additional Permission

Version 1.0 — 2026-08-31

`Copyright © 2026 Ritz`

Base license: **GNU Affero General Public License, version 3 or (at your option) any later version**. The official text in [LICENSE](LICENSE) is unchanged; the project license notice is in [NOTICE.md](licenses/NOTICE.md).

The English terms below are the operative permission. The Chinese summary is explanatory only. This document grants an additional permission under GNU AGPL version 3, section 7; it is not a replacement license or a noncommercial restriction on EP-VISTA.

## 1. Covered code and grantor

“Covered Code” means the original EP-VISTA program code, configuration and example configuration for which Ritz is the publicly credited copyright holder and to which a source notice or licenses/NOTICE.md applies this permission. This permission applies only to rights the grantor controls. It does not automatically apply to code owned by another contributor, third-party packages, models, data, documentation or trademarks.

## 2. Designated model and interface

“Designated Model” means the **unmodified NRLMSIS 2.0** model published by the U.S. Naval Research Laboratory (NRL), identified as MSIS (NRL-SOF-014-1) in the model terms reproduced in [licenses/MSIS2_LICENSE](licenses/MSIS2_LICENSE).

“Designated Interface” means the **pymsis 0.12.0 Python wrapper**, under its own MIT license, used to invoke NRLMSIS 2.0. The model is not part of the wrapper's MIT grant.

This permission does not extend to NRLMSISE-00, NRLMSIS 2.1, other model or interface versions, modified model implementations, or unrelated proprietary components.

## 3. Narrow permission for source distribution and interoperability

You have additional permission, insofar as rights in the Covered Code are concerned, to link or combine the Covered Code with the Designated Model through the Designated Interface, to run that combination, and to convey the Covered Code in source form, including modifications and adapters, for use with a separately acquired copy of the Designated Model.

Solely because of that permitted combination, the AGPL conditions applicable to the Covered Code do not require the Designated Model to be relicensed under the AGPL or its source to be supplied as part of the Corresponding Source of the Covered Code. This waiver applies only to the Designated Model, not to the EP-VISTA code that calls, adapts or communicates with it.

All otherwise applicable AGPL obligations for the Covered Code remain, including copyright and license notices and the Corresponding Source obligations for modifications, adapters, build/install scripts and modified versions used for remote network interaction. This permission does not permit the Covered Code or its modifications to be made proprietary merely because the Designated Model is used.

## 4. No grant of third-party rights

You must independently obtain and comply with the rights required to acquire, use, copy, modify or redistribute the Designated Model and Designated Interface. The Designated Model's academic/noncommercial and other conditions remain its own conditions, not new restrictions on EP-VISTA's AGPL license.

This document grants no NRL or other third-party copyright, patent, trademark, data or commercial-use rights. In particular, it is not NRL consent to commercial use, model modification or model redistribution. Neither citing NRL nor obtaining a separate EP-VISTA commercial license substitutes for any required NRL authorization.

## 5. No general bundling or proprietary-library exception

This additional permission addresses EP-VISTA source distribution and interoperability with the separately acquired Designated Model. It grants no additional permission to convey a binary or environment bundle containing the Designated Model, or to combine EP-VISTA with other AGPL-incompatible components. Such activities require their own compatibility and authorization assessment.

Nothing here narrows rights already available under the unmodified AGPL, the Designated Interface's MIT license, another valid license or applicable law. This document neither grants nor revokes rights independently granted by NRL.

## 6. Downstream notices and contributions

When relying on this permission, preserve the applicable notice and provide this document with the Covered Code as required by AGPL section 7. As that section provides, recipients may remove this additional permission from a copy; a copy without the permission cannot rely on it.

Contributors may expressly extend this permission to material they own, but are not compelled to do so by this document. Do not represent a contribution as covered by this permission unless its copyright holder has granted it. Any separate commercial relicensing authority must also be obtained independently.

## Metadata identifier

`LicenseRef-EP-VISTA-AGPL-3.0-or-later-NRLMSIS` identifies the **base AGPL-3.0-or-later terms together with this Version 1.0 additional permission**. It is a local SPDX license reference, not an SPDX-listed exception or an alternative permissive license. It does not include the NRL model license. The same identifier is used in project metadata and source notices to point to this complete set of terms.

## 中文说明（非替代条款）

- EP-VISTA 自研代码仍采用 AGPL-3.0-or-later；本例外仅放宽作者有权放宽的组合使用条件，不给自研代码附加“仅学术、不可商用”限制。
- 范围仅为**未修改的 NRLMSIS 2.0，通过 pymsis 0.12.0 调用**。不自动覆盖其他模型、版本、闭源组件或模型修改。
- 允许以源码形式分发相应 EP-VISTA 代码，并与用户另行合法获取的模型互操作；不因该组合要求把 NRL 模型改为 AGPL 或作为 EP-VISTA 对应源码提供。EP-VISTA 自身的修改、适配和对应源码义务仍按 AGPL 执行。
- 此文件不是 NRL 授权书，不授予模型的商用、修改、再分发、专利或商标权，也不是打包 EXE、完整环境或模型二进制的额外许可。
- 当前程序计算仍依赖 NRLMSIS；“另行安装”不等于技术上已有可选后端。自研源码开源不等于完整依赖环境可以自由商用。
- 下游可以按 AGPL 第7条移除附加许可。新贡献是否适用本例外、作者是否能单独商业再许可，均须有相应权利依据。

## Reference texts

- [GNU AGPL section 7](https://www.gnu.org/licenses/agpl-3.0.en.html#section7)
- [GNU FAQ on GPL-incompatible libraries and linking permissions](https://www.gnu.org/licenses/gpl-faq.en.html#GPLIncompatibleLibs) — the mechanism is guidance; the narrowly defined permission above is specific to EP-VISTA, not an FSF-approved NRL exception.
- [pymsis v0.12.0 model terms](https://github.com/SWxTREC/pymsis/blob/v0.12.0/MSIS2_LICENSE)

This file is the copyright holder's permission for the Covered Code, not a third-party authorization, legal opinion or guarantee of commercial usability of the complete runtime.

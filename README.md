# EP-VISTA

**超低轨道电推进系统方案权衡分析平台**

**Electric Propulsion for VLEO Integrated System Trade Analysis** · 正式版本 `V1.0`

EP-VISTA 是面向甚低地球轨道（VLEO）任务的电推进方案权衡分析平台。平台根据用户输入的轨道高度，自动计算满足当前J2节点进动近似的圆形太阳同步轨道（SSO）倾角，并结合给定的LTAN和起始时刻确定初始升交点赤经；随后在给定系统假设下，比较传统携带工质的电推进与吸气式电推进（ABEP）的推阻关系、供电需求和质量组成，提供中文桌面界面与命令行入口。

这是用于研究与方案分析的平台，不是设备选型认证或真实轨道控制仿真。结果需要结合模型假设、输入来源和采样收敛性判断。

## 功能

- 分析任务全程和单圈的推阻关系，检查逐圈平均推力、供电及设备工作范围。
- 比较太阳翼、电池、推进单元和携带推进剂等质量组成。
- 执行轨道高度扫描，查看不同轨道高度下的大气阻力、所需推进剂和推阻关系变化。
- 管理跨任务共享的推进器型号库，支持修改ID、删除记录、区分推进器类型与推进方式，以及CSV导入/导出和项目参数快照。
- 保存、打开项目设置；通过命令行校验输入和运行分析。

当前结果在界面或终端查看，不提供结果报告文件导出。

## 安装与启动

### 运行要求

- Python 3.11；当前验证环境为 Windows 11，其他操作系统尚未验证。
- NumPy、pymsis、Matplotlib、PySide6-Essentials，版本见 [environment.yml](environment.yml)。
- 首次配置需要 Conda 和网络；依赖安装完成且历史输入齐备后，计算不需要在线下载数据。

当前计算所使用的大气模型依赖 pymsis 0.12.0 调用 NRLMSIS 2.0；EP-VISTA 的许可不授予该第三方模型的额外权利。**若涉及商业用途，请阅读 [NRLMSIS 许可](licenses/MSIS2_LICENSE) 和 [第三方说明](licenses/THIRD_PARTY_NOTICES.md)，遵循相关要求。**

### 从源码运行

获取并解压或克隆完整源码后，在仓库根目录（包含本 README 和 `environment.yml` 的目录）打开支持 Conda 的终端：

```powershell
conda env create -f environment.yml
conda activate ep-vista
python run_ep_vista_gui.py
```

以后启动只需激活环境并运行最后一条命令（即以上的2-3行）。请完整保留 `src/`、`data/`、`examples/` 和根目录启动脚本；运行时会按需生成 `workspace/` 下的本地文件。

本项目按独立源码仓库组织，不依赖外层科研项目或指定磁盘位置。无需安装 EP-VISTA 项目包即可启动；当前不提供 EXE 或脱离源码数据目录的独立安装包。

## 快速上手

1. 按照上方”从源码运行“的指南，通过终端启动 GUI，点击“打开项目”，选择 [battery_mass_demo.ep-vista.json](examples/battery_mass_demo.ep-vista.json)。
2. 核对起始 UTC、轨道、功率与质量参数。该示例任务为 100 h，系统参数用于演示，不是设备推荐；天气输入采用随附历史数据。
3. 运行分析，在结果窗口查看“任务全程推阻关系”“绕地一周”和“结论”；高度扫描需另行启动。
4. 修改输入后重新计算，将自己的设置另存为 `.ep-vista.json`。

启动时使用的 [空白项目模板](examples/new_project_template.ep-vista.json) 有意保留必填空项和空候选表，需要填写参数、载入推进方案后才能计算。详细操作见 [使用指南](docs/USER_GUIDE.md)。

命令行操作同样在仓库根目录执行：

```powershell
python run_ep_vista_cli.py validate examples/battery_mass_demo.ep-vista.json
python run_ep_vista_cli.py list-thrusters
python run_ep_vista_cli.py run examples/battery_mass_demo.ep-vista.json
```

`validate` 只检查输入，不执行大气计算；它不等于物理验证或天气全程覆盖检查。`run` 执行计算并在终端显示结论，首次运行会生成缓存。

## 模型边界

- 支持 150–300 km 受控恒定高度圆形 SSO，采用 J2 长期节点变化、固定阻力系数、理想对日太阳翼和 NRLMSIS 2.0。
- “满足任务”要求每圈时间平均可用推力严格大于该圈平均整星阻力，并满足供电和设备工作范围等条件；这不保证圈内每个时刻都能定高。
- 不模拟轨道下降、大气风场/共转、食期储能与充电循环、进气道详细损失，也不替代完整 EPS、热设计或设备寿命认证。
- 历史天气必须覆盖任务及起始一圈的取样范围；固定活动等级只是敏感性情景，不是预报。默认型号中的待核验参数和近似质量不能作为已鉴定设备证据。

输入口径、计算判据与完整限制见 [使用指南](docs/USER_GUIDE.md)；来源记录见 [数据来源与引用](docs/DATA_SOURCES.md)。

## 文档与贡献

| 内容 | 入口 |
|---|---|
| 界面操作、输入口径、结果解释、文件与缓存 | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| 轨道、大气、阻力、推进、供电与质量的模型公式 | [docs/MODEL_AND_EQUATIONS.md](docs/MODEL_AND_EQUATIONS.md) |
| 推进器型号库、项目快照与天气 CSV 格式 | [docs/DATA_GUIDE.md](docs/DATA_GUIDE.md) |
| 数据来源、引用线索与待核验项 | [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) |
| 开发环境、测试、Issue 与 PR | [./CONTRIBUTING.md](CONTRIBUTING.md) |
| 维护者发布前检查 | [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) |

问题反馈请附版本、环境、复现步骤和不含隐私的最小示例，不要上传整个 `workspace/`。维护者：Ritz；请通过[仓库Issue](https://github.com/Ritz1207/EP-VISTA/issues)反馈。

## 许可与引用

自研程序采用 **AGPL-3.0-or-later**，并提供仅针对未修改 NRLMSIS 2.0 经 pymsis 0.12.0 互操作的窄范围附加许可。完整范围见 [版权说明](licenses/NOTICE.md)、[AGPL 原文](LICENSE) 和 [附加许可](ADDITIONAL_PERMISSION.md)。原创说明文档的 CC BY-SA 4.0 许可范围也见版权说明。

NRLMSIS 及其他第三方软件、模型和数据保留各自条款；自研代码开源不等于完整运行环境自由商用。本仓库不随源码提供模型源码/二进制或完整 Python 环境。随附数据的来源与再分发核查尚未全部完成，正式公开前须完成 [发布检查](docs/RELEASE_CHECKLIST.md)。

科研使用请从[软件引用说明](CITATION.md)选择BibTeX、GB/T 7714—2025或MLA格式；机器可读元数据见[CITATION.cff](CITATION.cff)。另请引用实际使用的模型及数据来源；引用建议不构成AGPL的附加限制。

`Copyright © 2026 Ritz`

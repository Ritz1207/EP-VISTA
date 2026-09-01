# 模型、指标与计算公式

本文档对应 EP-VISTA V1.0 的当前源码实现，说明从配置输入到轨道、大气、阻力、推进、供电、质量和高度扫描结果的计算链。本文档的目标是让使用者能够核对每个主要指标的定义、单位、数值方法和适用边界，而不是把软件测试等同于物理验证或设备认证。

公式旁的“外部依据”链接用于说明通用物理关系、第三方模型接口或数值算法的来源；“EP-VISTA 实现”链接指向本仓库实际执行的代码。两者必须同时阅读：外部资料不自动证明本实现正确，本地实现也不替代对外部模型和数据的正式引用。

## 1. 计算范围与总体流程

当前计算链为：

1. 根据任务高度、起始 UTC、LTAN、任务时长和沿轨道相位步长生成受控恒定高度圆形太阳同步轨道（SSO）采样点。
2. 将各采样点的 UTC、经纬度、高度以及 F10.7、Ap 输入 NRLMSIS 2.0，得到质量密度、组分数密度和温度。
3. 计算本体和理想对日太阳翼的迎风阻力，并对阻力进行时间积分。
4. 根据推进器推功比、比冲、功率范围和集气效率计算传统电推进或 ABEP 的可用推力。
5. 按逐圈时间平均的严格大于判据判断推力是否满足任务，同时独立检查供电和设备工作范围。
6. 根据线性供电闭合关系估算太阳翼、电池和任务初始质量组成。
7. 高度扫描对每个指定高度重复完整计算，不传播同一卫星在高度方向上的自然演化。

当前模型不传播轨道下降或圈内高度波动，不计算气动姿态、热设计、食期储能、充电循环、设备退化、可靠度或真实寿命。任务“设计寿命”只是计算时域和推进剂/电量累计时长，不是寿命预测结果。

## 2. 符号、单位与实现常数

| 符号 | 含义 | 当前值或单位 | 性质 |
|---|---|---:|---|
| $R_E$ | 地球平均半径 | 6,371,000 m | 源码常数 |
| $\mu_E$ | 地球引力参数 | $3.986004418\times10^{14}$ m³/s² | 源码常数 |
| $J_2$ | 地球二阶带谐系数 | $1.08262668\times10^{-3}$ | 源码常数 |
| $Y_{\mathrm{trop}}$ | 回归年长度 | 365.2422 d | 源码常数 |
| $g_0$ | 标准重力加速度 | 9.80665 m/s² | 常规标准值 |
| $h$ | 输入轨道高度 | km，界面限制 150–300 km | 配置输入 |
| $t$ | 自任务开始的时间 | s | 数值自变量 |
| $\rho$ | NRLMSIS 总质量密度 | kg/m³ | 第三方模型输出 |
| $v$ | 当前圆轨道惯性速度模 | m/s | 模型计算量 |
| $D$ | 整星阻力 | N；界面通常显示 mN | 模型计算量 |
| $I_{\mathrm{tot}}$ | 阻力总冲量 | N·s | 时间积分量 |
| $I_{\mathrm{sp}}$ | 比冲 | s | 推进器输入 |
| $k_{TP}$ | 推功比 | mN/kW | 推进器输入 |
| $\eta_c$ | ABEP 集气效率 | 0–1 | 推进器输入 |

上述地球参数是 EP-VISTA 当前代码采用的一组简化常数，并未声明为某一高精度地球参考系的完整参数集。NASA资料可用于核对圆轨道关系和常见地球参数量级，但不能据此把本程序视为高精度定轨软件：[NASA圆轨道公式](https://ntrs.nasa.gov/api/citations/19950006116/downloads/19950006116.pdf)、[NASA天体参数示例](https://ntrs.nasa.gov/api/citations/20070038369/downloads/20070038369.pdf)。$g_0$ 的常规值可在 [BIPM VIM 2.12](https://jcgm.bipm.org/vim/en/2.12.html) 核对。

EP-VISTA 实现：[orbit.py](../src/ep_vista_core/orbit.py)、[models.py](../src/ep_vista_core/models.py)。

## 3. 圆形 SSO 与时间采样

### 3.1 轨道半径、平均角速度、速度和周期

程序采用球形地球和二体圆轨道关系：

$$
r=R_E+1000h,
$$

$$
n=\sqrt{\frac{\mu_E}{r^3}},
\qquad
v=rn=\sqrt{\frac{\mu_E}{r}},
$$

$$
T_{\mathrm{orb}}=\frac{2\pi}{n}=2\pi\sqrt{\frac{r^3}{\mu_E}}.
$$

界面中的“轨道周期”就是 $T_{\mathrm{orb}}$。速度 $v$ 是圆轨道惯性速度，不扣除地球大气共转速度或风速；该处理直接影响后续阻力和 ABEP 进气质量流率。

外部依据：[NASA Orbital Mechanics Equations，圆轨道速度和周期](https://ntrs.nasa.gov/api/citations/19950006116/downloads/19950006116.pdf)。EP-VISTA 实现：[orbit.py](../src/ep_vista_core/orbit.py#L31-L45)。

### 3.2 J2 太阳同步倾角

程序令节点进动目标值为每个回归年 $360^\circ$：

$$
\dot\Omega_{\mathrm{target}}
=\frac{2\pi}{Y_{\mathrm{trop}}\,86400}.
$$

对于圆轨道，当前实现采用一阶 $J_2$ 节点进动关系：

$$
\dot\Omega
=-\frac{3}{2}J_2n\left(\frac{R_E}{r}\right)^2\cos i.
$$

从而得到界面显示的 SSO 倾角：

$$
i=\cos^{-1}\left[
-\frac{\dot\Omega_{\mathrm{target}}}
{1.5J_2n(R_E/r)^2}
\right].
$$

NASA资料给出了相同形式的圆轨道 $J_2$ 节点进动关系：[Introduction to Orbital Mechanics and Spacecraft Attitudes，Sun-Synchronous Orbit示例](https://ntrs.nasa.gov/api/citations/20205003902/downloads/Introduction%20to%20Orbital%20Mechanics%20and%20Spacecraft%20Attitudes%20for%20Thermal%20Engineers%20CHARTS%20PDF.pdf)。

当前实现把同一个平均半径 $R_E$ 同时用于轨道半径基准和 $J_2$ 项，而高精度任务设计通常需要明确参考椭球、引力场、历元和长期摄动模型。因此这里得到的是方案分析用倾角，不是高精度任务定轨结果。EP-VISTA 实现：[orbit.py](../src/ep_vista_core/orbit.py#L36-L45)。

### 3.3 沿轨道相位离散

若用户输入相位步长 $\Delta u$（rad），程序换算为：

$$
\Delta t=\frac{\Delta u}{n}.
$$

采样从 $t=0$ 开始，以 $\Delta t$ 递增；如果任务终点不落在规则网格上，程序额外加入准确的任务终点。默认项目步长为 $5^\circ$，约每圈72点；高度扫描快速预览为 $20^\circ$，约每圈18点。`batch_rows` 只改变 NRLMSIS 分批调用的内存和交互响应，不改变物理采样点。

EP-VISTA 实现：[orbit.py](../src/ep_vista_core/orbit.py#L94-L125)、[models.py](../src/ep_vista_core/models.py#L73-L76)、[高度扫描界面](../src/ep_vista_app/main_window.py#L889-L896)。

## 4. 太阳位置、LTAN和太阳翼迎风投影

### 4.1 太阳赤经和赤纬近似

程序首先由 Unix 时间得到儒略日和自 J2000.0 起的儒略世纪：

$$
JD=\frac{t_{\mathrm{Unix}}}{86400}+2440587.5,
\qquad
T_J=\frac{JD-2451545.0}{36525}.
$$

随后用低阶多项式计算太阳几何平黄经 $L_0$、平近点角 $M$、中心差 $C$、视黄经 $\lambda$ 和黄赤交角 $\epsilon$，再转换为赤经和赤纬：

$$
\alpha=\operatorname{atan2}(\cos\epsilon\sin\lambda,\cos\lambda),
\qquad
\delta=\sin^{-1}(\sin\epsilon\sin\lambda).
$$

源码中保留了所有多项式系数。该算法属于简化太阳位置近似，不调用 JPL 星历，也没有声称达到姿态定轨或高精度天文历表精度。通用太阳位置计算步骤可参考 [NOAA General Solar Position Calculations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF)；当前系数和运算顺序以 [orbit.py](../src/ep_vista_core/orbit.py#L48-L79) 为准。

### 4.2 LTAN、RAAN和节点进动

起始升交点赤经由输入 LTAN 与起始太阳赤经闭合：

$$
\Omega_0=\alpha_{\odot,0}+15^\circ(\mathrm{LTAN}-12).
$$

随后按恒定目标节点进动率推进：

$$
\Omega(t)=\Omega_0+\dot\Omega_{\mathrm{target}}t.
$$

界面可显示的当前 LTAN 为：

$$
\mathrm{LTAN}(t)=
\left[12+\frac{\Omega(t)-\alpha_\odot(t)}{15^\circ}\right]\bmod 24.
$$

这是 EP-VISTA 的解析闭合关系，不是对真实轨道摄动进行数值积分。太阳同步轨道的一般定义和快速设计背景见 [NASA NTRS: A-B-Cs of Sun-Synchronous Orbit Mission Design](https://ntrs.nasa.gov/citations/20210001902)。EP-VISTA 实现：[orbit.py](../src/ep_vista_core/orbit.py#L127-L171)。

### 4.3 地固经纬度与恒星时

程序用下式计算格林尼治平恒星时近似值（deg）：

$$
\theta_G=280.46061837
+360.98564736629(JD-2451545.0)
+0.000387933T_J^2
-\frac{T_J^3}{38710000}.
$$

然后绕地球自转轴把惯性坐标旋转到地固坐标，计算经纬度。类似的 GMST 表达及其时间尺度注意事项可参考 [Vallado等，Revisiting Spacetrack Report #3](https://celestrak.org/publications/AIAA/2006-6753/AIAA-2006-6753.pdf)。当前实现直接以 UTC 构造 $JD$，没有输入 UT1−UTC，也不包含极移；因此不是严格的 IAU/IERS 地球定向变换。

此外，程序的纬度由球形几何 $\sin^{-1}(z/r)$ 得到，属于球形地心纬度近似。EP-VISTA 实现：[orbit.py](../src/ep_vista_core/orbit.py#L82-L91)、[orbit.py](../src/ep_vista_core/orbit.py#L142-L161)。

### 4.4 β角和太阳翼迎风面积

设 $\hat{\mathbf n}_{\mathrm{orb}}$ 为轨道面单位法向，$\hat{\mathbf s}$ 为日心方向单位向量，则：

$$
\beta=\sin^{-1}(\hat{\mathbf n}_{\mathrm{orb}}\cdot\hat{\mathbf s}).
$$

程序假设太阳翼始终理想对日，其平面法向与 $\hat{\mathbf s}$ 一致。对速度方向的迎风投影系数为：

$$
f_{\mathrm{proj}}(t)=
\left|\hat{\mathbf v}(t)\cdot\hat{\mathbf s}(t)\right|,
$$

$$
A_{sa,\perp}(t)=A_{sa}f_{\mathrm{proj}}(t).
$$

这不是太阳翼姿态控制仿真，也不含遮挡、结构厚度、非理想指向或食期。EP-VISTA 实现：[orbit.py](../src/ep_vista_core/orbit.py#L162-L170)、[study.py](../src/ep_vista_core/study.py#L62-L64)。

## 5. 空间天气和 NRLMSIS 2.0

### 5.1 历史空间天气匹配

历史天气文件必须是连续3小时序列。对每个轨道采样 UTC，程序向下取整到对应的3小时 UTC 桶：

$$
t_{3h}=t-\left(t\bmod10800\right).
$$

程序按完全匹配的桶读取前一日 F10.7、中心81日平均 F10.7，以及以下七项 Ap：日平均、当前3小时、前3/6/9小时、前12–33小时八个3小时值的平均、前36–57小时八个3小时值的平均。程序不在相邻3小时记录之间插值；覆盖不足直接报错。

这些七项 Ap 的顺序与 pymsis 在 `geomagnetic_activity=-1` 时的接口定义一致，见 [pymsis 0.12.0 calculate API](https://swxtrec.github.io/pymsis/reference/generated/pymsis.msis.calculate.html)。随附天气快照来自 [CelesTrak Space Weather Data](https://celestrak.org/SpaceData/)，字段说明见 [CelesTrak Space Weather Format](https://celestrak.org/SpaceData/SpaceWx-format.php)，本地来源和哈希另见 [DATA_SOURCES.md](DATA_SOURCES.md)。EP-VISTA 实现：[weather.py](../src/ep_vista_core/weather.py#L18-L26)、[weather.py](../src/ep_vista_core/weather.py#L98-L138)。

### 5.2 固定活动情景

固定情景不是预报，而是把任务所有采样点设置为常量：

| 情景 | F10.7前一日 | F10.7中心81日均值 | 七项Ap |
|---|---:|---:|---:|
| low | 70 | 70 | 全部为4 |
| nominal | 150 | 150 | 全部为15 |
| high | 220 | 220 | 全部为50 |

这些数值是 EP-VISTA 的敏感性情景设定，不应表述为 NRLMSIS 官方活动等级定义，也没有概率或重现期含义。EP-VISTA 实现：[weather.py](../src/ep_vista_core/weather.py#L28-L32)、[weather.py](../src/ep_vista_core/weather.py#L141-L150)。

### 5.3 NRLMSIS调用和输出

程序固定要求 pymsis 0.12.0，并显式调用 `version=2.0`、`geomagnetic_activity=-1`。每个轨道采样点输入：

- UTC；
- 经度（deg）；
- 纬度（deg）；
- 高度（km）；
- 前一日 F10.7；
- 中心81日平均 F10.7；
- 七项 Ap。

NRLMSIS 2.0是温度、中性组分数密度和总质量密度的经验模型，其模型性质、输入驱动和验证范围应引用原论文：[Emmert et al., NRLMSIS 2.0, DOI 10.1029/2020EA001321](https://doi.org/10.1029/2020EA001321)。pymsis的输入排列、返回量和单位应引用 [pymsis 0.12.0 API](https://swxtrec.github.io/pymsis/reference/generated/pymsis.msis.calculate.html)。

EP-VISTA保存以下输出：

| 输出 | 单位 |
|---|---|
| 总质量密度 | kg/m³ |
| N₂、O₂、O、He、H、Ar、N、异常O数密度 | m⁻³ |
| 温度 | K |

NRLMSIS 2.0不提供2.1版新增的NO有效输出，因此程序允许返回数组中的NO位置为非有限值，但要求上述实际使用量为有限且非负。

重要坐标边界：pymsis接口文档将经纬度和高度定义为WGS84大地坐标；EP-VISTA当前轨道模块却用球形地球得到地心经纬度和相对平均半径的高度，然后直接传入pymsis。当前文档将此明确标为坐标近似，尚未证明它对150–300 km结果的影响可以忽略。EP-VISTA 实现：[atmosphere.py](../src/ep_vista_core/atmosphere.py#L21-L75)、[orbit.py](../src/ep_vista_core/orbit.py#L157-L161)。

## 6. 太阳翼、本体阻力和总冲量

### 6.1 动压和分项阻力

每个采样点的动压为：

$$
q(t)=\frac12\rho(t)v(t)^2.
$$

整星阻力把本体和太阳翼按各自阻力系数相加：

$$
D(t)=q(t)\left[C_{D,b}A_b+C_{D,sa}A_{sa,\perp}(t)\right].
$$

源码把牛顿换算为毫牛后用于界面和推进比较：

$$
D_{\mathrm{mN}}(t)=1000D(t).
$$

通用阻力方程可参考 [NASA Glenn Drag Equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-coefficient/)。NASA资料只说明通用关系，并不为本程序输入的固定 $C_D$、自由分子流适用性或太阳翼投影假设背书。

程序另外保存 $A_b+A_{sa,\perp}$ 作为“有效迎风面积”显示量，但实际阻力始终使用上式两个 $C_DA$ 项，不用单一等效阻力系数。EP-VISTA 实现：[study.py](../src/ep_vista_core/study.py#L62-L70)。

### 6.2 速度口径

$v$ 使用圆轨道惯性速度。模型没有计算相对大气速度：

$$
\mathbf v_{\mathrm{rel}}
\ne
\mathbf v_{\mathrm{orbit}}-\boldsymbol\omega_E\times\mathbf r-\mathbf v_{\mathrm{wind}}
$$

在当前实现中，上式右侧的地球共转和风场项均未加入。因此阻力和 ABEP 进气量都是基于惯性圆轨道速度的方案近似。

### 6.3 平均阻力、最大阻力和总冲量

任务全程平均阻力采用时间加权平均：

$$
\bar D=\frac{1}{t_f-t_0}\int_{t_0}^{t_f}D(t)\,dt.
$$

“最大阻力”是所有离散任务采样点中的最大值：

$$
D_{\max}=\max_jD(t_j).
$$

总冲量为：

$$
I_{\mathrm{tot}}=\int_{t_0}^{t_f}D(t)\,dt.
$$

程序使用复合梯形规则 `numpy.trapezoid`，并按采样点实际时间间隔积分。数值方法见 [NumPy `trapezoid` 文档](https://numpy.org/doc/stable/reference/generated/numpy.trapezoid.html)。EP-VISTA 实现：[study.py](../src/ep_vista_core/study.py#L65-L70)、[models.py](../src/ep_vista_core/models.py#L354-L363)。

## 7. 推进器输入一致性和功率限制推力

### 7.1 推功比和功率工作点

设用户配置的电推进功率为 $P_{EP}$，设备最大工作功率为 $P_{\max}$。当前工作功率为：

$$
P_{\mathrm{op}}=
\begin{cases}
\min(P_{EP},P_{\max}), & P_{\max}\text{已给定},\\
P_{EP}, & P_{\max}\text{为空}.
\end{cases}
$$

功率限制推力为：

$$
T_{\mathrm{power,mN}}=P_{\mathrm{op,kW}}k_{TP,\mathrm{mN/kW}}.
$$

若 $P_{\mathrm{op}}<P_{\min}$，可用推力序列直接置零，状态为推力不足。程序不对功率—推力曲线插值，也不模拟节流效率变化；一个候选方案只有一个恒定推功比。

EP-VISTA 实现：[propulsion.py](../src/ep_vista_core/propulsion.py#L23-L40)。

### 7.2 由推功比和比冲反推效率

采用理想喷流关系 $T=\dot m v_e$、$v_e=I_{sp}g_0$ 和喷流动能功率 $P_{jet}=\dot m v_e^2/2$，可得：

$$
\eta=\frac{P_{jet}}{P}
=\frac{T}{P}\frac{I_{sp}g_0}{2}.
$$

由于输入推功比单位是mN/kW，换成N/W需乘 $10^{-6}$：

$$
\eta=10^{-6}k_{TP}I_{sp}g_0/2.
$$

程序要求 $0<\eta\le1$，否则认为推功比与比冲不一致。这里的 $\eta$ 是由两个输入反推的总体能量一致性指标，不是独立测量的推进器效率，也不分解束流、阳极、PPU或羽流损失。电推进基本推力、比冲和功率关系可参考 [JPL, Fundamentals of Electric Propulsion](https://descanso.jpl.nasa.gov/SciTechBook/series4/Electric_Propulsion_2nd_edition.pdf)。EP-VISTA 实现：[models.py](../src/ep_vista_core/models.py#L286-L303)。

## 8. ABEP集气与实际可用推力

当前模型把卫星本体迎风面积直接作为进气面积（即认为卫星本体迎风面积小于等于集气器迎风面积）：

$$
A_{\mathrm{intake}}=A_b.
$$

捕获质量流率采用：

$$
\dot m_{\mathrm{cap}}(t)
=\eta_c\rho(t)v(t)A_{\mathrm{intake}}.
$$

由比冲得到进气限制推力：

$$
T_{\mathrm{intake}}(t)
=\dot m_{\mathrm{cap}}(t)I_{sp}g_0.
$$

最终可用推力逐点取功率限制和进气限制的较小值：

$$
T_{\mathrm{avail}}(t)
=\min\left[T_{\mathrm{power}},T_{\mathrm{intake}}(t)\right].
$$

ABEP系统中自由来流质量流率和集气效率的定义可参考 [Parodi et al., On the critical parameters for feasibility and advantage of air-breathing electric propulsion systems, DOI 10.1016/j.actaastro.2024.04.042](https://doi.org/10.1016/j.actaastro.2024.04.042)。该论文是通用外部依据；EP-VISTA没有实现论文中的全部面积效率、推进效率、流动压缩或进气道模型。

当前 $\eta_c$ 是一个恒定总体系数，不随组分、温度、姿态、攻角、稀薄流状态或进气道几何改变；程序也不计算压缩比、回流、离化率和推进器内部质量利用率。EP-VISTA 实现：[propulsion.py](../src/ep_vista_core/propulsion.py#L41-L53)、[study.py](../src/ep_vista_core/study.py#L78-L79)。

## 9. 逐圈平均判据与推进指标

### 9.1 圈界和逐圈时间平均

程序用未折返轨道相位 $u(t)$ 的每个 $360^\circ$ 交点定义圈界，并对交点时间作线性插值。对于第 $k$ 圈或末尾不足一圈的区间 $[t_k,t_{k+1}]$，任意量 $x(t)$ 的逐圈平均为：

$$
\bar x_k=
\frac{1}{t_{k+1}-t_k}
\int_{t_k}^{t_{k+1}}x(t)\,dt.
$$

积分使用包含插值圈界的复合梯形规则。末尾不足一整圈仍按实际时段形成一个统计区间。EP-VISTA 实现：[orbit_statistics.py](../src/ep_vista_core/orbit_statistics.py#L33-L63)。

### 9.2 “满足任务”判据

对于任务中的每一个完整或部分圈段，必须同时满足：

$$
\bar T_{\mathrm{avail},k}>\bar D_k.
$$

等号不算满足。程序还独立检查推进器最小工作功率、整星供电功率以及输入数据有效性。这个严格大于的逐圈平均规则是 EP-VISTA 的方案判据 `per_orbit_time_mean_strict_gt_v1`，不是外部标准，也不保证每个瞬时点定高。

如果圈内出现 $T_{\mathrm{avail}}(t)<D(t)$，程序不会传播由此产生的速度和高度偏差；后续高阻力区也不会因轨道已经下降而改变密度。因此“满足任务”只表示通过当前平均补偿筛选。

EP-VISTA 实现：[orbit_statistics.py](../src/ep_vista_core/orbit_statistics.py#L17-L21)、[propulsion.py](../src/ep_vista_core/propulsion.py#L85-L115)。

### 9.3 推进系统最低功率

界面中的“推进系统最低功率”定义为：

$$
P_{\mathrm{req,theory}}
=\frac{\max_k(\bar D_k)}{k_{TP}}.
$$

这是只由逐圈平均阻力最大值和推功比得到的理论阈值。严格大于判据意味着实际功率必须高于该值；它不是设备自身最小工作功率，并且没有纳入最大工作功率、ABEP进气限制、供电缺口或功率裕量。

EP-VISTA 实现：[propulsion.py](../src/ep_vista_core/propulsion.py#L85-L90)。

### 9.4 两种容易混淆的推力指标

| 指标 | 当前定义 | 是否作为任务通过判据 |
|---|---|---|
| 最小逐圈平均推力裕度 | $\min_k(\bar T_{\mathrm{avail},k}-\bar D_k)$ | 是，必须严格大于0 |
| 极限/最小瞬时推力余量 | $\min_j[T_{\mathrm{avail}}(t_j)-D(t_j)]$ | 否，仅描述离散采样点最差瞬时差值 |
| 可用推力 | $\min_jT_{\mathrm{avail}}(t_j)$ | 否，是任务采样点中的最小可用推力 |

为了避免零阻力造成数值问题，瞬时裕度计算内部把阻力下限设为机器最小正有限量；在正常正阻力算例中这不改变物理结果。EP-VISTA 实现：[propulsion.py](../src/ep_vista_core/propulsion.py#L88-L91)、[propulsion.py](../src/ep_vista_core/propulsion.py#L117-L138)。

## 10. 总冲量与推进剂质量

传统携带工质方案的推进剂质量按理想恒定比冲关系计算：

$$
m_p=\frac{I_{\mathrm{tot}}}{I_{sp}g_0}.
$$

这等价于对完成阻力补偿所需质量流率积分，但没有加入储备系数、启动/关机消耗、泄漏、剩余量、效率随工况变化或储箱排空限制。若当前推进方案不能满足任务，程序仍可能显示这个条件性理论推进剂估算。

ABEP方案的 `propellant_kg` 固定为0，含义是“不携带任务推进剂”，不是大气质量流率为0，也不是进气装置和推进单元质量为0。外部电推进关系参考 [JPL, Fundamentals of Electric Propulsion](https://descanso.jpl.nasa.gov/SciTechBook/series4/Electric_Propulsion_2nd_edition.pdf)。EP-VISTA 实现：[propulsion.py](../src/ep_vista_core/propulsion.py#L117-L122)。

## 11. 供电闭合关系

本节全部是 EP-VISTA 当前线性方案闭合关系，不代表完整EPS设计标准。

### 11.1 太阳翼面积和发电功率

太阳翼自动定面积只在供电方式为“太阳翼”且面积模式为自动时启用：

$$
A_{sa}=\frac{1000P_{\mathrm{total,kW}}}{p_{A,\mathrm{W/m^2}}}.
$$

固定硬件模式直接使用输入面积。发电功率为：

$$
P_{sa,\mathrm{kW}}=\frac{A_{sa}p_A}{1000}.
$$

该功率被视为任务全程恒定可用；太阳翼迎风投影变化只影响阻力，不影响发电功率。EP-VISTA 实现：[models.py](../src/ep_vista_core/models.py#L47-L63)、[budgets.py](../src/ep_vista_core/budgets.py#L18-L23)。

### 11.2 电池补充功率和配置电量

太阳翼相对整星恒定负载的功率缺口为：

$$
P_{\mathrm{def}}=\max(P_{\mathrm{total}}-P_{sa},0).
$$

只有“电池供电”模式才把该缺口作为电池需求；“太阳翼供电”模式不使用电池补充。电池实际配置供电功率受输入上限约束：

$$
P_{bat,\mathrm{sup}}=\min(P_{\mathrm{def}},P_{bat,\max}).
$$

$$
P_{\mathrm{gap}}=\max(P_{\mathrm{def}}-P_{bat,\mathrm{sup}},0).
$$

任务时长为 $t_{\mathrm{mission,h}}$ 时：

$$
E_{bat,\mathrm{config}}=P_{bat,\mathrm{sup}}t_{\mathrm{mission,h}}.
$$

如果电池输出上限小于缺口，配置电量只按实际受限供电功率计算，所以显示的电池质量不是“完全补足整星需求所需质量”；同时程序将供电状态标为不足，并把候选方案总状态覆盖为供电功率不足。

EP-VISTA 实现：[budgets.py](../src/ep_vista_core/budgets.py#L20-L50)、[study.py](../src/ep_vista_core/study.py#L204-L219)。

### 11.3 太阳翼和电池质量

设太阳翼系统比功率为 $p_m$（W/kg），电池系统可用比能量为 $e_{bat}$（kWh/kg）：

$$
m_{sa}=\frac{1000P_{sa}}{p_m},
$$

$$
m_{bat}=\frac{E_{bat,\mathrm{config}}}{e_{bat}}.
$$

这里的输入必须是系统级可用口径，否则容易漏计结构、调节与配电部件。模型不含食期、充电循环、放电深度的独立变量、退化、温度、冗余和设计裕量；这些影响只能由用户预先折算进输入比功率或可用比能量。

EP-VISTA 实现：[budgets.py](../src/ep_vista_core/budgets.py#L26-L33)。

## 12. 任务初始质量

每个候选方案的任务初始总质量按六项直接相加：

$$
m_0=m_{structure}+m_{sa}+m_{bat}+m_{propulsion}+m_p+m_{payload}.
$$

任一组成未知（空值）时，总质量返回未知；输入0表示明确不计入，与未知不同。推进剂质量包含当前任务时域内的全部理论携带推进剂，因此这是任务初始质量，不是任务末期质量。

质量不反向耦合到阻力、轨道或推进剂需求。对于给定几何、$C_D$、高度和天气，改变结构质量或载荷质量不会改变 $D(t)$、$I_{\mathrm{tot}}$ 或 $m_p$。模型也没有核对推进单元结构质量是否已经包含PPU、进气装置、储箱或其他配套部件。

EP-VISTA 实现：[budgets.py](../src/ep_vista_core/budgets.py#L63-L92)。

## 13. 高度扫描

高度序列按用户输入的最低高度、最高高度和间隔生成，并尽量包含终点：

$$
h_j=h_{\min}+j\Delta h,
\qquad h_j\le h_{\max}+0.5\Delta h.
$$

每个高度都复制同一任务配置，只替换高度，然后针对一个候选方案重新运行完整轨道—大气—阻力—推进—供电—质量链。高度扫描输出：

- 任务全程时间平均阻力；
- 离散采样点最大阻力；
- 总冲量；
- 传统方案理论推进剂质量或ABEP的0携带推进剂值；
- 最小瞬时推力余量。

扫描点之间不插值，不传播同一卫星的自然升降，也不计算高度变化过程中的控制量。快速预览和详细计算只改变沿轨道相位步长；正式使用需通过缩小 $\Delta u$ 检查结果收敛。

EP-VISTA 实现：[sensitivity.py](../src/ep_vista_core/sensitivity.py)、[高度扫描界面](../src/ep_vista_app/main_window.py#L1727-L1823)。

## 14. 数值方法、缓存与可重复性

- 连续物理量只在离散轨道相位点求值。
- 任务终点和逐圈边界通过显式加入或线性插值保留。
- 平均值和总冲量使用复合梯形积分；来源见 [NumPy `trapezoid`](https://numpy.org/doc/stable/reference/generated/numpy.trapezoid.html)。
- NRLMSIS分批大小只影响内存占用、取消响应和进度显示，不改变输入采样点。
- 轨道—大气—阻力结果可缓存；缓存键包含任务、几何、大气和物理采样配置，不包含仅影响批处理的 `batch_rows`。
- 修改输入后必须重新计算；界面旧结果和高度扫描使用上次计算时冻结的输入快照。

现有自动测试覆盖部分数据、界面、项目快照和运行路径，但自动测试通过不等于外部物理验证、模型不确定度评估或跨平台认证。发布前仍需分别执行公式级单元测试、采样收敛检查、独立软件/手算对照和具有来源的基准算例。相关边界见 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)。

## 15. 指标定义速查

| 界面/结果指标 | 计算定义 | 主要限制 |
|---|---|---|
| SSO倾角 | 一阶 $J_2$ 节点进动匹配回归年 | 不是高精度定轨 |
| 轨道周期 | $2\pi\sqrt{r^3/\mu_E}$ | 球形二体圆轨道 |
| 密度范围 | NRLMSIS离散采样点总质量密度最小值至最大值 | 不是连续包络或不确定区间 |
| 平均阻力 | 全任务阻力时间积分除以任务时长 | 取决于采样收敛性 |
| 最大阻力 | 离散任务采样点最大值 | 可能漏过点间峰值 |
| 总冲量 | 阻力对时间的梯形积分 | 假设需求等于阻力补偿 |
| 推进系统最低功率 | 最大逐圈平均阻力除以推功比 | 不含ABEP进气和设备限制 |
| 可用推力 | 任务离散点的最小可用推力 | 不是平均推力 |
| 最小逐圈平均裕度 | $\min_k(\bar T_k-\bar D_k)$ | 当前任务通过依据 |
| 极限瞬时推力余量 | $\min_j(T_j-D_j)$ | 不是任务通过依据 |
| 推进剂质量 | $I_{tot}/(I_{sp}g_0)$；ABEP记0携带量 | 无储备、启动和退化 |
| 太阳翼质量 | $1000P_{sa}/p_m$ | 线性系统比功率闭合 |
| 电池配置电量 | 受限补充功率×任务时长 | 不含食期和循环 |
| 电池质量 | 配置电量/系统可用比能量 | 供电不足时不是补足需求质量 |
| 初始总质量 | 六项已知质量之和 | 任一项未知则总量未知 |
| 满足任务 | 每圈平均可用推力严格大于平均阻力，且供电/工作范围有效 | 不保证瞬时定高 |

## 16. 明确未建模的能力

以下项目当前没有计算公式或求解器，不能从现有输出推断：

- 轨道下降、再升轨和圈内高度波动；
- 真实控制律、推力器开关机、节流曲线和控制裕量；
- 地球大气共转、风场和高保真自由分子气动；
- 太阳翼姿态动力学、遮挡、食期和发电退化；
- 电池充放电循环、SOC、温度、寿命和冗余；
- ABEP进气道几何、压缩比、回流、组分选择、离化和内部损失；
- PPU、热控、储箱、进气装置等完整分系统质量闭合；
- 推进器侵蚀、可靠度、失效率和寿命认证；
- NRLMSIS、空间天气、$C_D$、推进器性能和质量输入的不确定度传播；
- 多目标优化、统计置信区间或自动设备排名。

## 17. 外部资料与链接

以下资料是本文档实际使用的外部依据；访问日期为2026-09-01。若使用EP-VISTA的计算结果发表科研成果时，仍应根据实际使用内容核对原文并采用目标期刊要求的正式参考文献格式。

1. NASA, *Orbital Mechanics Equations*, circular-orbit velocity and period: <https://ntrs.nasa.gov/api/citations/19950006116/downloads/19950006116.pdf>
2. NASA, *Introduction to Orbital Mechanics and Spacecraft Attitudes for Thermal Engineers*, J2 sun-synchronous example: <https://ntrs.nasa.gov/api/citations/20205003902/downloads/Introduction%20to%20Orbital%20Mechanics%20and%20Spacecraft%20Attitudes%20for%20Thermal%20Engineers%20CHARTS%20PDF.pdf>
3. NASA NTRS, Boain, *A-B-Cs of Sun-Synchronous Orbit Mission Design*: <https://ntrs.nasa.gov/citations/20210001902>
4. NOAA Global Monitoring Laboratory, *General Solar Position Calculations*: <https://gml.noaa.gov/grad/solcalc/solareqns.PDF>
5. Vallado et al., *Revisiting Spacetrack Report #3*, GMST expression and time-scale discussion: <https://celestrak.org/publications/AIAA/2006-6753/AIAA-2006-6753.pdf>
6. Emmert et al., *NRLMSIS 2.0: A Whole-Atmosphere Empirical Model of Temperature and Neutral Species Densities*, DOI: <https://doi.org/10.1029/2020EA001321>
7. pymsis 0.12.0, `calculate` API, inputs and output units: <https://swxtrec.github.io/pymsis/reference/generated/pymsis.msis.calculate.html>
8. CelesTrak, Space Weather Data and format: <https://celestrak.org/SpaceData/>；<https://celestrak.org/SpaceData/SpaceWx-format.php>
9. NASA Glenn Research Center, drag equation and drag coefficient: <https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-coefficient/>
10. Goebel and Katz, JPL, *Fundamentals of Electric Propulsion*, second edition: <https://descanso.jpl.nasa.gov/SciTechBook/series4/Electric_Propulsion_2nd_edition.pdf>
11. Parodi et al., *On the critical parameters for feasibility and advantage of air-breathing electric propulsion systems*, DOI: <https://doi.org/10.1016/j.actaastro.2024.04.042>
12. BIPM/JCGM, standard acceleration of free fall: <https://jcgm.bipm.org/vim/en/2.12.html>
13. NumPy, `numpy.trapezoid`: <https://numpy.org/doc/stable/reference/generated/numpy.trapezoid.html>

## 18. 维护要求

修改任何计算公式、常数、变量定义、第三方模型版本、输出口径或判据时，应同时更新：

- 本文档的公式、边界与源码链接；
- [USER_GUIDE.md](USER_GUIDE.md)中的用户口径；
- [DATA_GUIDE.md](DATA_GUIDE.md)中的字段和单位；
- [DATA_SOURCES.md](DATA_SOURCES.md)中的来源与核验状态；
- 对应的公式级测试、数值基线和发布检查记录。

文档更新不能替代代码验证；代码测试通过也不能替代外部资料核对和物理适用性判断。

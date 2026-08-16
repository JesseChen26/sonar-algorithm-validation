# NOAA ME70 `.raw` 完整声学物理量解析说明

## 1. 当前数据与已完成工作

### 数据来源

- 数据集：NOAA NCEI Water Column Sonar Data Archive，PC1902 ME70
- DOI：https://doi.org/10.25921/tctw-am57
- 本地文件：`D:\C#\水声算法\real_noaa_wcsd\PC1902_ME70\PC_2019_-D20190613-T030352.raw`
- 文件大小：约 `2.99 MB`
- 仪器类型：Kongsberg/Simrad ME70 `.raw`

NOAA README 说明 Kongsberg/Simrad `.raw` 文件由 ME70、EK60、EK80 或 ES60 等仪器生成，包含 power，并可选包含 angular position data；每个 beam/frequency 由独立 channel 标识。

### 已完成

当前已完成的是**结构级解析**：

- 读取 `.raw` 二进制文件；
- 识别 Kongsberg/Simrad datagram framing；
- 统计 datagram 类型；
- 提取 `RAW0` payload；
- 生成 RAW payload 字节级和 int16-log echogram 预览图。

当前解析结果：

| Datagram | 数量 | 作用 |
|---|---:|---|
| `CON0` | 1 | 配置记录 |
| `CON1` | 1 | 配置/通道相关记录 |
| `NME0` | 31 | NMEA 导航/定位文本记录 |
| `RAW0` | 231 | 声学原始数据记录 |

当前结果能够证明：真实 NOAA ME70 `.raw` 文件下载正确，文件内存在有效的声学 `RAW0` 记录，并且 payload 中有明显的多束/多通道回波结构。

## 2. 完整声学物理量解析目标

完整解析的目标不是只画 payload 预览图，而是从原始 `.raw` 文件得到工程可解释的声学量：

| 输出物理量 | 含义 | 单位/表达 |
|---|---|---|
| `echo_range` | 每个采样点对应的距离 | m |
| `power` | 原始接收功率或厂商编码 power | counts 或 dB-like |
| `angle_alongship` | 沿船方向相位角/角度 | deg 或 counts 转换值 |
| `angle_athwartship` | 横船方向相位角/角度 | deg 或 counts 转换值 |
| `Sv` | 体积后向散射强度 | dB re 1 m^-1 |
| `TS` | 目标强度 | dB re 1 m^2 |
| `MVBS` | 平均体积后向散射强度 | dB |
| `bottom_range` | 海底/底线距离 | m |
| `navigation` | 时间、经纬度、航速、航向 | UTC, deg, kn, deg |

## 3. 完整解析流程

### 3.1 Datagram framing

Kongsberg/Simrad `.raw` 文件通常由连续 datagram 组成。每个 datagram 需要解析：

1. datagram 长度；
2. datagram 类型，例如 `CON0`、`NME0`、`RAW0`；
3. 时间戳；
4. payload；
5. 末尾重复长度或校验长度。

当前已经完成这一步。

### 3.2 配置记录解析：`CON0/CON1`

完整物理量解析必须从配置记录中提取：

- channel 数量；
- channel ID；
- transducer name；
- frequency；
- beam type；
- gain；
- equivalent beam angle；
- angle sensitivity；
- angle offset；
- pulse length；
- transmit power；
- bandwidth；
- sample interval；
- sound speed；
- transceiver/channel 映射关系。

这些字段决定了后续 power 到 `Sv/TS` 的标定是否可信。

当前没有完整解析 `CON0/CON1` 的字段，只统计了记录类型和 payload 结构。

### 3.3 导航记录解析：`NME0`

`NME0` 通常包含 NMEA 文本，例如：

- `$GPGGA`：定位、UTC、经纬度、高程；
- `$GPRMC`：时间、经纬度、航速、航向；
- `$GPHDT` / `$HEHDT`：航向；
- 其他厂商或船载导航句子。

完整解析应输出：

- ping 时间；
- latitude；
- longitude；
- heading；
- speed over ground；
- course over ground；
- 导航记录与声学 ping 的时间同步关系。

当前尚未解析 NMEA 文本，也未完成 ping 与导航插值匹配。

### 3.4 声学记录解析：`RAW0`

完整 `RAW0` 解析需要得到：

- channel ID；
- ping 时间；
- transmit mode；
- sample count；
- sample interval；
- power samples；
- optional angle samples；
- beam/frequency/channel 对应关系。

当前只把 `RAW0` payload 当作字节流/int16 流预览，没有按照厂商字段完整拆解。

### 3.5 距离轴计算：`echo_range`

每个采样点对应的距离一般按双程传播时间计算：

```text
echo_range[i] = sound_speed * sample_interval * i / 2
```

实际工程中还需要考虑：

- transmit pulse length；
- transducer draft / installation depth；
- sample offset；
- blanking range；
- sound speed profile；
- heave/pitch/roll correction；
- 每个 channel 的采样率与起始样点。

当前结果图横轴仍是 `payload/sample index`，不是严格 `echo_range (m)`。

### 3.6 Power 转换

厂商 `.raw` 中的 power samples 不是最终物理量。完整解析需要根据 RAW 格式规范把编码值转换为接收功率或等效 dB 值。

需要确认：

- power sample 的数据类型；
- 是否为 int16 编码；
- scale factor；
- offset；
- power 与 electrical received level 的关系；
- 是否包含 angle pairs；
- 是否是 EK60-like narrowband power/angle 格式。

当前只做了 `int16-log` 可视化，不能把灰度值解释成真实接收功率。

### 3.7 环境参数

计算 `Sv/TS` 需要环境参数：

- temperature；
- salinity；
- pressure/depth；
- sound speed；
- absorption coefficient；
- pH（如果吸收模型需要）；
- frequency dependent absorption。

Echopype 文档说明，标定时需要 calibration parameters 和 environmental parameters；声速影响 echo range，吸收系数影响传播损失补偿。

当前没有从 `.raw` 或外部环境文件中提取/设定温盐深参数，也没有计算吸收系数。

### 3.8 标定参数

完整 `Sv/TS` 计算需要仪器标定参数，例如：

- gain correction；
- equivalent beam angle；
- sa correction；
- angle offset alongship；
- angle offset athwartship；
- angle sensitivity alongship；
- angle sensitivity athwartship；
- transducer impedance / frequency response；
- transmit power；
- pulse duration；
- bandwidth。

Echopype 文档中，EK60/EK80 类数据的 `compute_Sv` 支持通过 `cal_params` 覆盖 `sa_correction`、`gain_correction`、`equivalent_beam_angle` 等参数。

当前没有解析或外部补充这些标定参数，因此不能输出可靠的 calibrated `Sv/TS`。

### 3.9 `Sv` 计算逻辑

`Sv` 是体积后向散射强度，工程上通常由原始 power、距离补偿、吸收补偿和仪器标定项共同计算。

概念上包含：

```text
Sv = received_power_term
     + spreading_loss_compensation
     + absorption_compensation
     - transmit_and_transducer_terms
     - pulse_volume_term
     + calibration_corrections
```

常见补偿项包括：

- `20 log10(range)` 或与厂商定义一致的传播扩展补偿；
- `2 * absorption * range` 双程吸收补偿；
- pulse duration / sample volume；
- equivalent beam angle；
- gain correction；
- sa correction。

注意：不同仪器、宽带/窄带、power/complex 编码模式下公式细节不同，应以厂商 RAW 规范或 Echopype 对应 sonar model 的实现为准。

当前没有完成这一步。

### 3.10 `TS` 计算逻辑

`TS` 是目标强度，常用于单体目标或点目标回波分析。Echopype 文档说明，`TS = 10 * log10(sigma_bs)`，其中 `sigma_bs` 是 backscattering cross-section。

完整 TS 计算需要：

- 单体目标检测；
- echo integration 或 peak picking；
- 距离补偿；
- 吸收补偿；
- transducer gain；
- beam angle correction；
- pulse duration / matched filter 处理；
- 目标是否位于主瓣中心的修正。

当前没有完成单体目标提取或 TS 标定。

### 3.11 MVBS 与降采样

`MVBS` 是 mean volume backscattering strength，通常用于把高分辨率 `Sv` 按时间/距离窗口平均，降低噪声并用于生态/水柱统计。

完整流程：

1. 得到 calibrated `Sv`；
2. 转为线性域；
3. 按 ping bin 和 range bin 平均；
4. 再转回 dB；
5. 输出 MVBS echogram。

当前没有完成 MVBS。

### 3.12 底检测与水柱分析

完整真实数据分析还应包括：

- bottom detection；
- surface/bubble/noise masking；
- seabed line removal；
- water column target layer extraction；
- school/patch detection；
- 多频率或多 beam 对比；
- ping-to-ping 稳定性分析。

当前仅在仿真数据中做了底线检测和斜距校正，尚未对 NOAA ME70 真实 raw 数据做物理距离轴上的底检测。

## 4. 当前没有分析全的地方

### A. RAW 格式字段没有完整解析

当前只解析 datagram 外层结构，未完整解析 `CON0/CON1/RAW0` 的字段含义。

缺失项：

- channel ID；
- frequency；
- beam/channel 映射；
- sample count；
- sample interval；
- power/angle 编码方式；
- transmit power；
- pulse length；
- gain；
- equivalent beam angle。

### B. 没有 calibrated `Sv`

当前图像不是 `Sv echogram`。  
缺失项：

- power scale；
- sound speed；
- absorption；
- gain correction；
- equivalent beam angle；
- sa correction；
- range compensation；
- pulse volume correction。

### C. 没有 `TS`

当前没有目标检测和单体目标标定。  
缺失项：

- 单体目标候选提取；
- beam angle correction；
- echo peak / echo integration；
- target strength equation；
- 与目标真值或人工标注对比。

### D. 没有真实距离轴

当前横轴是 payload/sample index。  
缺失项：

- sample interval；
- sound speed；
- range offset；
- transducer draft；
- ping/channel 对齐。

### E. 没有导航同步

当前识别了 `NME0` 数量，但没有解析 NMEA。  
缺失项：

- UTC；
- latitude/longitude；
- heading；
- speed；
- ping time interpolation；
- 航迹图。

### F. 没有多 beam/channel 分离

ME70 是多 beam / 多 channel 数据。当前 payload 预览没有把不同 beam/channel 拆开。  
缺失项：

- channel list；
- 每个 channel 的独立 echogram；
- beam angle 信息；
- beam-to-beam backscatter 对比。

### G. 没有噪声处理

完整水柱处理需要：

- background noise estimation；
- impulse noise removal；
- surface noise mask；
- bottom mask；
- false echo removal。

当前未做真实数据噪声处理。

### H. 没有与成熟工具交叉验证

完整工程验证应使用 Echopype、Echoview 或厂商软件做对照。  
缺失项：

- Echopype `open_raw` / `compute_Sv` 结果；
- Echoview ECS 标定文件；
- 与软件输出 Sv echogram 的差异对比；
- 参数表一致性检查。

## 5. 推荐下一步实现路线

### 路线 1：使用 Echopype 快速得到 `Sv`

如果环境允许安装 Echopype，可优先尝试：

```python
import echopype as ep

ed = ep.open_raw(
    r"D:\C#\水声算法\real_noaa_wcsd\PC1902_ME70\PC_2019_-D20190613-T030352.raw",
    sonar_model="EK60"
)

ds_Sv = ep.calibrate.compute_Sv(ed)
```

注意：ME70 文件是否能直接按 `EK60` 或其他 model 打开，需要实测确认。若 Echopype 不支持该 ME70 变体，需要改用厂商规范或其他库。

### 路线 2：手写 RAW0 字段解析

1. 完整解析 `CON0/CON1`；
2. 建立 channel table；
3. 解析每个 `RAW0` 的 channel ID、mode、sample count、power/angle；
4. 按 channel 组装 `ping × range` 数据矩阵；
5. 根据 sample interval 和 sound speed 计算 `echo_range`；
6. 加入环境参数和标定参数；
7. 实现 `Sv/TS` 转换；
8. 输出 per-channel echogram、bottom line 和统计图。

### 路线 3：真实数据 + 仿真算法结合

当前最稳妥的简历项目结构是：

- 真实 NOAA ME70 `.raw`：证明会下载、读取、解析真实声呐数据结构；
- 自建仿真数据：证明会做波束形成、CFAR、斜距校正和误差分析；
- 后续计划：补齐完整 Sv/TS 标定和真实数据上的检测/底线分析。

## 6. 简历中的稳妥表述

推荐写：

> 基于 NOAA 公开 ME70 水柱声呐原始 `.raw` 数据，完成 Kongsberg/Simrad RAW datagram 结构解析，识别 `CON/NMEA/RAW` 等记录类型并生成真实 RAW payload 回波结构预览图；同时构建可控多波束仿真数据，实现 delay-and-sum 波束形成、二维 CFAR 检测、底线检测和斜距校正，并基于真值评估距离/角度误差及参数敏感性。

不建议写：

> 已完成 ME70 声呐数据的完整 Sv/TS 标定解析。

因为当前还没有完成完整标定参数解析、环境参数补偿和物理量转换。

## 7. 参考资料

- NOAA NCEI Water Column Sonar Data Archive: https://www.ncei.noaa.gov/products/water-column-sonar-data
- NOAA PC1902 ME70 DOI: https://doi.org/10.25921/tctw-am57
- NOAA metadata/instrument说明中指出 Simrad `.raw` 包含 power 和可选 angular position data，并由独立 channel 标识 beam/frequency。
- Echopype calibration docs: https://echopype.readthedocs.io/en/latest/data-proc-func.html
- Echopype TS docs: https://echopype.readthedocs.io/en/v0.6.3/api/echopype.calibrate.compute_TS.html

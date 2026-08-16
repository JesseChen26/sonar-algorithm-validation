# NOAA PC1902 ME70 真实水柱声呐数据解析报告

## 数据来源

- 数据集：ME70 Water Column Sonar Data Collected During PC1902
- 机构：NOAA/NMFS/SEFSC Panama City Laboratory 等
- DOI：https://doi.org/10.25921/tctw-am57
- 文件：`PC_2019_-D20190613-T030352.raw`
- 本地路径：`D:\C#\水声算法\real_noaa_wcsd\PC1902_ME70`
- 文件大小：约 `2.99 MB`

NOAA README 说明该类 Kongsberg/Simrad `.raw` 文件由 ME70、EK60、EK80 或 ES60 等仪器生成，包含 power 以及可选 angular position 数据，每个 beam/frequency 由独立 channel 标识。

## 已完成内容

1. 从 NOAA 公开 S3 桶下载 ME70 原始 `.raw` 文件。
2. 解析 Kongsberg/Simrad RAW datagram framing。
3. 统计 datagram 类型与数量。
4. 提取 RAW payload，生成真实数据结构预览图。
5. 生成 int16-log payload echogram，用于展示文件内真实回波结构。

## 解析结果

共解析出 `264` 个 datagram：

- `CON0`：1 个
- `CON1`：1 个
- `NME0`：31 个
- `RAW0`：231 个

其中 `RAW0` 是主要声学数据记录，`NME0` 对应导航/定位文本记录，`CON0/CON1` 对应配置类记录。

## 结果图

- `results/01_datagram_sequence.png`：datagram 顺序与类型结构图。
- `results/02_raw_payload_byte_echogram.png`：RAW payload 字节级 echogram。
- `results/03_raw_payload_i16_echogram.png`：RAW payload int16-log echogram。

## 结果判断

当前结果证明真实 NOAA ME70 原始声呐文件已经能被读取并完成结构级解析，且 RAW payload 中存在明显多通道/多束回波结构，不是随机字节或下载错误文件。

需要注意：当前解析还不是完整的 Simrad 标定解析流程，尚未完成 power 到 calibrated Sv/TS 的物理量转换，也未解析全部 channel 元数据、采样率、脉冲参数和角度信息。产品级处理应继续补充：

1. 完整 Simrad RAW 格式解析；
2. channel/frequency/beam 元数据提取；
3. power 到 Sv/TS 的标定；
4. 按 ping-channel-range 构建真实 echogram；
5. 与仿真波束形成/CFAR 模块衔接。

## 简历中的稳妥表述

基于 NOAA 公开 ME70 水柱声呐原始 `.raw` 数据，完成文件下载、datagram 结构解析、RAW0/NME0/CON0 等记录类型统计，并生成真实 RAW payload 回波结构预览图；结合自建多波束仿真数据，实现 delay-and-sum 波束形成、二维 CFAR 检测、底线检测和斜距校正，形成“真实数据读取验证 + 可控仿真算法验证”的水声算法项目闭环。

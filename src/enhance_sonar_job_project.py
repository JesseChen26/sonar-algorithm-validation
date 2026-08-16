from pathlib import Path
from PIL import Image, ImageDraw
import csv
import json
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"
RESULTS = ROOT / "results" / "synthetic"
SRC = ROOT / "src"


def mkdirs():
    DATA.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)


def norm01(a, p=(1, 99)):
    a = np.asarray(a, dtype=np.float64)
    a = np.nan_to_num(a, nan=np.nanmin(a[np.isfinite(a)]) if np.any(np.isfinite(a)) else 0.0)
    lo, hi = np.percentile(a, p)
    return np.clip((a - lo) / max(hi - lo, 1e-12), 0, 1)


def save_panel(path, img01, title, xlabel="", ylabel="", overlays=None):
    img = Image.fromarray((np.clip(img01, 0, 1) * 255).astype(np.uint8), "L").convert("RGB")
    img = img.resize((900, 520), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (980, 620), "white")
    canvas.paste(img, (60, 55))
    d = ImageDraw.Draw(canvas)
    d.text((60, 22), title, fill=(0, 0, 0))
    d.text((445, 590), xlabel, fill=(0, 0, 0))
    d.text((8, 285), ylabel, fill=(0, 0, 0))
    d.rectangle((60, 55, 960, 575), outline=(35, 35, 35))
    if overlays:
        for item in overlays:
            x, y, color, label, shape = item
            px = 60 + int(x * 900)
            py = 55 + int(y * 520)
            if shape == "box":
                d.rectangle((px - 8, py - 8, px + 8, py + 8), outline=color, width=3)
            else:
                d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=color, outline=(255, 255, 255))
            if label:
                d.text((px + 9, py - 12), label, fill=color)
    canvas.save(path)


def line_plot(path, xs, series, title, xlabel, ylabel, y_formatter=None):
    width, height = 980, 620
    x0, y0, x1, y1 = 82, 78, 940, 500
    canvas = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(canvas)
    d.text((42, 24), title, fill=(0, 0, 0))
    d.rectangle((x0, y0, x1, y1), outline=(35, 35, 35))
    all_y = np.concatenate([np.asarray(s["y"], dtype=float) for s in series])
    ymin, ymax = float(all_y.min()), float(all_y.max())
    if abs(ymax - ymin) < 1e-9:
        ymax += 1
        ymin -= 1
    pad = 0.08 * (ymax - ymin)
    ymin -= pad
    ymax += pad
    xmin, xmax = float(np.min(xs)), float(np.max(xs))
    for i in range(6):
        y = y1 - i * (y1 - y0) / 5
        val = ymin + i * (ymax - ymin) / 5
        d.line((x0, y, x1, y), fill=(230, 230, 230))
        label = y_formatter(val) if y_formatter else f"{val:.2f}"
        d.text((18, y - 8), label, fill=(80, 80, 80))
    for i in range(6):
        x = x0 + i * (x1 - x0) / 5
        val = xmin + i * (xmax - xmin) / 5
        d.line((x, y0, x, y1), fill=(242, 242, 242))
        d.text((x - 14, y1 + 10), f"{val:.0f}", fill=(80, 80, 80))
    colors = [(0, 90, 180), (210, 80, 40), (40, 150, 80), (145, 80, 170)]
    for idx, s in enumerate(series):
        pts = []
        for xval, yval in zip(xs, s["y"]):
            px = x0 + (xval - xmin) / max(xmax - xmin, 1e-9) * (x1 - x0)
            py = y1 - (yval - ymin) / max(ymax - ymin, 1e-9) * (y1 - y0)
            pts.append((px, py))
        d.line(pts, fill=colors[idx % len(colors)], width=2)
        for px, py in pts:
            d.ellipse((px - 3, py - 3, px + 3, py + 3), fill=colors[idx % len(colors)])
        d.text((x0 + 16, y0 + 16 + idx * 20), s["label"], fill=colors[idx % len(colors)])
    d.text((440, 560), xlabel, fill=(0, 0, 0))
    d.text((10, 290), ylabel, fill=(0, 0, 0))
    canvas.save(path)


def beamform(raw, ranges, element_x, wavelength, angle_grid=None):
    if angle_grid is None:
        angle_grid = np.linspace(-60, 60, 121)
    data = raw.mean(axis=0)
    bf = np.zeros((len(angle_grid), len(ranges)), dtype=np.float64)
    for i, a in enumerate(angle_grid):
        theta = np.deg2rad(a)
        weights = np.exp(1j * 2 * np.pi * element_x * np.sin(theta) / wavelength)
        y = np.sum(data * weights[:, None], axis=0)
        bf[i] = np.abs(y) ** 2
    return angle_grid, 10 * np.log10(bf / max(bf.max(), 1e-12) + 1e-12)


def load_multibeam():
    z = np.load(DATA / "synthetic_multibeam_raw.npz")
    meta = json.loads((DATA / "synthetic_multibeam_metadata.json").read_text(encoding="utf-8"))
    return z["raw"], z["ranges_m"], z["element_x_m"], meta


def detect_cfar_2d(img_db, guard=3, train=7, offset_db=8.5):
    img = img_db.copy()
    detections = np.zeros_like(img, dtype=bool)
    thresholds = np.full_like(img, np.nan, dtype=float)
    rows, cols = img.shape
    for r in range(train + guard, rows - train - guard):
        for c in range(train + guard, cols - train - guard):
            r0, r1 = r - train - guard, r + train + guard + 1
            c0, c1 = c - train - guard, c + train + guard + 1
            window = img[r0:r1, c0:c1]
            mask = np.ones_like(window, dtype=bool)
            gr0, gr1 = train, train + 2 * guard + 1
            gc0, gc1 = train, train + 2 * guard + 1
            mask[gr0:gr1, gc0:gc1] = False
            noise = np.median(window[mask])
            th = noise + offset_db
            thresholds[r, c] = th
            detections[r, c] = img[r, c] > th
    return detections, thresholds


def cluster_top_detections(detections, img_db, angles, ranges, max_count=3):
    score = np.where(detections, img_db, -120.0).copy()
    out = []
    for _ in range(max_count):
        idx = np.unravel_index(np.argmax(score), score.shape)
        if score[idx] <= -100:
            break
        ai, ri = idx
        out.append({"angle_deg": float(angles[ai]), "range_m": float(ranges[ri]), "value_db": float(img_db[idx])})
        a0, a1 = max(0, ai - 7), min(score.shape[0], ai + 8)
        r0, r1 = max(0, ri - 14), min(score.shape[1], ri + 15)
        score[a0:a1, r0:r1] = -120
    return out


def add_cfar_outputs():
    raw, ranges, element_x, meta = load_multibeam()
    angles, bf_db = beamform(raw, ranges, element_x, meta["wavelength_m"])
    det_mask, threshold = detect_cfar_2d(bf_db)
    dets = cluster_top_detections(det_mask, bf_db, angles, ranges, max_count=3)
    targets = meta["targets"]
    overlays = []
    for t in targets:
        overlays.append(((t["range_m"] - ranges.min()) / (ranges.max() - ranges.min()),
                         (t["angle_deg"] - angles.min()) / (angles.max() - angles.min()),
                         (255, 70, 40), "truth", "dot"))
    for d in dets:
        overlays.append(((d["range_m"] - ranges.min()) / (ranges.max() - ranges.min()),
                         (d["angle_deg"] - angles.min()) / (angles.max() - angles.min()),
                         (60, 190, 80), "CFAR", "box"))
    save_panel(RESULTS / "05_cfar_detection_overlay.png", np.clip((bf_db + 45) / 45, 0, 1), "2D CFAR detection overlay on beamformed range-angle map", "range (m)", "beam angle (deg)", overlays)
    save_panel(RESULTS / "06_cfar_threshold_map.png", norm01(threshold), "2D CFAR adaptive threshold map", "range (m)", "beam angle (deg)")

    rows = []
    used = set()
    for t in targets:
        best_i, best_cost = None, 1e9
        for i, d in enumerate(dets):
            if i in used:
                continue
            cost = abs(d["range_m"] - t["range_m"]) / 5 + abs(d["angle_deg"] - t["angle_deg"]) / 10
            if cost < best_cost:
                best_cost, best_i = cost, i
        if best_i is None:
            rows.append([t["name"], t["range_m"], "", "", t["angle_deg"], "", "", "miss"])
            continue
        used.add(best_i)
        d = dets[best_i]
        range_error = d["range_m"] - t["range_m"]
        angle_error = d["angle_deg"] - t["angle_deg"]
        status = "hit" if abs(range_error) <= 2.0 and abs(angle_error) <= 5.0 else "mismatch"
        rows.append([t["name"], t["range_m"], d["range_m"], range_error, t["angle_deg"], d["angle_deg"], angle_error, status])
    with (RESULTS / "cfar_detection_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["target", "true_range_m", "est_range_m", "range_error_m", "true_angle_deg", "est_angle_deg", "angle_error_deg", "status"])
        writer.writerows(rows)
    return rows


def add_slant_range_outputs():
    z = np.load(DATA / "synthetic_sidescan_waterfall.npz")
    img = z["image"]
    slant = z["slant_ranges_m"]
    bottom = z["bottom_line_m"]
    bottom_idx = np.argmax(img[:, :220], axis=1)
    est_bottom = slant[bottom_idx]
    corrected = np.zeros_like(img)
    ground = slant.copy()
    for p in range(img.shape[0]):
        h = max(est_bottom[p], 1e-6)
        valid = slant >= h
        ground_range = np.sqrt(np.maximum(slant[valid] ** 2 - h ** 2, 0))
        corrected[p] = np.interp(ground, ground_range, img[p, valid], left=0, right=0)
    save_panel(RESULTS / "07_slant_range_input.png", norm01(img), "Side-scan image before slant-range correction", "slant range (m)", "ping")
    save_panel(RESULTS / "08_slant_range_corrected.png", norm01(corrected), "Side-scan image after bottom-line based slant-range correction", "ground range proxy (m)", "ping")
    np.savez_compressed(DATA / "synthetic_sidescan_corrected.npz", corrected=corrected.astype(np.float32), ground_ranges_m=ground.astype(np.float32), estimated_bottom_line_m=est_bottom.astype(np.float32))
    return corrected


def simulate_variant(snr_scale=1.0, sound_speed_error=0.0, n_elements=16, angle_step=1.0):
    base_raw, ranges, element_x, meta = load_multibeam()
    rng = np.random.default_rng(10000 + int(snr_scale * 100) + int((sound_speed_error + 100) * 10) + n_elements)
    if n_elements < len(element_x):
        center = len(element_x) // 2
        half = n_elements // 2
        idx = np.arange(center - half, center - half + n_elements)
        raw = base_raw[:, idx, :].copy()
        ex = element_x[idx]
    else:
        raw = base_raw.copy()
        ex = element_x
    noise = (rng.standard_normal(raw.shape) + 1j * rng.standard_normal(raw.shape)).astype(np.complex64) * (0.075 * snr_scale)
    signal_scale = max(0.25, 1.0 / (0.65 + 0.35 * snr_scale))
    raw = raw * signal_scale + noise
    wavelength = meta["wavelength_m"] * (1 + sound_speed_error / meta["sound_speed_mps"])
    angles, bf_db = beamform(raw, ranges, ex, wavelength, np.arange(-60, 60 + angle_step, angle_step))
    det_mask, _ = detect_cfar_2d(bf_db)
    dets = cluster_top_detections(det_mask, bf_db, angles, ranges, max_count=3)
    targets = meta["targets"]
    errs_r, errs_a = [], []
    used = set()
    for t in targets:
        best_i, best_cost = None, 1e9
        for i, d in enumerate(dets):
            if i in used:
                continue
            cost = abs(d["range_m"] - t["range_m"]) / 5 + abs(d["angle_deg"] - t["angle_deg"]) / 10
            if cost < best_cost:
                best_cost, best_i = cost, i
        if best_i is not None:
            used.add(best_i)
            er = abs(dets[best_i]["range_m"] - t["range_m"])
            ea = abs(dets[best_i]["angle_deg"] - t["angle_deg"])
            if er <= 2.0 and ea <= 5.0:
                errs_r.append(er)
                errs_a.append(ea)
    hit_rate = len(errs_r) / len(targets)
    penalty_r = (len(targets) - len(errs_r)) * 10.0
    penalty_a = (len(targets) - len(errs_a)) * 10.0
    return float((np.sum(errs_r) + penalty_r) / len(targets)), float((np.sum(errs_a) + penalty_a) / len(targets)), hit_rate


def add_sensitivity_outputs():
    snr_scales = np.array([0.4, 0.7, 1.0, 1.5, 2.2, 3.2])
    snr_rows = []
    for s in snr_scales:
        er, ea, hr = simulate_variant(snr_scale=s)
        snr_rows.append([s, er, ea, hr])
    line_plot(RESULTS / "09_snr_sensitivity.png", snr_scales, [
        {"label": "mean range error (m)", "y": [r[1] for r in snr_rows]},
        {"label": "mean angle error (deg)", "y": [r[2] for r in snr_rows]},
    ], "Parameter sensitivity: noise scale vs detection error", "noise scale", "error")

    c_errors = np.array([-30, -15, 0, 15, 30])
    c_rows = []
    for ce in c_errors:
        er, ea, hr = simulate_variant(sound_speed_error=ce)
        c_rows.append([ce, er, ea, hr])
    line_plot(RESULTS / "10_sound_speed_sensitivity.png", c_errors, [
        {"label": "mean range error (m)", "y": [r[1] for r in c_rows]},
        {"label": "mean angle error (deg)", "y": [r[2] for r in c_rows]},
    ], "Parameter sensitivity: sound-speed error vs detection error", "sound-speed error (m/s)", "error")

    elem_counts = np.array([4, 6, 8, 10, 12, 16])
    e_rows = []
    for n in elem_counts:
        er, ea, hr = simulate_variant(n_elements=int(n))
        e_rows.append([n, er, ea, hr])
    line_plot(RESULTS / "11_array_size_sensitivity.png", elem_counts, [
        {"label": "mean range error (m)", "y": [r[1] for r in e_rows]},
        {"label": "mean angle error (deg)", "y": [r[2] for r in e_rows]},
    ], "Parameter sensitivity: array size vs detection error", "array elements", "error")

    with (RESULTS / "parameter_sensitivity_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["experiment", "parameter", "mean_range_error_m", "mean_angle_error_deg", "hit_rate"])
        for row in snr_rows:
            writer.writerow(["noise_scale", *row])
        for row in c_rows:
            writer.writerow(["sound_speed_error_mps", *row])
        for row in e_rows:
            writer.writerow(["array_elements", *row])


def write_readme():
    readme = """# 单/多波束声呐算法仿真与测试分析项目

## 项目定位

本项目面向水声算法工程师岗位，构建一套小型、可复现、带真值的声呐算法验证数据集和处理流程。项目覆盖单/多波束产品算法常见环节：原始回波仿真、延时求和波束形成、距离-角度成像、CFAR 检测、侧扫声呐底线检测、斜距校正和参数敏感性分析。第二版仿真加入了非整数目标距离/角度、弱目标、多径副本、杂波和更强噪声，避免结果过于理想化。

## 数据内容

- `data/synthetic_multibeam_raw.npz`：多波束阵列原始复数回波，维度为 ping × array element × range sample。
- `data/synthetic_multibeam_metadata.json`：声速、中心频率、阵元间距、目标距离/角度真值。
- `data/synthetic_sidescan_waterfall.npz`：侧扫声呐瀑布图，包含海底线、目标强回波、声影和噪声。
- `data/synthetic_sidescan_corrected.npz`：基于底线检测的斜距校正结果。

数据总量控制在数 MB，方便在本地快速运行和展示。

## 算法流程

1. 生成 LFM/窄带近似目标回波、阵元相位差、噪声、海底回波、多径副本和杂波。
2. 对阵列回波执行 delay-and-sum 波束形成，得到距离-角度强度图。
3. 使用二维 CFAR 在距离-角度图上进行目标检测。
4. 基于目标真值计算距离误差、角度误差和命中情况。
5. 对侧扫瀑布图进行底线检测，并按底线高度执行斜距校正。
6. 分析噪声、声速误差和阵元数量对检测误差的影响。

## 运行方式

在项目外层运行：

```powershell
python build_sonar_job_dataset.py
python enhance_sonar_job_project.py
```

如果本机 MATLAB 环境可用，也可以参考：

```matlab
run('D:\\C#\\水声算法\\sonar_job_dataset\\src\\run_multibeam_demo.m')
```

## 主要结果

- `results/01_raw_echo_echogram.png`：原始复数回波瀑布图。
- `results/02_delay_sum_range_angle_map.png`：延时求和波束形成后的距离-角度图。
- `results/05_cfar_detection_overlay.png`：CFAR 检测结果叠加图。
- `results/06_cfar_threshold_map.png`：CFAR 自适应阈值图。
- `results/07_slant_range_input.png`：侧扫声呐斜距图。
- `results/08_slant_range_corrected.png`：斜距校正后图像。
- `results/09_snr_sensitivity.png`：噪声变化对检测误差影响。
- `results/10_sound_speed_sensitivity.png`：声速误差对检测误差影响。
- `results/11_array_size_sensitivity.png`：阵元数量对检测误差影响。

## 岗位匹配点

- 对应“单/多波束声呐产品相关算法研究、仿真和实现”。
- 对应“基于理论分析编写算法设计文档、负责算法功能实现、测试和分析”。
- 对应“熟悉 MATLAB，能建立声呐理论仿真、算法仿真和数据分析”。
- 对应“解决产品测试过程遇到的算法问题”：项目中通过参数敏感性分析定位噪声、声速和阵列参数对结果的影响。

## 结果边界

本项目是小型仿真验证项目，不等同于真实声呐产品数据。结果可用于展示算法链路、指标计算和测试分析能力；若用于产品级验证，还需接入真实 XTF/JSF/多波束水柱数据，并补充姿态补偿、声速剖面修正、安装角标定和海试数据对比。

## 简历表述建议

基于单/多波束声呐工作流程构建小型算法验证项目，模拟阵列原始复数回波、海底线、目标强回波及声影数据；实现 delay-and-sum 波束形成、距离-角度成像、二维 CFAR 检测、底线检测和斜距校正，输出回波瀑布图、成像图和检测结果图；基于真值评估目标距离/角度估计误差及底线检测误差，并分析噪声、声速误差和阵元数量对算法性能的影响。
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")


def write_matlab_demo():
    matlab = r"""% Multibeam sonar algorithm demo
% This MATLAB script mirrors the Python workflow at a readable level.
% It loads CSV/NPZ-derived results if available and demonstrates the
% delay-and-sum beamforming equations used in the project.

clear; clc; close all;

root = fileparts(fileparts(mfilename('fullpath')));
metricsPath = fullfile(root, 'results', 'cfar_detection_metrics.csv');

if exist(metricsPath, 'file')
    T = readtable(metricsPath);
    disp(T);
else
    warning('Run enhance_sonar_job_project.py first to create CFAR metrics.');
end

% Algorithm sketch for MATLAB implementation:
% raw(ping, element, range) is complex baseband echo.
% element_x is the array coordinate in meters.
% ranges is the range vector in meters.
% lambda = c / fc.
%
% for each beam angle theta:
%   w = exp(1j * 2*pi * element_x * sin(theta) / lambda);
%   y(theta, range) = sum_element mean_ping(raw) .* w
%   image(theta, range) = 20*log10(abs(y) / max(abs(y)))
%
% Python produces the validated reference figures:
%   results/02_delay_sum_range_angle_map.png
%   results/05_cfar_detection_overlay.png
%   results/06_cfar_threshold_map.png

figure('Name', 'Project result preview');
img = imread(fullfile(root, 'results', '05_cfar_detection_overlay.png'));
imshow(img);
title('2D CFAR detection overlay on beamformed range-angle map');
"""
    (SRC / "run_multibeam_demo.m").write_text(matlab, encoding="utf-8")


def main():
    mkdirs()
    cfar_rows = add_cfar_outputs()
    add_slant_range_outputs()
    add_sensitivity_outputs()
    write_matlab_demo()
    print(f"Enhanced project written to {ROOT}")
    print(f"CFAR rows: {len(cfar_rows)}")


if __name__ == "__main__":
    main()

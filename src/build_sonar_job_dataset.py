from pathlib import Path
from PIL import Image, ImageDraw
import json
import numpy as np


OUT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = OUT_ROOT / "data" / "synthetic"
RESULT_DIR = OUT_ROOT / "results" / "synthetic"


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)


def save_gray(path: Path, arr: np.ndarray):
    a = arr.astype(np.float64)
    lo, hi = np.percentile(a, [1, 99])
    a = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)
    Image.fromarray((a * 255).astype(np.uint8), "L").save(path)


def save_rgb(path: Path, arr01: np.ndarray, overlays=None, xlabel="", ylabel="", title=""):
    arr = np.clip(arr01, 0, 1)
    img = Image.fromarray((arr * 255).astype(np.uint8), "L").convert("RGB")
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
            x, y, color, label = item
            px = 60 + int(x * 900)
            py = 55 + int(y * 520)
            d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=color, outline=(255, 255, 255))
            if label:
                d.text((px + 8, py - 10), label, fill=color)
    canvas.save(path)


def simulate_multibeam_raw(seed=7):
    rng = np.random.default_rng(seed)
    c = 1500.0
    fc = 30000.0
    wavelength = c / fc
    n_elements = 16
    n_pings = 36
    n_ranges = 640
    range_max = 100.0
    ranges = np.linspace(0, range_max, n_ranges)
    element_x = (np.arange(n_elements) - (n_elements - 1) / 2) * (wavelength / 2)

    targets = [
        {"name": "target_A", "range_m": 42.35, "angle_deg": -21.6, "amplitude": 0.88},
        {"name": "target_B", "range_m": 67.82, "angle_deg": 12.4, "amplitude": 0.58},
        {"name": "target_C", "range_m": 80.73, "angle_deg": 33.7, "amplitude": 0.36},
    ]
    bottom = {"range_m": 88.0, "slope_m_per_ping": 0.10, "angle_deg": 0.0, "amplitude": 0.58}

    raw = (0.055 * (rng.standard_normal((n_pings, n_elements, n_ranges)) +
                   1j * rng.standard_normal((n_pings, n_elements, n_ranges)))).astype(np.complex64)

    clutter_angles = np.deg2rad(np.array([-43.5, 47.2]))
    clutter_ranges = np.array([54.8, 76.2])
    clutter_amps = np.array([0.18, 0.14])

    sigma_r = 0.55
    for p in range(n_pings):
        ping_shift = (p - (n_pings - 1) / 2) / n_pings
        for target in targets:
            r0 = target["range_m"] + 0.15 * np.sin(2 * np.pi * p / n_pings)
            theta = np.deg2rad(target["angle_deg"] + 0.6 * ping_shift)
            profile = target["amplitude"] * np.exp(-0.5 * ((ranges - r0) / sigma_r) ** 2)
            phase = np.exp(-1j * 2 * np.pi * element_x * np.sin(theta) / wavelength)
            raw[p] += phase[:, None] * profile[None, :]

            multipath_r0 = r0 + 3.2 + 0.15 * np.cos(2 * np.pi * p / n_pings)
            multipath_profile = 0.18 * target["amplitude"] * np.exp(-0.5 * ((ranges - multipath_r0) / 0.9) ** 2)
            multipath_phase = np.exp(-1j * 2 * np.pi * element_x * np.sin(theta + np.deg2rad(3.5)) / wavelength)
            raw[p] += multipath_phase[:, None] * multipath_profile[None, :]

        for ca, cr, amp in zip(clutter_angles, clutter_ranges, clutter_amps):
            cr0 = cr + 0.35 * np.sin(2 * np.pi * p / 9)
            profile = amp * np.exp(-0.5 * ((ranges - cr0) / 1.6) ** 2)
            phase = np.exp(-1j * 2 * np.pi * element_x * np.sin(ca) / wavelength)
            raw[p] += phase[:, None] * profile[None, :]

        r_bottom = bottom["range_m"] + bottom["slope_m_per_ping"] * (p - n_pings / 2)
        profile = bottom["amplitude"] * np.exp(-0.5 * ((ranges - r_bottom) / 1.2) ** 2)
        raw[p] += profile[None, :]

    meta = {
        "type": "synthetic_multibeam_raw_complex",
        "sound_speed_mps": c,
        "center_frequency_hz": fc,
        "wavelength_m": wavelength,
        "array": {"n_elements": n_elements, "spacing_m": wavelength / 2},
        "dimensions": {"n_pings": n_pings, "n_elements": n_elements, "n_ranges": n_ranges},
        "range_max_m": range_max,
        "targets": targets,
        "bottom": bottom,
        "interference": {
            "multipath": "weak delayed replica per target",
            "clutter_ranges_m": clutter_ranges.tolist(),
            "clutter_angles_deg": np.rad2deg(clutter_angles).tolist()
        },
        "intended_algorithms": ["delay-and-sum beamforming", "range-angle imaging", "CFAR detection", "range/angle error analysis"],
    }
    np.savez_compressed(
        DATA_DIR / "synthetic_multibeam_raw.npz",
        raw=raw,
        ranges_m=ranges.astype(np.float32),
        element_x_m=element_x.astype(np.float32),
        target_ranges_m=np.array([t["range_m"] for t in targets], dtype=np.float32),
        target_angles_deg=np.array([t["angle_deg"] for t in targets], dtype=np.float32),
    )
    (DATA_DIR / "synthetic_multibeam_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return raw, ranges, element_x, targets, wavelength


def beamform(raw, ranges, element_x, wavelength):
    angles = np.linspace(-60, 60, 121)
    bf = np.zeros((len(angles), len(ranges)), dtype=np.float64)
    data = raw.mean(axis=0)
    for i, a in enumerate(angles):
        theta = np.deg2rad(a)
        weights = np.exp(1j * 2 * np.pi * element_x * np.sin(theta) / wavelength)
        y = np.sum(data * weights[:, None], axis=0)
        bf[i] = np.abs(y) ** 2
    bf_db = 10 * np.log10(bf / max(bf.max(), 1e-12) + 1e-12)
    return angles, bf_db


def cfar_like_detect(bf_db, angles, ranges, targets):
    work = bf_db.copy()
    detections = []
    for _ in targets:
        idx = np.unravel_index(np.argmax(work), work.shape)
        a_idx, r_idx = idx
        detections.append({"angle_deg": float(angles[a_idx]), "range_m": float(ranges[r_idx]), "value_db": float(work[idx])})
        a0, a1 = max(0, a_idx - 8), min(work.shape[0], a_idx + 9)
        r0, r1 = max(0, r_idx - 18), min(work.shape[1], r_idx + 19)
        work[a0:a1, r0:r1] = -120
    return detections


def match_metrics(detections, targets):
    rows = []
    used = set()
    for t in targets:
        best_i, best_cost = None, 1e9
        for i, d in enumerate(detections):
            if i in used:
                continue
            cost = abs(d["range_m"] - t["range_m"]) / 5 + abs(d["angle_deg"] - t["angle_deg"]) / 10
            if cost < best_cost:
                best_cost, best_i = cost, i
        used.add(best_i)
        d = detections[best_i]
        rows.append({
            "target": t["name"],
            "true_range_m": t["range_m"],
            "est_range_m": d["range_m"],
            "range_error_m": d["range_m"] - t["range_m"],
            "true_angle_deg": t["angle_deg"],
            "est_angle_deg": d["angle_deg"],
            "angle_error_deg": d["angle_deg"] - t["angle_deg"],
        })
    return rows


def write_metrics(rows):
    path = RESULT_DIR / "multibeam_detection_metrics.csv"
    with path.open("w", encoding="utf-8") as f:
        f.write("target,true_range_m,est_range_m,range_error_m,true_angle_deg,est_angle_deg,angle_error_deg\n")
        for r in rows:
            f.write(",".join(str(r[k]) for k in ["target", "true_range_m", "est_range_m", "range_error_m", "true_angle_deg", "est_angle_deg", "angle_error_deg"]) + "\n")


def simulate_sidescan(seed=11):
    rng = np.random.default_rng(seed)
    n_pings, n_slant = 140, 520
    slant_ranges = np.linspace(0, 80, n_slant)
    bottom_line = 18 + 2.2 * np.sin(np.linspace(0, 3 * np.pi, n_pings)) + np.linspace(-1.0, 2.0, n_pings)
    img = 0.10 + 0.04 * rng.standard_normal((n_pings, n_slant))
    img = np.clip(img, 0, None)
    target_truth = [
        {"ping": 42, "slant_range_m": 37.5, "name": "object_1"},
        {"ping": 91, "slant_range_m": 54.0, "name": "object_2"},
    ]
    for p in range(n_pings):
        b = bottom_line[p]
        bottom_profile = 0.55 * np.exp(-0.5 * ((slant_ranges - b) / 0.55) ** 2)
        decay = 1 / np.sqrt(1 + slant_ranges)
        img[p] += bottom_profile + 0.40 * decay
    for t in target_truth:
        pp = np.arange(n_pings)[:, None]
        rr = slant_ranges[None, :]
        blob = np.exp(-0.5 * ((pp - t["ping"]) / 2.8) ** 2) * np.exp(-0.5 * ((rr - t["slant_range_m"]) / 1.2) ** 2)
        shadow = np.exp(-0.5 * ((pp - t["ping"] - 4) / 5.0) ** 2) * ((rr > t["slant_range_m"] + 1.5) & (rr < t["slant_range_m"] + 9.0))
        img += 0.85 * blob
        img -= 0.13 * shadow
    img = np.clip(img, 0, None).astype(np.float32)
    np.savez_compressed(DATA_DIR / "synthetic_sidescan_waterfall.npz", image=img, slant_ranges_m=slant_ranges.astype(np.float32), bottom_line_m=bottom_line.astype(np.float32))
    meta = {
        "type": "synthetic_sidescan_waterfall",
        "dimensions": {"n_pings": n_pings, "n_slant_ranges": n_slant},
        "targets": target_truth,
        "intended_algorithms": ["bottom-line detection", "slant-range correction", "TVG/gain normalization", "target highlight and acoustic shadow analysis"],
    }
    (DATA_DIR / "synthetic_sidescan_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return img, slant_ranges, bottom_line, target_truth


def plot_multibeam(raw, ranges, targets, angles, bf_db, detections):
    echogram = 20 * np.log10(np.abs(raw[:, 0, :]) + 1e-6)
    save_rgb(RESULT_DIR / "01_raw_echo_echogram.png", (echogram - echogram.min()) / (echogram.max() - echogram.min()), xlabel="range bin", ylabel="ping", title="Raw complex echo preview: element 1 ping-range echogram")

    view = np.clip((bf_db + 45) / 45, 0, 1)
    overlays = []
    for t in targets:
        x = (t["range_m"] - ranges.min()) / (ranges.max() - ranges.min())
        y = (t["angle_deg"] - angles.min()) / (angles.max() - angles.min())
        overlays.append((x, y, (255, 60, 50), "truth"))
    for d in detections:
        x = (d["range_m"] - ranges.min()) / (ranges.max() - ranges.min())
        y = (d["angle_deg"] - angles.min()) / (angles.max() - angles.min())
        overlays.append((x, y, (60, 190, 80), "est"))
    save_rgb(RESULT_DIR / "02_delay_sum_range_angle_map.png", view, overlays=overlays, xlabel="range (m)", ylabel="beam angle (deg)", title="Delay-and-sum beamforming result: range-angle intensity map")


def plot_sidescan(img, slant_ranges, bottom_line, target_truth):
    view = np.clip((img - np.percentile(img, 2)) / (np.percentile(img, 99) - np.percentile(img, 2)), 0, 1)
    overlays = []
    for t in target_truth:
        x = (t["slant_range_m"] - slant_ranges.min()) / (slant_ranges.max() - slant_ranges.min())
        y = t["ping"] / (img.shape[0] - 1)
        overlays.append((x, y, (255, 60, 50), t["name"]))
    save_rgb(RESULT_DIR / "03_sidescan_waterfall_with_truth.png", view, overlays=overlays, xlabel="slant range (m)", ylabel="ping", title="Synthetic side-scan waterfall: bottom return, target highlight, acoustic shadow")

    bottom_idx = np.argmax(img[:, :220], axis=1)
    est_bottom = slant_ranges[bottom_idx]
    rows = []
    for i, (truth, est) in enumerate(zip(bottom_line, est_bottom)):
        rows.append((i, truth, est, est - truth))
    with (RESULT_DIR / "sidescan_bottom_detection_metrics.csv").open("w", encoding="utf-8") as f:
        f.write("ping,true_bottom_m,est_bottom_m,error_m\n")
        for row in rows:
            f.write(f"{row[0]},{row[1]:.4f},{row[2]:.4f},{row[3]:.4f}\n")

    width, height = 980, 520
    canvas = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(canvas)
    d.text((24, 18), "Bottom-line detection error on side-scan waterfall", fill=(0, 0, 0))
    x0, y0, x1, y1 = 70, 75, 940, 430
    d.rectangle((x0, y0, x1, y1), outline=(40, 40, 40))
    err = np.array([r[3] for r in rows])
    max_abs = max(np.max(np.abs(err)), 1e-6)
    pts = []
    for i, e in enumerate(err):
        x = x0 + i * (x1 - x0) / (len(err) - 1)
        y = (y0 + y1) / 2 - (e / max_abs) * (y1 - y0) * 0.43
        pts.append((x, y))
    d.line((x0, (y0 + y1) / 2, x1, (y0 + y1) / 2), fill=(220, 220, 220))
    d.line(pts, fill=(0, 90, 180), width=2)
    d.text((70, 455), f"mean abs error={np.mean(np.abs(err)):.3f} m, max abs error={np.max(np.abs(err)):.3f} m", fill=(0, 0, 0))
    canvas.save(RESULT_DIR / "04_bottom_line_error.png")


def main():
    ensure_dirs()
    raw, ranges, element_x, targets, wavelength = simulate_multibeam_raw()
    angles, bf_db = beamform(raw, ranges, element_x, wavelength)
    detections = cfar_like_detect(bf_db, angles, ranges, targets)
    rows = match_metrics(detections, targets)
    write_metrics(rows)
    plot_multibeam(raw, ranges, targets, angles, bf_db, detections)

    img, slant_ranges, bottom_line, target_truth = simulate_sidescan()
    plot_sidescan(img, slant_ranges, bottom_line, target_truth)

    summary = {
        "dataset_root": str(OUT_ROOT),
        "multibeam_targets": targets,
        "multibeam_detections": detections,
        "metrics": rows,
        "notes": "Small synthetic raw/processed sonar dataset with ground truth for job-matched algorithm demos.",
    }
    (OUT_ROOT / "README_project_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote upgraded sonar dataset and results to {OUT_ROOT}")
    for r in rows:
        print(f"{r['target']}: range_error={r['range_error_m']:.2f} m, angle_error={r['angle_error_deg']:.2f} deg")


if __name__ == "__main__":
    main()

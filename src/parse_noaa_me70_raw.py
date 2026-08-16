from pathlib import Path
from PIL import Image, ImageDraw
import csv
import json
import struct
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "real_noaa_me70" / "PC_2019_-D20190613-T030352.raw"
OUT = ROOT / "results" / "real_noaa_me70"
OUT.mkdir(exist_ok=True)


def read_datagrams(path):
    data = path.read_bytes()
    offset = 0
    records = []
    while offset + 12 <= len(data):
        size = struct.unpack_from("<i", data, offset)[0]
        if size <= 0 or offset + 4 + size + 4 > len(data):
            offset += 1
            continue
        payload_start = offset + 4
        payload_end = payload_start + size
        trailer = struct.unpack_from("<i", data, payload_end)[0]
        dtype = data[payload_start:payload_start + 4].decode("latin1", errors="replace")
        if trailer == size and dtype[:3].isprintable():
            records.append({
                "offset": offset,
                "size": size,
                "type": dtype,
                "payload_start": payload_start,
                "payload_end": payload_end,
            })
            offset = payload_end + 4
        else:
            offset += 1
    return data, records


def parse_sample_datagram(data, rec):
    payload = data[rec["payload_start"]:rec["payload_end"]]
    body = payload[12:]
    if len(body) < 128:
        return None
    header = np.frombuffer(body[:128], dtype="<u2")
    sample_bytes = body[128:]
    if not sample_bytes:
        return None
    arr_i16 = np.frombuffer(sample_bytes[: len(sample_bytes) // 2 * 2], dtype="<i2").astype(np.float32)
    arr_u8 = np.frombuffer(sample_bytes, dtype=np.uint8).astype(np.float32)
    return {
        "type": rec["type"],
        "offset": rec["offset"],
        "size": rec["size"],
        "header_u16_first32": header[:32].astype(int).tolist(),
        "i16": arr_i16,
        "u8": arr_u8,
    }


def norm01(a):
    a = np.asarray(a, dtype=float)
    lo, hi = np.percentile(a, [1, 99])
    return np.clip((a - lo) / max(hi - lo, 1e-12), 0, 1)


def save_image(path, arr01, title, xlabel="", ylabel=""):
    im = Image.fromarray((norm01(arr01) * 255).astype(np.uint8), "L").convert("RGB")
    im = im.resize((920, 520), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (1000, 620), "white")
    canvas.paste(im, (60, 55))
    d = ImageDraw.Draw(canvas)
    d.text((60, 22), title, fill=(0, 0, 0))
    d.text((450, 590), xlabel, fill=(0, 0, 0))
    d.text((8, 285), ylabel, fill=(0, 0, 0))
    d.rectangle((60, 55, 980, 575), outline=(35, 35, 35))
    canvas.save(path)


def build_raw_byte_echogram(data, records):
    sample_records = [r for r in records if r["type"].startswith("RAW")]
    rows = []
    max_len = 0
    for rec in sample_records:
        payload = data[rec["payload_start"]:rec["payload_end"]]
        body = payload[12:]
        if len(body) <= 128:
            continue
        row = np.frombuffer(body[128:], dtype=np.uint8).astype(np.float32)
        if row.size < 64:
            continue
        rows.append(row)
        max_len = max(max_len, row.size)
    if not rows:
        return None
    width = min(max_len, 2400)
    mat = np.zeros((len(rows), width), dtype=np.float32)
    for i, row in enumerate(rows):
        if row.size >= width:
            idx = np.linspace(0, row.size - 1, width).astype(int)
            mat[i] = row[idx]
        else:
            mat[i, : row.size] = row
    return mat


def build_i16_echogram(data, records):
    sample_records = [r for r in records if r["type"].startswith("RAW")]
    rows = []
    max_len = 0
    for rec in sample_records:
        parsed = parse_sample_datagram(data, rec)
        if not parsed or parsed["i16"].size < 64:
            continue
        row = np.abs(parsed["i16"])
        rows.append(row)
        max_len = max(max_len, row.size)
    if not rows:
        return None
    width = min(max_len, 2400)
    mat = np.zeros((len(rows), width), dtype=np.float32)
    for i, row in enumerate(rows):
        if row.size >= width:
            idx = np.linspace(0, row.size - 1, width).astype(int)
            mat[i] = row[idx]
        else:
            mat[i, : row.size] = row
    return np.log1p(mat)


def save_type_summary(records):
    counts = {}
    sizes = {}
    for r in records:
        counts[r["type"]] = counts.get(r["type"], 0) + 1
        sizes[r["type"]] = sizes.get(r["type"], 0) + r["size"]
    with (OUT / "datagram_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["datagram_type", "count", "total_payload_bytes"])
        for k in sorted(counts):
            w.writerow([k, counts[k], sizes[k]])
    return counts, sizes


def save_record_map(records):
    xs = np.arange(len(records))
    sizes = np.array([r["size"] for r in records], dtype=float)
    types = sorted(set(r["type"] for r in records))
    type_to_id = {t: i for i, t in enumerate(types)}
    y = np.array([type_to_id[r["type"]] for r in records], dtype=float)
    canvas = Image.new("RGB", (1000, 620), "white")
    d = ImageDraw.Draw(canvas)
    d.text((60, 24), "NOAA PC1902 ME70 RAW datagram sequence", fill=(0, 0, 0))
    x0, y0, x1, y1 = 80, 70, 940, 510
    d.rectangle((x0, y0, x1, y1), outline=(35, 35, 35))
    colors = [(0, 90, 180), (210, 80, 40), (40, 150, 80), (150, 90, 180), (190, 140, 30)]
    for i, r in enumerate(records):
        px = x0 + int(i / max(len(records) - 1, 1) * (x1 - x0))
        py = y0 + int(type_to_id[r["type"]] / max(len(types) - 1, 1) * (y1 - y0))
        radius = max(2, min(8, int(np.log10(max(r["size"], 10)))))
        color = colors[type_to_id[r["type"]] % len(colors)]
        d.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color)
    for i, t in enumerate(types):
        d.text((80 + (i % 4) * 210, 535 + (i // 4) * 18), t, fill=colors[i % len(colors)])
    d.text((420, 585), "datagram index", fill=(0, 0, 0))
    canvas.save(OUT / "01_datagram_sequence.png")


def main():
    data, records = read_datagrams(RAW)
    counts, sizes = save_type_summary(records)
    save_record_map(records)
    byte_echo = build_raw_byte_echogram(data, records)
    if byte_echo is not None:
        save_image(OUT / "02_raw_payload_byte_echogram.png", byte_echo, "NOAA ME70 RAW payload byte echogram", "downsampled payload/sample index", "RAW datagram index")
    i16_echo = build_i16_echogram(data, records)
    if i16_echo is not None:
        save_image(OUT / "03_raw_payload_i16_echogram.png", i16_echo, "NOAA ME70 RAW payload int16-log echogram", "downsampled payload/sample index", "RAW datagram index")

    sample_headers = []
    for r in records:
        if r["type"].startswith("RAW"):
            p = parse_sample_datagram(data, r)
            if p:
                sample_headers.append({k: p[k] for k in ["type", "offset", "size", "header_u16_first32"]})
            if len(sample_headers) >= 5:
                break
    meta = {
        "source": "NOAA NCEI WCSD, Pisces PC1902 ME70",
        "doi": "https://doi.org/10.25921/tctw-am57",
        "file": str(RAW),
        "file_bytes": len(data),
        "datagram_count": len(records),
        "datagram_type_counts": counts,
        "sample_headers": sample_headers,
        "note": "This parser validates Simrad/Kongsberg RAW datagram framing and produces structure/payload echogram previews. Full calibrated Sv extraction requires instrument-specific RAW decoding.",
    }
    (OUT / "parse_summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Parsed {len(records)} datagrams from {RAW.name}")
    print(counts)
    print(f"Outputs: {OUT}")


if __name__ == "__main__":
    main()

"""Measure the download speed of the encoder weights from the Hugging Face CDN -> evidence/download_speed.json

The report's feasibility item cites this number (a 4 MB byte range of model.safetensors, one request).

Run: .venv/bin/python -I src/download_speed.py
"""
import json
import pathlib
import subprocess
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
URL = ("https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/resolve/"
       "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/model.safetensors")
FMT = "%{http_code} %{size_download} %{speed_download} %{time_total}"

out = subprocess.run(["curl", "-s", "-m", "90", "-L", "-r", "0-3999999", "-o", "/dev/null", "-w", FMT, URL],
                     capture_output=True, text=True).stdout.split()
size = subprocess.run(["curl", "-s", "-m", "30", "-I", URL], capture_output=True, text=True).stdout
linked = next((l.split(":", 1)[1].strip() for l in size.splitlines() if l.lower().startswith("x-linked-size")), None)
res = {"url": URL, "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "http_code": out[0], "bytes": int(out[1]), "bytes_per_second": float(out[2]), "seconds": float(out[3]),
       "file_size_bytes": int(linked) if linked else None}
if res["file_size_bytes"]:
    res["estimated_full_download_hours"] = round(res["file_size_bytes"] / res["bytes_per_second"] / 3600, 1)
(ROOT / "evidence" / "download_speed.json").write_text(json.dumps(res, indent=2))
print(res)

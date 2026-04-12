from __future__ import annotations

import glob
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone


def write_json_file(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return {
        "path": path,
        "size_bytes": os.path.getsize(path),
    }


def write_api_artifacts(artifact_dir, artifacts):
    written = {}
    os.makedirs(artifact_dir, exist_ok=True)
    for name, payload in sorted((artifacts or {}).items()):
        path = os.path.join(artifact_dir, f"{name}.json")
        written[name] = write_json_file(path, payload)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifact_count": len(written),
        "artifacts": written,
    }
    write_json_file(os.path.join(artifact_dir, "manifest.json"), manifest)
    return manifest


def publish_download_excels(download_dir, public_dir):
    dst_dir = os.path.join(public_dir, "download")
    os.makedirs(dst_dir, exist_ok=True)
    copied_files = []
    for src in sorted(glob.glob(os.path.join(download_dir, "*.xlsx"))):
        try:
            dst = os.path.join(dst_dir, os.path.basename(src))
            shutil.copy2(src, dst)
            copied_files.append(os.path.basename(dst))
        except Exception as exc:
            print(f"Warn publish excel {src}: {exc}")
    zip_name = "ყველა_ანგარიში.xlsx.zip"
    zip_path = os.path.join(dst_dir, zip_name)
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as handle:
            for file_name in copied_files:
                path = os.path.join(dst_dir, file_name)
                if os.path.isfile(path):
                    handle.write(path, arcname=file_name)
    except Exception as exc:
        print(f"Warn zip create {zip_path}: {exc}")
        zip_name = ""
    print(f"  Published Excel files to public/download: {len(copied_files)}")
    return {"files": copied_files, "zip_file": zip_name}

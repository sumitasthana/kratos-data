"""Emit frames to Parquet and write a run manifest.

The manifest is a first-class deliverable, not a log line. It records the spec
hash, the seed, and a content hash of the output so any change to the generated
data is visible and has to be explained. The content hash is computed from a
canonical serialisation of the frames, not from the Parquet bytes, because
Parquet embeds library versions and timestamps that would make byte comparison
falsely unstable across machines.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


def content_hash(frames: dict[str, pd.DataFrame]) -> str:
    """Deterministic hash of the logical content of the output frames."""
    h = hashlib.sha256()
    for name in sorted(frames):
        df = frames[name].sort_index(axis=1)
        sort_cols = [c for c in df.columns if c in ("account_id", "cycle_seq", "cycle", "event_id")]
        if sort_cols:
            df = df.sort_values(sort_cols).reset_index(drop=True)
        h.update(name.encode())
        h.update(df.to_csv(index=False).encode())
    return h.hexdigest()


def spec_hash(spec_root: Path) -> str:
    """Hash every YAML file under the spec root, in a stable order."""
    h = hashlib.sha256()
    for f in sorted(spec_root.rglob("*.yaml")):
        h.update(f.relative_to(spec_root).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def write(result: dict, out_dir: str | Path, spec_root: Path) -> dict:
    """Write frames as Parquet and a manifest.json. Returns the manifest."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    frames = {k: result[k] for k in ("account_cycle", "events", "accounts")}
    for name, df in frames.items():
        df.to_parquet(out / f"{name}.parquet", index=False)

    manifest = {
        **result["stats"],
        "spec_hash": spec_hash(spec_root),
        "output_hash": content_hash(frames),
        "speculative": True,  # every parameter here is a placeholder, not calibrated
        "note": "Skeleton output. Economics are placeholders, not calibrated billing.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

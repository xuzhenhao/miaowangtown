"""Version constants and compatibility check helpers."""
from pathlib import Path
import json

EXPECTED_VERSIONS = {
    "schema_version": 1,
    "master_mesh_version": 1,
    "uv_version": 1,
    "rig_version": 1,
    "animation_version": 1,
    "render_spec_version": 1,
    "identity_version": 1,
    "asset_version": 1,
}


def verify_master_spec_versions(spec_path: Path) -> bool:
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    for k, v in EXPECTED_VERSIONS.items():
        if data.get(k) != v:
            raise ValueError(f"Version mismatch for {k}: expected {v}, got {data.get(k)}")
    return True

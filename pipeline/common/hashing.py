"""Deterministic SHA-256 hashing for frozen UV layouts and palettes."""
import hashlib
import json
from typing import List, Sequence, Union


def compute_uv_hash_from_loops(loop_rows: Sequence[Sequence[Union[int, float]]]) -> str:
    """Compute deterministic sha256:<hex> from [[vertex_index, round(u,6), round(v,6)], ...]."""
    normalized = [
        [int(row[0]), round(float(row[1]), 6), round(float(row[2]), 6)]
        for row in loop_rows
    ]
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()

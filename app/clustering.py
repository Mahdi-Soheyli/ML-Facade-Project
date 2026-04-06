"""Cluster panels by governing nominal glass key; assign stable display colors."""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas import ClusterGroup

_DATA = Path(__file__).resolve().parents[1] / "building_code" / "e1300_data" / "tables.json"

_PALETTE = [
    "#1e3a5f",
    "#2e7d8f",
    "#2d8f5c",
    "#8faa3c",
    "#c9a227",
    "#c17f2a",
    "#b85c38",
    "#a84848",
    "#8b3d8b",
    "#5c4a7a",
    "#4a6fa5",
    "#6b8e23",
]


def _nominal_order_and_mm() -> tuple[list[str], dict[str, float]]:
    data = json.loads(_DATA.read_text(encoding="utf-8"))
    order = list(data["nominal_keys_ordered"])
    mm_map = {k: float(v) for k, v in data["table4_nominal_mm_to_minimum_mm"].items()}
    return order, mm_map


def build_clusters(panel_results: list[dict]) -> list[ClusterGroup]:
    """
    panel_results: list of dicts with keys id, oracle.minimum_nominal_key (optional).
    Groups by minimum_nominal_key; color by order of first appearance sorted by table order.
    """
    order, mm_map = _nominal_order_and_mm()
    key_to_ids: dict[str, list[str]] = {}
    for row in panel_results:
        pid = row["id"]
        ora = row.get("oracle") or {}
        nk = ora.get("minimum_nominal_key")
        if nk is None:
            nk = ora.get("governing_nominal_fallback")  # unused; keep extensibility
        if nk is None:
            nk = "__unknown__"
        key_to_ids.setdefault(str(nk), []).append(pid)

    def sort_key(k: str) -> tuple[int, str]:
        if k == "__unknown__":
            return (10_000, k)
        if k in order:
            return (order.index(k), k)
        return (5000, k)

    sorted_keys = sorted(key_to_ids.keys(), key=sort_key)
    clusters: list[ClusterGroup] = []
    for i, nk in enumerate(sorted_keys):
        ids = key_to_ids[nk]
        th = None if nk == "__unknown__" else mm_map.get(nk)
        clusters.append(
            ClusterGroup(
                cluster_index=i,
                color_hex=_PALETTE[i % len(_PALETTE)],
                nominal_key=None if nk == "__unknown__" else nk,
                thickness_mm_min=th,
                panel_ids=sorted(ids),
            )
        )
    return clusters

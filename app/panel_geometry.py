"""
Derive panel short/long dimensions (m) from planar triangle or quad vertices.

Workshop rule: project vertices onto the panel plane, then use principal-component
axes (2×2 covariance) and take axis-aligned extents in that basis; short_m and
long_m are the smaller and larger extent respectively.
"""

from __future__ import annotations

import math
from typing import Sequence

# Max distance from fitted plane / max edge length for coplanarity check
_PLANE_TOL_REL = 1e-4


def _sub(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _cross(u: Sequence[float], v: Sequence[float]) -> list[float]:
    return [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    ]


def _dot(u: Sequence[float], v: Sequence[float]) -> float:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def _norm(v: Sequence[float]) -> float:
    return math.sqrt(_dot(v, v))


def _scale(v: Sequence[float], s: float) -> list[float]:
    return [v[0] * s, v[1] * s, v[2] * s]


def _unit(v: Sequence[float]) -> list[float]:
    n = _norm(v)
    if n < 1e-15:
        raise ValueError("degenerate panel: zero-length normal")
    return _scale(v, 1.0 / n)


def _normal_from_polygon(vertices: list[list[float]]) -> list[float]:
    n = len(vertices)
    if n < 3:
        raise ValueError("need at least 3 vertices")
    p0 = vertices[0]
    for i in range(1, n - 1):
        e1 = _sub(vertices[i], p0)
        e2 = _sub(vertices[(i + 1) % n], p0)
        c = _cross(e1, e2)
        if _norm(c) > 1e-12:
            return _unit(c)
    raise ValueError("degenerate panel: cannot compute normal")


def _orthonormal_basis(normal: Sequence[float]) -> tuple[list[float], list[float]]:
    """Return (u, v) spanning the plane perpendicular to normal."""
    n = _unit(list(normal))
    # Pick a vector not parallel to n
    if abs(n[0]) < 0.9:
        aux = [1.0, 0.0, 0.0]
    else:
        aux = [0.0, 1.0, 0.0]
    u = _cross(n, aux)
    u = _unit(u)
    v = _cross(n, u)
    v = _unit(v)
    return u, v


def _project2d(vertices: list[list[float]], u: Sequence[float], v: Sequence[float]) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    p0 = vertices[0]
    for p in vertices:
        w = _sub(p, p0)
        pts.append((_dot(w, u), _dot(w, v)))
    return pts


def _polygon_area_2d(pts: list[tuple[float, float]]) -> float:
    n = len(pts)
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        s += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(s) * 0.5


def _max_deviation_from_plane(vertices: list[list[float]], normal: Sequence[float], origin: Sequence[float]) -> float:
    n = _unit(list(normal))
    max_d = 0.0
    for p in vertices:
        w = _sub(p, origin)
        d = abs(_dot(w, n))
        if d > max_d:
            max_d = d
    return max_d


def _pca_extents_2d(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """Returns (extent_minor, extent_major) after sorting so minor <= major."""
    if len(pts) < 2:
        raise ValueError("need at least 2 2D points")
    mx = sum(x for x, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    cxx = cyy = cxy = 0.0
    for x, y in pts:
        dx = x - mx
        dy = y - my
        cxx += dx * dx
        cyy += dy * dy
        cxy += dx * dy
    n = float(len(pts))
    cxx /= n
    cyy /= n
    cxy /= n
    tr = cxx + cyy
    det = cxx * cyy - cxy * cxy
    disc = max(0.0, tr * tr * 0.25 - det)
    lam_max = tr * 0.5 + math.sqrt(disc)
    lam_min = tr * 0.5 - math.sqrt(disc)
    if lam_max < 1e-18:
        # All points coincident
        return 0.0, 0.0
    # Eigenvector for lam_max
    if abs(cxy) > 1e-18:
        vx = lam_max - cyy
        vy = cxy
    else:
        vx, vy = (1.0, 0.0) if cxx >= cyy else (0.0, 1.0)
    ln = math.hypot(vx, vy)
    if ln < 1e-18:
        e1 = (1.0, 0.0)
    else:
        e1 = (vx / ln, vy / ln)
    e2 = (-e1[1], e1[0])
    proj1 = [x * e1[0] + y * e1[1] for x, y in pts]
    proj2 = [x * e2[0] + y * e2[1] for x, y in pts]
    span1 = max(proj1) - min(proj1)
    span2 = max(proj2) - min(proj2)
    a, b = min(span1, span2), max(span1, span2)
    return a, b


def derive_short_long_area(
    n_edges: int,
    vertices_m: list[list[float]],
    normal: list[float] | None,
    edge_lengths_m: list[float] | None,
    area_m2: float | None,
) -> tuple[float, float, float, list[float]]:
    """
    Returns (short_m, long_m, area_m2_computed, unit_normal).
    Raises ValueError on bad input.
    """
    if n_edges not in (3, 4):
        raise ValueError("n_edges must be 3 or 4")
    if len(vertices_m) != n_edges:
        raise ValueError("vertices_m length must equal n_edges")
    verts = [[float(v[0]), float(v[1]), float(v[2])] for v in vertices_m]
    for i in range(n_edges):
        j = (i + 1) % n_edges
        ei = _norm(_sub(verts[j], verts[i]))
        if ei < 1e-9:
            raise ValueError("degenerate edge length")

    n_vec = normal if normal is not None else _normal_from_polygon(verts)
    n_vec = _unit(n_vec)

    max_edge = max(_norm(_sub(verts[(i + 1) % n_edges], verts[i])) for i in range(n_edges))
    tol = max(_PLANE_TOL_REL * max_edge, 1e-6)
    dev = _max_deviation_from_plane(verts, n_vec, verts[0])
    if dev > tol:
        raise ValueError(f"vertices are not coplanar within tolerance (max deviation {dev:.6g} m)")

    if edge_lengths_m is not None:
        if len(edge_lengths_m) != n_edges:
            raise ValueError("edge_lengths_m length must equal n_edges")
        for i in range(n_edges):
            j = (i + 1) % n_edges
            comp = _norm(_sub(verts[j], verts[i]))
            if abs(comp - float(edge_lengths_m[i])) > max(tol * 10, 1e-4 * max(comp, 1e-6)):
                raise ValueError("edge_lengths_m inconsistent with vertex positions")

    u_axis, v_axis = _orthonormal_basis(n_vec)
    pts2 = _project2d(verts, u_axis, v_axis)
    area_computed = _polygon_area_2d(pts2)
    if area_computed < 1e-12:
        raise ValueError("degenerate polygon area")

    if area_m2 is not None:
        if abs(area_computed - float(area_m2)) / max(area_computed, 1e-12) > 0.02:
            raise ValueError("area_m2 inconsistent with vertex polygon")

    minor, major = _pca_extents_2d(pts2)
    if minor <= 0 or major <= 0:
        raise ValueError("degenerate principal extents")
    short_m = float(minor)
    long_m = float(major)
    return short_m, long_m, area_computed, n_vec

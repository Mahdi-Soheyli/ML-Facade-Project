# Paste into a GhPython component (Rhino 7/8 + Grasshopper).
# Inputs:
#   Surface — Surface or single-face Brep
#   U_Div   — int, divisions along U (number of quads around that direction)
#   V_Div   — int, divisions along V
# Optional inputs:
#   Pattern — omit or 0 = Lunchbox-style stagger + LB resolution (252 @ 12,20 closed hoop).
#             1 = full-resolution stagger. 2 = dense UV checkerboard (480 @ 12,20).
#   Swap_UV — True/False, or omit for AUTO (recommended). Many Rhino cylinders have the
#             CLOSED hoop on surface V (direction 1) and HEIGHT on U (direction 0). This
#             script’s “U_Div” must follow the CLOSED direction for stagger + 252 count. AUTO
#             sets Swap_UV = True when IsClosed(1) and not IsClosed(0). If you see strong
#             vertical panel seams instead of horizontal bands, toggle Swap_UV manually.
# Output:
#   P  — list of Brep, one planar face per triangle
#
# Pattern 0: stagger along logical U (hoop); iso-lines in logical V = horizontal rings on tower.
#
# Lunchbox reference (Proving Ground docs):
#   Triangle Panels C = BOTH diagonals per quad → 4 tris/quad (diamond).
#   Triangular Panels A = ONE diagonal, same every quad → directional.
#   Triangle Panels B = isotropic / staggered look, valence 6 interior (Pattern 0).

import Rhino.Geometry as rg

try:
    import scriptcontext as sc

    def _doc_tol():
        return sc.doc.ModelAbsoluteTolerance
except Exception:

    def _doc_tol():
        return 0.001


def _brep_from_triangle(p0, p1, p2):
    pl = rg.Polyline([p0, p1, p2, p0])
    crv = pl.ToPolylineCurve()
    tol = _doc_tol()
    breps = rg.Brep.CreatePlanarBreps(crv, tol)
    if breps is None or len(breps) < 1:
        return None
    return breps[0]


def _as_surface(geom):
    if geom is None:
        return None
    if isinstance(geom, rg.Brep):
        if geom.Faces.Count < 1:
            return None
        return geom.Faces[0].UnderlyingSurface()
    if isinstance(geom, rg.Surface):
        return geom
    return None


def _logical_domains(srf, swap_uv):
    """Logical U = hoop (stagger direction); logical V = height. Returns (u_dom, v_dom)."""
    if swap_uv:
        return srf.Domain(1), srf.Domain(0)
    return srf.Domain(0), srf.Domain(1)


def _pt(srf, u, v, swap_uv):
    """Evaluate surface: logical (u,v) → Rhino PointAt. swap: hoop is physical dir 1."""
    if swap_uv:
        return srf.PointAt(v, u)
    return srf.PointAt(u, v)


def _logical_u_closed(srf, swap_uv):
    """True if logical U (hoop) direction is periodic / seam-closed."""
    di = 1 if swap_uv else 0
    if srf.IsClosed(di):
        return True
    tol = max(_doc_tol() * 100.0, 1e-4)
    u_dom = srf.Domain(di)
    o_dom = srf.Domain(1 - di)
    mid = o_dom.Mid
    u0 = u_dom.ParameterAt(0.0)
    u1 = u_dom.ParameterAt(1.0)
    a = _pt(srf, u0, mid, swap_uv)
    b = _pt(srf, u1, mid, swap_uv)
    return a.DistanceTo(b) < tol


def _resolve_swap_uv(srf, swap_in):
    """None = auto: common case is closed hoop on V only → swap."""
    if swap_in is True:
        return True
    if swap_in is False:
        return False
    return srf.IsClosed(1) and (not srf.IsClosed(0))


def _ceil_half_u(u_div):
    """ceil(U/2) for int U >= 1 — Lunchbox-style half-U module count around the seam."""
    u_div = max(1, int(u_div))
    return max(1, (u_div + 1) // 2)


def _grid_points_regular(srf, u_dom, v_dom, u_div, v_div, u_closed, swap_uv):
    """Regular UV lattice: closed U → u_div × (v_div+1); open → (u_div+1) × (v_div+1)."""
    pts = []
    if u_closed:
        for i in range(u_div):
            row = []
            u = u_dom.ParameterAt(i / float(u_div))
            for j in range(v_div + 1):
                v = v_dom.ParameterAt(j / float(v_div))
                row.append(_pt(srf, u, v, swap_uv))
            pts.append(row)
    else:
        for i in range(u_div + 1):
            row = []
            u = u_dom.ParameterAt(i / float(u_div))
            for j in range(v_div + 1):
                v = v_dom.ParameterAt(j / float(v_div))
                row.append(_pt(srf, u, v, swap_uv))
            pts.append(row)
    return pts


def _triangles_checkerboard(pts, u_div, v_div, u_closed):
    """
    Each UV quad gets ONE diagonal; orientation alternates in a checkerboard (Lunchbox B).
    Returns list of (p0,p1,p2).
    """
    tris = []
    if u_closed:
        un = u_div
        for j in range(v_div):
            for i in range(un):
                ip = (i + 1) % un
                p00 = pts[i][j]
                p10 = pts[ip][j]
                p11 = pts[ip][j + 1]
                p01 = pts[i][j + 1]
                if (i + j) % 2 == 0:
                    tris.append((p00, p10, p11))
                    tris.append((p00, p11, p01))
                else:
                    tris.append((p00, p10, p01))
                    tris.append((p10, p11, p01))
    else:
        for j in range(v_div):
            for i in range(u_div):
                p00 = pts[i][j]
                p10 = pts[i + 1][j]
                p11 = pts[i + 1][j + 1]
                p01 = pts[i][j + 1]
                if (i + j) % 2 == 0:
                    tris.append((p00, p10, p11))
                    tris.append((p00, p11, p01))
                else:
                    tris.append((p00, p10, p01))
                    tris.append((p10, p11, p01))
    return tris


# --- Optional legacy: staggered U rows (half-offset), with boundary rows full --------

def _row_points(srf, u_dom, v, u_div, stagger, u_closed, swap_uv):
    row = []
    if u_closed:
        if not stagger:
            for i in range(u_div):
                u = u_dom.ParameterAt(i / float(u_div))
                row.append(_pt(srf, u, v, swap_uv))
        else:
            for i in range(u_div):
                u = u_dom.ParameterAt((i + 0.5) / float(u_div))
                row.append(_pt(srf, u, v, swap_uv))
    else:
        if not stagger:
            for i in range(u_div + 1):
                u = u_dom.ParameterAt(i / float(u_div))
                row.append(_pt(srf, u, v, swap_uv))
        else:
            for i in range(u_div):
                u = u_dom.ParameterAt((i + 0.5) / float(u_div))
                row.append(_pt(srf, u, v, swap_uv))
    return row


def _strip_open_even_to_odd(bot, top):
    u_div = len(top)
    tris = []
    for i in range(u_div - 1):
        tris.append((bot[i], top[i], bot[i + 1]))
        tris.append((bot[i + 1], top[i], top[i + 1]))
    tris.append((bot[u_div - 1], top[u_div - 1], bot[u_div]))
    return tris


def _strip_open_odd_to_even(bot, top):
    u_div = len(bot)
    tris = []
    for i in range(u_div - 1):
        tris.append((bot[i], top[i + 1], top[i]))
        tris.append((bot[i], bot[i + 1], top[i + 1]))
    tris.append((bot[u_div - 1], top[u_div], top[u_div - 1]))
    return tris


def _strip_closed_even_to_odd(bot, top):
    n = len(bot)
    if n != len(top):
        return []
    tris = []
    for i in range(n):
        ip = (i + 1) % n
        tris.append((bot[i], top[i], bot[ip]))
        tris.append((bot[ip], top[i], top[ip]))
    return tris


def _strip_closed_odd_to_even(bot, top):
    n = len(bot)
    if n != len(top):
        return []
    tris = []
    for i in range(n):
        ip = (i + 1) % n
        tris.append((bot[i], top[ip], top[i]))
        tris.append((bot[i], bot[ip], top[ip]))
    return tris


def _strip_open_full_full(bot, top):
    if len(bot) != len(top) or len(bot) < 2:
        return []
    tris = []
    for i in range(len(bot) - 1):
        tris.append((bot[i], bot[i + 1], top[i + 1]))
        tris.append((bot[i], top[i + 1], top[i]))
    return tris


def _strip_closed_full_full(bot, top):
    n = len(bot)
    if n != len(top) or n < 2:
        return []
    tris = []
    for i in range(n):
        ip = (i + 1) % n
        tris.append((bot[i], bot[ip], top[ip]))
        tris.append((bot[i], top[ip], top[i]))
    return tris


def _stagger_for_row(j, v_div):
    if j == 0 or j == v_div:
        return False
    return (j % 2) == 1


def _strip_between(bot_stagger, top_stagger, u_closed):
    if not bot_stagger and top_stagger:
        return _strip_closed_even_to_odd if u_closed else _strip_open_even_to_odd
    if bot_stagger and not top_stagger:
        return _strip_closed_odd_to_even if u_closed else _strip_open_odd_to_even
    if not bot_stagger and not top_stagger:
        return _strip_closed_full_full if u_closed else _strip_open_full_full
    return None


def _triangles_stagger_uv(srf, u_div, v_div, u_closed, u_dom, v_dom, swap_uv):
    rows = []
    for j in range(v_div + 1):
        v = v_dom.ParameterAt(j / float(v_div))
        rows.append(
            _row_points(
                srf,
                u_dom,
                v,
                u_div,
                stagger=_stagger_for_row(j, v_div),
                u_closed=u_closed,
                swap_uv=swap_uv,
            )
        )
    out = []
    for j in range(v_div):
        sb = _stagger_for_row(j, v_div)
        st = _stagger_for_row(j + 1, v_div)
        fn = _strip_between(sb, st, u_closed)
        if fn is None:
            continue
        for a, b, c in fn(rows[j], rows[j + 1]):
            out.append((a, b, c))
    return out


def _triangles_from_surface(srf, u_div, v_div, pattern, swap_in):
    u_div = max(1, int(u_div))
    v_div = max(1, int(v_div))
    swap_uv = _resolve_swap_uv(srf, swap_in)
    u_dom, v_dom = _logical_domains(srf, swap_uv)
    u_closed = _logical_u_closed(srf, swap_uv)

    if pattern == 1:
        # Full U/V: stagger only (no halving) — more panels than Lunchbox-style default.
        tris = _triangles_stagger_uv(srf, u_div, v_div, u_closed, u_dom, v_dom, swap_uv)
    elif pattern == 2:
        # Dense rectangular grid + checkerboard — continuous UV grid lines (often looks “wrong”).
        pts = _grid_points_regular(srf, u_dom, v_dom, u_div, v_div, u_closed, swap_uv)
        tris = _triangles_checkerboard(pts, u_div, v_div, u_closed)
    else:
        # Pattern 0: STAGGERED rows (diagrid look) at Lunchbox-like density.
        # u_half = ceil(U/2) points around; v_strips = V+1 → 2*u_half*(V+1) tris if U is closed.
        nu = _ceil_half_u(u_div)
        nv_strips = v_div + 1
        tris = _triangles_stagger_uv(srf, nu, nv_strips, u_closed, u_dom, v_dom, swap_uv)

    out = []
    for a, b, c in tris:
        brep = _brep_from_triangle(a, b, c)
        if brep is not None:
            out.append(brep)
    return out


srf = _as_surface(Surface)
try:
    _p = Pattern
    _pat = int(_p) if _p is not None else 0
except Exception:
    _pat = 0

try:
    _sw = Swap_UV
except Exception:
    _sw = None

if srf is None:
    P = []
else:
    P = _triangles_from_surface(srf, U_Div, V_Div, _pat, _sw)

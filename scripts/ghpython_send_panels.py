# Paste into a GhPython component (Rhino 7/8 + Grasshopper).
# Sends panel data to POST /api/session. Wind is set only in the web app (Save wind / Calculate).
#
# Production API (hardcoded):
#   https://ml-facade-project-production.up.railway.app
#
# Inputs:
#   Run          — bool (True = send once; use a button/latch to avoid repeat posts)
#   Session_ID   — str, optional (copy from web app). If empty, server returns a new id in Message.
#   Panel_Tree   — DataTree: one branch per panel. Flat list per branch, in this order:
#                    • n edge lengths (floats) — n = 3 for triangle, n = 4 for quad
#                    • 1 normal — Vector3d (outward)
#                    • n vertices — Point3d in order (same n as edges)
#                    • optional trailing Surface / Brep (e.g. trimmed surface) for area check
#                  Legacy: one Python dict per branch with API keys still works.
#
# Outputs:
#   OK           — bool
#   Status       — int HTTP status
#   Message      — str (JSON; includes session_id)

from __future__ import division

import json

try:
    import urllib2 as urllib_request
    import urllib2 as urllib_error
except ImportError:
    import urllib.request as urllib_request
    import urllib.error as urllib_error

try:
    from Grasshopper import DataTree
except ImportError:
    DataTree = None

try:
    import Rhino.Geometry as rg
except ImportError:
    rg = None

# Public Railway URL (no trailing slash)
API_BASE = "https://ml-facade-project-production.up.railway.app"


def _num(x):
    try:
        return float(x)
    except Exception:
        return None


def _vec3_from_normal_item(o):
    """Normal should be Vector3d; accept 3-float list/tuple."""
    if o is None:
        return None
    if rg is not None:
        try:
            if isinstance(o, rg.Vector3d) and o.IsValid:
                return [float(o.X), float(o.Y), float(o.Z)]
        except Exception:
            pass
    xs = _three_floats(o)
    if xs is not None:
        return xs
    return None


def _three_floats(o):
    if o is None:
        return None
    if rg and isinstance(o, rg.Point3d):
        return [float(o.X), float(o.Y), float(o.Z)]
    try:
        if hasattr(o, "__len__") and len(o) >= 3:
            return [float(o[0]), float(o[1]), float(o[2])]
    except Exception:
        pass
    return None


def _point3d_to_list(o):
    if o is None:
        return None
    if rg and isinstance(o, rg.Point3d):
        return [float(o.X), float(o.Y), float(o.Z)]
    return _three_floats(o)


def _area_from_surface_like(o):
    if o is None:
        return None
    n = _num(o)
    if n is not None and n > 0:
        return float(n)
    if rg is None:
        return None
    try:
        if isinstance(o, rg.Brep) and o.Faces.Count > 0:
            mp = rg.AreaMassProperties.Compute(o)
            if mp is not None:
                return float(mp.Area)
        if isinstance(o, rg.Surface):
            mp = rg.AreaMassProperties.Compute(o)
            if mp is not None:
                return float(mp.Area)
    except Exception:
        pass
    return None


def _panel_from_gh_flat_list(items, pid):
    """
    Order: [e0..e_{n-1}] [normal] [v0..v_{n-1}] [optional Surface...]
    n = 3 or 4.
    """
    items = [x for x in items if x is not None]
    if len(items) < 7:
        return None

    i = 0
    edges = []
    while i < len(items):
        f = _num(items[i])
        if f is not None:
            edges.append(f)
            i += 1
        else:
            break

    n_e = len(edges)
    if n_e not in (3, 4):
        return None
    if i >= len(items):
        return None

    normal = _vec3_from_normal_item(items[i])
    if normal is None:
        return None
    i += 1

    verts = []
    for _ in range(n_e):
        if i >= len(items):
            return None
        p = _point3d_to_list(items[i])
        if p is None:
            return None
        verts.append(p)
        i += 1

    area_m2 = None
    while i < len(items):
        a = _area_from_surface_like(items[i])
        if a is not None:
            area_m2 = a
        i += 1

    elev = sum(p[2] for p in verts) / float(len(verts))
    pdat = {
        "id": pid,
        "n_edges": n_e,
        "vertices_m": verts,
        "elevation_m": elev,
        "case": "single_monolithic",
        "support_family": "monolithic_four_sides",
        "duration": "short",
        "lites": [{"glass": "AN", "construction": "monolithic"}],
        "normal": normal,
        "edge_lengths_m": edges,
    }
    if area_m2 is not None:
        pdat["area_m2"] = area_m2
    return pdat


def _panel_dict_from_branch_dict(branch_items):
    if not branch_items:
        return None
    first = branch_items[0]
    if isinstance(first, dict):
        return first
    return None


def _branch_to_panel(items, pid):
    d = _panel_dict_from_branch_dict(items)
    if d is not None:
        if "id" not in d:
            d = dict(d)
            d["id"] = pid
        return d
    p = _panel_from_gh_flat_list(items, pid)
    return p


def main():
    Run = True
    Session_ID = ""
    Panel_Tree = None

    g = globals()
    Run = g.get("Run", Run)
    sid = g.get("Session_ID", Session_ID)
    Session_ID = str(sid).strip() if sid is not None else ""
    Panel_Tree = g.get("Panel_Tree", Panel_Tree)

    if not Run:
        return False, 0, "skipped (Run is False)"

    if Panel_Tree is None:
        return False, 0, "Panel_Tree is empty"

    panels = []
    if DataTree is not None and isinstance(Panel_Tree, DataTree):
        for i in range(Panel_Tree.BranchCount):
            path = Panel_Tree.Path(i)
            path_str = path.ToString()
            pid = path_str.replace("{", "").replace("}", "").replace(" ", "")
            items = list(Panel_Tree.Branch(i))
            pdat = _branch_to_panel(items, pid)
            if pdat is None:
                continue
            panels.append(pdat)
    else:
        return False, 0, "Panel_Tree must be a Grasshopper DataTree"

    if not panels:
        return (
            False,
            0,
            "no panels extracted. Expected each branch: "
            "n edge floats, then normal (Vector3d), then n Point3d, then optional Surface.",
        )

    body = {"panels": panels}
    if Session_ID:
        body["session_id"] = Session_ID

    url = API_BASE + "/api/session"
    data = json.dumps(body).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib_request.urlopen(req, timeout=120)
        status = resp.getcode()
        txt = resp.read().decode("utf-8")
        return True, status, txt
    except urllib_error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return False, e.code, err
    except Exception as ex:
        return False, 0, str(ex)


OK, Status, Message = main()

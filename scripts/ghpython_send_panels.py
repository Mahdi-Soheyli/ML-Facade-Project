# Paste into a GhPython component (Rhino 7/8 + Grasshopper).
# Sends panel data to POST /api/session. Wind is set only in the web app (Save wind / Calculate).
#
# Production API (hardcoded):
#   https://ml-facade-project-production.up.railway.app
#
# Inputs:
#   Run          — bool (True = send once; use a button/latch to avoid repeat posts)
#   Session_ID   — str, optional. Use a unique value per participant (e.g. your name) so sessions
#                  stay independent. If empty, the server creates an id (see Message JSON).
#   Open_Browser — bool (default True). If True and the POST succeeds, opens the dashboard in your
#                  default browser with ?session=… so you can set wind and calculate.
#   Panel_Tree   — DataTree, **Tree access**. One branch per glazing “panel” (any planar face:
#                  Brep face, Surface, etc.—there is no special Panel type in Rhino).
#                  Per branch, in order (no surface here if you use Surface_Tree):
#                    • n edge lengths (floats) — n = 3 triangle, n = 4 quad
#                    • 1 outward normal — Vector3d (or Plane → ZAxis)
#                    • n vertices — Point3d in order
#                    • optional: extra Surface/Brep **in this same branch** for area (legacy)
#                  GH_Point / GH_Vector / GH_Number (.Value) unwrapped automatically.
#   Surface_Tree — optional DataTree, **Tree access**. One branch per panel, parallel to Panel_Tree
#                  (same branch count / order). Typically **one** Brep or Surface per branch; used for
#                  area_m2. Lets you keep messy surface types off the geometry wire.
#                  If omitted, area comes only from trailing geometry in Panel_Tree (legacy).
#                  You may pass a **flat list** of surfaces instead (same order as branches {0},{1},…).
#                  Legacy: one Python dict per branch (full API keys) still works.
#
# Outputs:
#   OK           — bool
#   Status       — int HTTP status
#   Message      — str (JSON; includes session_id)
#   Opened_URL   — str URL opened in the browser, or empty

from __future__ import division

import json
import re
import sys

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
    import System
except ImportError:
    System = None

try:
    import rhinoscriptsyntax as rs
except ImportError:
    rs = None

try:
    import scriptcontext as sc
except ImportError:
    sc = None


def _is_grasshopper_datatree(obj):
    """True for GH DataTree in IronPython and CPython (isinstance(DataTree) often fails in CPython)."""
    if obj is None:
        return False
    try:
        bc = getattr(obj, "BranchCount", None)
        br = getattr(obj, "Branch", None)
        if bc is None or br is None:
            return False
        if callable(bc):
            bc = bc()
        return int(bc) >= 0
    except Exception:
        return False

try:
    import Rhino.Geometry as rg
except ImportError:
    rg = None


def _is_string(s):
    try:
        return isinstance(s, basestring)
    except NameError:
        return isinstance(s, str)


def _parse_brace_triple_string(s):
    """Parse Rhino-style '{x, y, z}' if GH passes a string."""
    if not _is_string(s):
        return None
    m = re.match(
        r"^\s*\{\s*([+-]?(?:\d*\.\d+|\d+(?:\.\d+)?)(?:[eE][+-]?\d+)?)\s*,"
        r"\s*([+-]?(?:\d*\.\d+|\d+(?:\.\d+)?)(?:[eE][+-]?\d+)?)\s*,"
        r"\s*([+-]?(?:\d*\.\d+|\d+(?:\.\d+)?)(?:[eE][+-]?\d+)?)\s*\}\s*$",
        s.strip(),
    )
    if m is None:
        return None
    try:
        return [float(m.group(1)), float(m.group(2)), float(m.group(3))]
    except Exception:
        return None


def _ilist_to_pylist(branch):
    """
    Grasshopper branch data is often IList. In CPython, list(IList) can be empty or wrong;
    use Count + indexer (see McNeel forums / pythonnet).
    """
    if branch is None:
        return []
    out = []
    try:
        n = int(branch.Count)
    except Exception:
        try:
            n = len(branch)
        except Exception:
            n = 0
    for j in range(n):
        try:
            out.append(branch[j])
        except Exception:
            try:
                out.append(branch.get_Item(j))
            except Exception:
                pass
    if out:
        return out
    try:
        return list(branch)
    except Exception:
        return []


def _branch_items_from_tree(tree, index):
    """Items on branch index (same order as Path(index))."""
    try:
        path = tree.Path(index)
        br = tree.Branch(path)
    except Exception:
        try:
            br = tree.Branch(index)
        except Exception:
            return []
    return _ilist_to_pylist(br)


def _gh_unwrap(o):
    """
    Grasshopper often passes GH_Point / GH_Vector / GH_Number (IGH_Goo) with the real
    Rhino type on .Value. isinstance(..., Point3d) fails until unwrapped.
    """
    if o is None:
        return None
    try:
        if hasattr(o, "Value"):
            v = o.Value
            if v is not None:
                return v
    except Exception:
        pass
    return o


def _coerce_guid_geometry(o):
    """
    GhPython can pass referenced Rhino objects as System.Guid instead of real geometry.
    Try to resolve common cases used here: points and Brep/Surface-like geometry.
    """
    if o is None or System is None or rs is None:
        return o
    try:
        if not isinstance(o, System.Guid):
            return o
    except Exception:
        return o

    for fn_name in ("coerce3dpoint", "coercebrep", "coercesurface", "coercegeometry"):
        fn = getattr(rs, fn_name, None)
        if fn is None:
            continue
        try:
            g = fn(o)
            if g is not None:
                return g
        except Exception:
            pass
    return o


def _run_state_key():
    try:
        gid = str(ghenv.Component.InstanceGuid)
    except Exception:
        gid = "ghpython_send_panels"
    return "ml_facade_send_run_state:" + gid


def _is_rising_edge(run_flag):
    """
    Send only once when Run changes False -> True.
    Keeps Grasshopper recomputes from POSTing on every slider move / viewport update.
    """
    if sc is None:
        return bool(run_flag)
    key = _run_state_key()
    prev = bool(sc.sticky.get(key, False))
    curr = bool(run_flag)
    sc.sticky[key] = curr
    return curr and (not prev)


# Public Railway URL (no trailing slash)
API_BASE = "https://ml-facade-project-production.up.railway.app"


def _quote_session(s):
    try:
        from urllib.parse import quote

        return quote(str(s), safe="")
    except ImportError:
        from urllib import quote

        if sys.version_info[0] < 3:
            return quote(str(s).encode("utf-8"))
        return quote(str(s), safe="")


def _open_browser(url):
    if not url:
        return
    try:
        import webbrowser

        webbrowser.open(url)
        return
    except Exception:
        pass
    try:
        import os

        if os.name == "nt":
            os.startfile(url)
    except Exception:
        pass


def _num(x):
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        pass
    u = _gh_unwrap(x)
    if u is not x:
        try:
            return float(u)
        except Exception:
            return None
    if _is_string(x):
        try:
            return float(x.strip())
        except Exception:
            return None
    return None


def _vec3_from_normal_item(o):
    """Normal should be Vector3d; accept 3-float list/tuple, GH_Vector, Plane.ZAxis."""
    o = _gh_unwrap(o)
    o = _coerce_guid_geometry(o)
    if o is None:
        return None
    if rg is not None:
        try:
            if isinstance(o, rg.Vector3d) and o.IsValid:
                return [float(o.X), float(o.Y), float(o.Z)]
            if isinstance(o, rg.Plane):
                z = o.ZAxis
                if z.IsValid:
                    return [float(z.X), float(z.Y), float(z.Z)]
        except Exception:
            pass
    xs = _three_floats(o)
    if xs is not None:
        return xs
    return None


def _three_floats(o):
    if o is None:
        return None
    o = _gh_unwrap(o)
    o = _coerce_guid_geometry(o)
    if rg and isinstance(o, rg.Point3d):
        return [float(o.X), float(o.Y), float(o.Z)]
    if rg and isinstance(o, rg.Vector3d) and getattr(o, "IsValid", True):
        try:
            return [float(o.X), float(o.Y), float(o.Z)]
        except Exception:
            pass
    try:
        if hasattr(o, "__len__") and len(o) >= 3:
            return [float(o[0]), float(o[1]), float(o[2])]
    except Exception:
        pass
    try:
        x = getattr(o, "X", None)
        y = getattr(o, "Y", None)
        z = getattr(o, "Z", None)
        if x is not None and y is not None and z is not None:
            return [float(x), float(y), float(z)]
    except Exception:
        pass
    xs = _parse_brace_triple_string(o) if _is_string(o) else None
    if xs is not None:
        return xs
    return None


def _point3d_to_list(o):
    if o is None:
        return None
    o = _gh_unwrap(o)
    o = _coerce_guid_geometry(o)
    if rg and isinstance(o, rg.Point3d):
        return [float(o.X), float(o.Y), float(o.Z)]
    return _three_floats(o)


def _area_from_surface_like(o):
    if o is None:
        return None
    o = _gh_unwrap(o)
    o = _coerce_guid_geometry(o)
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


def _try_parse_geometry(filt):
    """
    Parse one branch after removing None. Returns (edges, normal, verts, idx_after_verts, filt)
    or None. idx_after_verts indexes filt for optional trailing surfaces.
    """
    if len(filt) < 7:
        return None
    i = 0
    edges = []
    while i < len(filt):
        f = _num(filt[i])
        if f is not None:
            edges.append(f)
            i += 1
        else:
            break
    n_e = len(edges)
    if n_e not in (3, 4):
        return None
    if i >= len(filt):
        return None
    normal = _vec3_from_normal_item(filt[i])
    if normal is None:
        return None
    i += 1
    verts = []
    for _ in range(n_e):
        if i >= len(filt):
            return None
        p = _point3d_to_list(filt[i])
        if p is None:
            return None
        verts.append(p)
        i += 1
    return (edges, normal, verts, i, filt)


def _panel_from_gh_flat_list(items, pid, extra_surface=None):
    """
    Order: [e0..e_{n-1}] [normal] [v0..v_{n-1}] [optional Surface/Brep tail...]
    extra_surface: optional Brep/Surface merged in for area (second input tree).
    """
    filt = [x for x in items if x is not None]
    r = _try_parse_geometry(filt)
    if r is None:
        return None
    edges, normal, verts, idx_after, filt2 = r
    n_e = len(edges)

    area_m2 = None
    if extra_surface is not None:
        area_m2 = _area_from_surface_like(extra_surface)
    if area_m2 is None:
        j = idx_after
        while j < len(filt2):
            a = _area_from_surface_like(filt2[j])
            if a is not None:
                area_m2 = a
            j += 1

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


def _branch_to_panel(items, pid, extra_surface=None):
    d = _panel_dict_from_branch_dict(items)
    if d is not None:
        if "id" not in d:
            d = dict(d)
            d["id"] = pid
        if extra_surface is not None and d.get("area_m2") is None:
            am = _area_from_surface_like(extra_surface)
            if am is not None:
                d = dict(d)
                d["area_m2"] = am
        return d
    return _panel_from_gh_flat_list(items, pid, extra_surface=extra_surface)


def _surface_for_index(Surface_Tree, index):
    """First non-None item on branch index, or list/tuple by index."""
    if Surface_Tree is None:
        return None
    if isinstance(Surface_Tree, (list, tuple)):
        if index < len(Surface_Tree):
            return _gh_unwrap(Surface_Tree[index])
        return None
    if not _is_grasshopper_datatree(Surface_Tree):
        return None
    try:
        bc = int(Surface_Tree.BranchCount)
    except Exception:
        return None
    if index >= bc:
        return None
    try:
        for x in _branch_items_from_tree(Surface_Tree, index):
            if x is not None:
                return _gh_unwrap(x)
    except Exception:
        pass
    return None


def _diagnose_geometry_failure(filt):
    """Human-readable reason _try_parse_geometry failed (filt = raw branch items, may include None)."""
    filt2 = [x for x in filt if x is not None]
    if len(filt2) < 7:
        return "branch has %d non-null items (need >=7 for a triangle)." % len(filt2)
    i = 0
    edges = []
    while i < len(filt2):
        f = _num(filt2[i])
        if f is not None:
            edges.append(f)
            i += 1
        else:
            break
    n_e = len(edges)
    if n_e not in (3, 4):
        t = type(filt2[i]).__name__ if i < len(filt2) else "?"
        return "found %d edge lengths (need 3 or 4); next item index %d type=%s" % (n_e, i, t)
    if i >= len(filt2):
        return "missing normal after edges."
    if _vec3_from_normal_item(filt2[i]) is None:
        t = type(filt2[i]).__name__
        return "normal at index %d not parseable (type=%s)." % (i, t)
    i += 1
    for k in range(n_e):
        if i >= len(filt2):
            return "missing vertex %d of %d." % (k + 1, n_e)
        if _point3d_to_list(filt2[i]) is None:
            return "vertex at index %d not parseable (type=%s)." % (i, type(filt2[i]).__name__)
        i += 1
    return "unknown (logic mismatch)."


def main():
    Run = True
    Open_Browser = True
    Session_ID = ""
    Panel_Tree = None
    Surface_Tree = None

    g = globals()
    Run = g.get("Run", Run)
    Open_Browser = bool(g.get("Open_Browser", Open_Browser))
    sid = g.get("Session_ID", Session_ID)
    Session_ID = str(sid).strip() if sid is not None else ""
    Panel_Tree = g.get("Panel_Tree", Panel_Tree)
    Surface_Tree = g.get("Surface_Tree", Surface_Tree)

    if not Run:
        _is_rising_edge(False)
        return False, 0, "skipped (Run is False)", ""

    if not _is_rising_edge(Run):
        return False, 0, "waiting for Run rising edge (toggle False -> True to send once)", ""

    if Panel_Tree is None:
        return False, 0, "Panel_Tree is empty", ""

    panels = []
    if _is_grasshopper_datatree(Panel_Tree):
        n_br = Panel_Tree.BranchCount
        try:
            n_br = int(n_br)
        except Exception:
            n_br = 0
        for i in range(n_br):
            path = Panel_Tree.Path(i)
            path_str = path.ToString()
            pid = path_str.replace("{", "").replace("}", "").replace(" ", "")
            items = _branch_items_from_tree(Panel_Tree, i)
            extra = _surface_for_index(Surface_Tree, i)
            pdat = _branch_to_panel(items, pid, extra_surface=extra)
            if pdat is None:
                continue
            panels.append(pdat)
    else:
        return (
            False,
            0,
            "Panel_Tree must be a Grasshopper DataTree (right-click Panel_Tree input → Tree access).",
            "",
        )

    if not panels:
        hint = ""
        if _is_grasshopper_datatree(Panel_Tree):
            try:
                z = _branch_items_from_tree(Panel_Tree, 0)
                if len(z) == 0:
                    hint = (
                        " First branch read 0 items via IList index (CPython fix applied in script—"
                        "re-paste latest ghpython_send_panels.py). "
                    )
                else:
                    hint = " First branch: %d items. Parse check: %s" % (
                        len(z),
                        _diagnose_geometry_failure(z),
                    )
            except Exception as ex:
                hint = " (diagnostic failed: %s)" % ex
        msg = (
            "no panels extracted. Each branch: 3–4 edge lengths, 1 normal, 3–4 points; "
            "optional area in-branch or Surface_Tree."
        )
        if hint:
            msg += hint
        msg += " Tree access on Panel_Tree; align Surface_Tree if used."
        return False, 0, msg, ""

    body = {"panels": panels}
    if Session_ID:
        body["session_id"] = Session_ID

    url = API_BASE + "/api/session"
    data = json.dumps(body).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})
    opened = ""
    try:
        resp = urllib_request.urlopen(req, timeout=120)
        status = resp.getcode()
        txt = resp.read().decode("utf-8")
        if Open_Browser and status == 200:
            try:
                j = json.loads(txt)
                sid_final = Session_ID or j.get("session_id", "")
                if sid_final:
                    opened = API_BASE + "/?session=" + _quote_session(sid_final)
                    _open_browser(opened)
            except Exception:
                pass
        return True, status, txt, opened
    except urllib_error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return False, e.code, err, ""
    except Exception as ex:
        return False, 0, str(ex), ""


OK, Status, Message, Opened_URL = main()

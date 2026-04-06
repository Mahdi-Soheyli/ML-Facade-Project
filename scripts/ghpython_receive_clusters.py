# Paste into a GhPython component (Rhino 7/8 + Grasshopper).
# After the web app (or POST /api/session/{id}/calculate), pulls GET /api/session/{id}/results
# and builds DataTrees: one branch per cluster with panel ids, plus colors per branch.
#
# Production API (hardcoded):
#   https://ml-facade-project-production.up.railway.app
#
# Inputs:
#   Run          — bool
#   Session_ID   — str (copy from the web app — same as sender)
#
# Outputs:
#   OK           — bool
#   Status       — int HTTP status
#   Message      — str (raw JSON on success, or error body)
#   Ids_Tree     — DataTree[str]: branch i = list of panel ids in cluster i
#   Colors_Tree  — DataTree[str]: branch i = one color hex for cluster i (same length as Ids_Tree branches)
#   Thickness_mm — DataTree[float]: branch i = Table-4 minimum mm for that cluster (one value per branch)

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
    from Grasshopper.Kernel.Data import GH_Path
except ImportError:
    DataTree = None
    GH_Path = None

API_BASE = "https://ml-facade-project-production.up.railway.app"


def main():
    Run = True
    Session_ID = ""

    g = globals()
    Run = g.get("Run", Run)
    sid = g.get("Session_ID", Session_ID)
    Session_ID = str(sid).strip() if sid is not None else ""

    empty_ids = DataTree() if DataTree else None
    empty_col = DataTree()
    empty_thk = DataTree()

    if not Run:
        return False, 0, "skipped", empty_ids, empty_col, empty_thk

    if not Session_ID:
        return False, 0, "Session_ID is empty (copy from web app)", empty_ids, empty_col, empty_thk

    url = API_BASE + "/api/session/" + Session_ID + "/results"
    req = urllib_request.Request(url)
    try:
        resp = urllib_request.urlopen(req, timeout=120)
        status = resp.getcode()
        txt = resp.read().decode("utf-8")
    except urllib_error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return False, e.code, err, empty_ids, empty_col, empty_thk
    except Exception as ex:
        return False, 0, str(ex), empty_ids, empty_col, empty_thk

    try:
        data = json.loads(txt)
    except Exception:
        return False, status, txt, empty_ids, empty_col, empty_thk

    clusters = data.get("clusters") or []
    ids_tree = DataTree()
    col_tree = DataTree()
    thk_tree = DataTree()

    for c in clusters:
        idx = int(c.get("cluster_index", 0))
        path = GH_Path(idx)
        color = c.get("color_hex") or "#888888"
        thk = c.get("thickness_mm_min")
        for pid in c.get("panel_ids") or []:
            ids_tree.Add(str(pid), path)
        col_tree.Add(str(color), path)
        if thk is not None:
            thk_tree.Add(float(thk), path)

    return True, status, txt, ids_tree, col_tree, thk_tree


OK, Status, Message, Ids_Tree, Colors_Tree, Thickness_mm = main()

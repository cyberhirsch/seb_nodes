"""Every seb_360_*.json loads into a real ComfyUI with no unknown seb node types.

Missing third-party packs are reported but do not fail the test -- that is an
install issue, not a node issue.
"""
import glob
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

from _common import finish, open_app, require_server

require_server()
WF_DIR = os.environ.get("SEB_WORKFLOW_DIR") or r"G:\AI\_Workflows\Utility"
if not os.path.isdir(WF_DIR):
    print(json.dumps({"SKIP": f"no workflow dir {WF_DIR}; set SEB_WORKFLOW_DIR"}))
    sys.exit(2)

LOAD = """
async (wf) => {
  const errs = [];
  const orig = console.error;
  console.error = (...a) => { errs.push(a.map(String).join(' ').slice(0, 140)); orig(...a); };
  try { await window.app.loadGraphData(wf, true, false); } catch (e) { errs.push('load: ' + String(e).slice(0, 140)); }
  await new Promise(r => setTimeout(r, 1500));
  console.error = orig;
  return {count: window.app.graph._nodes.length, errs: errs.slice(0, 5)};
}
"""

rep = {}
with sync_playwright() as pw:
    b, pg = open_app(pw, 1500, 900)
    known = set(pg.evaluate("() => Object.keys(LiteGraph.registered_node_types)"))
    for f in sorted(glob.glob(os.path.join(WF_DIR, "seb_360_*.json"))):
        wf = json.load(open(f, encoding="utf-8"))
        declared = [n["type"] for n in wf["nodes"]]
        unknown = sorted({t for t in declared if t not in known})
        res = pg.evaluate(LOAD, wf)
        rep[os.path.basename(f)] = {
            "nodes": f"{res['count']}/{len(declared)}",
            "unknown_seb_types": [t for t in unknown if "Seb" in t],
            "needs_pack": [t for t in unknown if "Seb" not in t],
            "errors": res["errs"],
            "loads": res["count"] == len(declared),
        }
    b.close()

ok = all(v["loads"] and not v["unknown_seb_types"] for v in rep.values())
finish(rep, ok)

"""Node face: one preview, box follows the framing aspect, editor button visible.

Also checks the wiring: user edits and the editor sync both reach fitPreview.
"""
import os
import time

from playwright.sync_api import sync_playwright

from _common import HERE, PANO, add_read_node, finish, open_app, require_server

require_server()

PROBE = """
() => {
  const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
  const surfaces = [];
  for (const w of (n.widgets || [])) {
    const el = w.element || null;
    if (el && el.tagName === 'CANVAS') surfaces.push(w.name);
    else if (el && el.querySelector && el.querySelector('canvas,img')) surfaces.push(w.name + '/nested');
  }
  const names = ["yaw","pitch","fov","projection","view_width","view_height"];
  const wrapped = names.filter(k => {
    const w = n.widgets.find(x => x.name === k);
    return !!(w && typeof w.callback === "function" && /fitPreview|update\\(\\)/.test(String(w.callback)));
  });
  return {
    widgets: (n.widgets || []).map(w => `${w.type}:${w.name}`),
    surfaces, cutoutSurface: !!n.__panoCutoutNodeSurface, imgs: (n.imgs || []).length,
    wrapped: wrapped.length, syncFits: /fitPreview/.test(String(n.__sebSyncCam || "")),
    size: n.size.slice(),
  };
}
"""
SET_VIEW = """
([vw, vh]) => {
  const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
  n.widgets.find(w => w.name === 'view_width').value = vw;
  n.widgets.find(w => w.name === 'view_height').value = vh;
  n.onResize && n.onResize(n.size);
  n.setDirtyCanvas(true, true);
}
"""
BOX = """() => { const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
  return {w: n.previewCanvas.clientWidth, h: n.previewCanvas.clientHeight}; }"""

rep = {}
with sync_playwright() as pw:
    b, pg = open_app(pw, 1400, 1100)
    add_read_node(pg, PANO, width=400, fov=90, yaw=0, pitch=0)
    time.sleep(4)
    rep["face"] = pg.evaluate(PROBE)
    for name, (vw, vh) in {"square": (1536, 1536), "wide": (1536, 768),
                           "tall": (768, 1536)}.items():
        pg.evaluate(SET_VIEW, [vw, vh])
        time.sleep(1.5)
        box = pg.evaluate(BOX)
        got = box["w"] / box["h"] if box["h"] else 0
        clamped = box["h"] in (96, 480)
        rep[name] = {"box": box, "want": round(vw / vh, 3), "got": round(got, 3),
                     "ok": clamped or abs(got - vw / vh) < 0.06, "clamped": clamped}
        pg.screenshot(path=os.path.join(HERE, f"_face_{name}.png"),
                      clip={"x": 0, "y": 0, "width": 700, "height": 1050})
    b.close()

f = rep["face"]
rep["VERDICT"] = {
    "single_preview_surface": len(f["surfaces"]) == 1,
    "no_core_image_preview": f["imgs"] == 0 and not any("canvas-image-preview" in w for w in f["widgets"]),
    "their_cutout_gone": not f["cutoutSurface"],
    "editor_button_visible": "button:Open Pano Editor" in f["widgets"],
    "aspects_follow": all(rep[k]["ok"] for k in ("square", "wide", "tall")),
    "user_edits_wired": f["wrapped"] == 6,
    "editor_sync_wired": f["syncFits"],
}
finish(rep, all(rep["VERDICT"].values()))

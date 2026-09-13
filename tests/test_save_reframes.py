"""Editor Save -> the node face re-frames, and to the SAME place Python extracts.

Frame yaw +90 / fov 30 in the editor and Save. The node's preview centre must
flip from the RED marker (lon 0) to the GREEN one (lon +90) -- the same marker
test_yaw_truth expects from Python at yaw +90.
"""
import os
import time

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

from _common import (HERE, PANO, add_read_node, editor_save, finish, open_app,
                     open_editor, require_server, set_editor_camera, widget_values)

require_server()


def node_preview_centre(pg, path):
    box = pg.evaluate("""() => { const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
        const r = n.previewCanvas.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; }""")
    pg.screenshot(path=path)
    im = Image.open(path).convert("RGB")
    cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
    r = min(box["w"], box["h"]) * 0.18
    m = ImageStat.Stat(im.crop((int(cx - r), int(cy - r), int(cx + r), int(cy + r)))).mean
    return {"rgb": [round(v, 1) for v in m], "dominant": "RGB"[m.index(max(m))]}


rep = {}
with sync_playwright() as pw:
    b, pg = open_app(pw)
    add_read_node(pg, PANO, width=380, canvas_width=2048, view_width=768, view_height=768,
                  fov=30, yaw=0, pitch=0)
    time.sleep(5)
    rep["before"] = node_preview_centre(pg, os.path.join(HERE, "_reframe_before.png"))
    open_editor(pg)
    set_editor_camera(pg, 90, 0, 30, 30)
    editor_save(pg)
    rep["widgets_after"] = widget_values(pg, "yaw", "pitch", "fov", "view_width", "view_height")
    rep["after"] = node_preview_centre(pg, os.path.join(HERE, "_reframe_after.png"))
    b.close()

rep["VERDICT"] = {
    "widgets_took_camera": rep["widgets_after"]["yaw"] == 90 and rep["widgets_after"]["fov"] == 30,
    "preview_was_on_lon0": rep["before"]["dominant"] == "R",
    "preview_now_on_lon+90": rep["after"]["dominant"] == "G",
}
finish(rep, all(rep["VERDICT"].values()))

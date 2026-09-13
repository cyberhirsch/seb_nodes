"""A mask painted in the editor must reach Python's MASK output.

Paint strokes over the centre of the editor's view (lon 0 / lat 0), Save, and
extract at yaw 0 with mask_mode 'editor': the centre must be white and the
corners black. 'core' must ignore the painting entirely.
"""
import glob
import json
import os
import time

import numpy as np
from playwright.sync_api import sync_playwright

from _common import (INPUT_DIR, PANO, add_read_node, editor_canvas_box, editor_save,
                     finish, forget, open_app, open_editor, require_server, state_json,
                     view_mask)

require_server()
forget(PANO)
UP = os.path.join(INPUT_DIR, "panorama_stickers")

rep = {}
with sync_playwright() as pw:
    b, pg = open_app(pw)
    add_read_node(pg, PANO, canvas_width=2048)
    time.sleep(3)
    open_editor(pg)
    pg.locator('button[aria-label="Mask"]').first.click()
    time.sleep(1.5)
    box = editor_canvas_box(pg)
    cx, cy = box["x"] + box["w"] * 0.5, box["y"] + box["h"] * 0.5
    for row in range(5):
        y = cy - 40 + row * 20
        pg.mouse.move(cx - 150, y)
        pg.mouse.down()
        for i in range(1, 31):
            pg.mouse.move(cx - 150 + i * 10, y, steps=2)
        pg.mouse.up()
        time.sleep(0.3)
    time.sleep(1.5)
    editor_save(pg, wait=9)             # close -> rasterise -> upload -> state rewrite
    st = state_json(pg)
    b.close()

j = json.loads(st)
rep["mask_strokes_in_state"] = len((((j.get("painting") or {}).get("mask") or {}).get("strokes")) or [])
rep["painting_layer"] = j.get("painting_layer")
rep["uploaded"] = sorted(os.path.basename(p) for p in glob.glob(os.path.join(UP, "pano_mask_*.png")))

CAM = dict(yaw=0.0, pitch=0.0, fov=60.0, w=512, h=512, margin=0.0, state_json=st)
ed = view_mask(mask_mode="editor", **CAM)
core = view_mask(mask_mode="core", **CAM)
h, w = ed.shape
rep["editor_centre"] = round(float(ed[h // 2 - 10:h // 2 + 10, w // 2 - 10:w // 2 + 10].mean()), 3)
rep["editor_corner"] = round(float(ed[:20, :20].mean()), 3)
rep["editor_coverage_pct"] = round(float((ed > 0.5).mean() * 100), 2)
rep["core_min"] = round(float(core.min()), 3)

rep["VERDICT"] = {
    "editor_uploaded_a_mask": bool(rep["painting_layer"] and rep["painting_layer"].get("mask")),
    "python_mask_white_where_painted": rep["editor_centre"] > 0.6,
    "python_mask_black_elsewhere": rep["editor_corner"] < 0.05,
    "core_mode_ignores_painting": rep["core_min"] > 0.99,
}
forget(PANO)
finish(rep, all(rep["VERDICT"].values()))

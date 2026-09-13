"""Typing a camera on the node must survive the editor writing state_json.

The editor seeds a default frame and rewrites state_json on unrelated changes;
without the push-back sync that stamped 42/0/0 over whatever was typed.
"""
import json
import time

from playwright.sync_api import sync_playwright

from _common import PANO, add_read_node, finish, open_app, require_server, set_widget

require_server()

SNAP = """() => {
  const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
  const g = k => n.widgets.find(w => w.name === k).value;
  let sh = null; try { sh = (JSON.parse(g('state_json') || '{}').shots || [])[0] || null; } catch (e) {}
  return {fov: g('fov'), yaw: g('yaw'), pitch: g('pitch'),
          shot: sh && {yaw: sh.yaw_deg, pitch: sh.pitch_deg, h: sh.hFOV_deg, v: sh.vFOV_deg}}; }"""
TOUCH = """() => {
  const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
  const w = n.widgets.find(x => x.name === 'state_json');
  const st = JSON.parse(w.value); st.output_preset = 4096; w.value = JSON.stringify(st); }"""

rep = {}
with sync_playwright() as pw:
    b, pg = open_app(pw)
    add_read_node(pg, PANO)
    time.sleep(3)                       # editor seeds its default frame
    rep["seeded"] = pg.evaluate(SNAP)
    for k, v in (("fov", 90), ("yaw", 35), ("pitch", -20)):
        set_widget(pg, k, v)
    time.sleep(3)                       # push-back has had its 200ms
    rep["after_typing"] = pg.evaluate(SNAP)
    pg.evaluate(TOUCH)                  # something else rewrites state_json
    time.sleep(2)
    rep["after_state_rewrite"] = pg.evaluate(SNAP)
    b.close()

a, t = rep["after_state_rewrite"], rep["after_typing"]
rep["VERDICT"] = {
    "seeded_a_frame": bool(rep["seeded"]["shot"]),
    "typed_values_pushed_into_state": t["shot"] and t["shot"]["yaw"] == 35 and t["shot"]["h"] == 90,
    "typed_values_survive_rewrite": a["fov"] == 90 and a["yaw"] == 35 and a["pitch"] == -20,
}
finish(rep, all(rep["VERDICT"].values()))

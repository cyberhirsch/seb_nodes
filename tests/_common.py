"""Shared plumbing for the 360 tests.

All tests drive a real headless Chromium against a running ComfyUI. The embedded
browser pane does not composite (requestAnimationFrame never fires), so nothing
here works through it -- start a scratch instance and point SEB_PORT at it.

Environment:
  SEB_PORT          port of the scratch ComfyUI (default 8189; PANO_PORT also read)
  SEB_INPUT_DIR     that instance's input directory (default: ../../../input from
                    this folder, i.e. the ComfyUI this pack is installed in)
  SEB_WORKFLOW_DIR  where the seb_360_*.json workflows live (workflow test only)
"""
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("SEB_PORT") or os.environ.get("PANO_PORT") or "8189")
BASE = f"http://127.0.0.1:{PORT}"
INPUT_DIR = os.environ.get("SEB_INPUT_DIR") or os.path.normpath(
    os.path.join(HERE, "..", "..", "..", "input"))
PANO = "seb_360_testpano.png"      # marker panorama, see make_testpano.py
PANO_B = "seb_360_testpano_b.png"  # a visibly different one, for swap tests

LAUNCH_ARGS = [
    "--use-gl=swiftshader", "--enable-unsafe-swiftshader",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
]


# --------------------------------------------------------------------------- HTTP
def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=60))


def server_up(timeout=5):
    try:
        urllib.request.urlopen(BASE + "/system_stats", timeout=timeout)
        return True
    except Exception:
        return False


def forget(pano_id):
    """Drop the store entry so a test starts from the file on disk."""
    return post("/seb/360/forget", {"id": pano_id})


def read_node(image=PANO, yaw=0.0, pitch=0.0, fov=30.0, w=512, h=512,
              mask_mode="core", margin=0.0, state_json="", canvas=2048,
              projection="perspective"):
    return {"class_type": "Read360Seb", "inputs": {
        "image": image, "projection": projection, "yaw": yaw, "pitch": pitch,
        "fov": fov, "view_width": w, "view_height": h, "mask_mode": mask_mode,
        "margin_deg": margin, "coverage": "360", "state_json": state_json,
        "canvas_width": canvas}}


def run_prompt(prompt, want_node=None, timeout=90):
    """Queue a prompt; return the history entry (or that node's first image meta)."""
    pid = post("/prompt", {"prompt": prompt, "client_id": "seb_tests"})["prompt_id"]
    for _ in range(int(timeout * 2)):
        h = get("/history/" + pid)
        entry = h.get(pid)
        if entry:                                   # in the history = finished, success or not
            status = entry.get("status") or {}
            if status.get("status_str") != "success":
                msg = ""
                for m in status.get("messages") or []:
                    if isinstance(m, list) and len(m) > 1 and m[0] == "execution_error":
                        msg = str((m[1] or {}).get("exception_message", ""))
                raise RuntimeError(f"prompt failed: {msg or status}")
            if want_node is None:
                return entry
            imgs = (entry["outputs"].get(want_node) or {}).get("images") or []
            if imgs:
                return imgs[0]
            raise RuntimeError(f"node {want_node} produced no image")
        time.sleep(0.5)
    raise RuntimeError("prompt timed out")


def fetch_image(meta):
    q = urllib.parse.urlencode({"filename": meta["filename"],
                                "subfolder": meta.get("subfolder", ""),
                                "type": meta.get("type", "temp")})
    raw = urllib.request.urlopen(f"{BASE}/view?{q}", timeout=60).read()
    return Image.open(io.BytesIO(raw))


def view_rgb(image=PANO, **kw):
    """Extract a view through the API and return it as an RGB PIL image."""
    p = {"1": read_node(image, **kw),
         "2": {"class_type": "PreviewImage", "inputs": {"images": ["1", 0]}}}
    return fetch_image(run_prompt(p, "2")).convert("RGB")


def view_mask(image=PANO, **kw):
    """Extract a view's MASK through the API, as a float array 0..1."""
    import numpy as np
    p = {"1": read_node(image, **kw),
         "2": {"class_type": "MaskToImage", "inputs": {"mask": ["1", 1]}},
         "3": {"class_type": "PreviewImage", "inputs": {"images": ["2", 0]}}}
    im = fetch_image(run_prompt(p, "3")).convert("L")
    return np.asarray(im, dtype=np.float32) / 255.0


# ------------------------------------------------------------------------ pixels
def centre_stats(im, frac=0.2):
    """Mean RGB of the central `frac` of an image, plus which channel dominates."""
    w, h = im.size
    box = (int(w * (0.5 - frac / 2)), int(h * (0.5 - frac / 2)),
           int(w * (0.5 + frac / 2)), int(h * (0.5 + frac / 2)))
    m = ImageStat.Stat(im.crop(box)).mean[:3]
    return {"rgb": [round(v, 1) for v in m], "dominant": "RGB"[m.index(max(m))]}


def delta(a, b):
    return round(sum(abs(x - y) for x, y in zip(a, b)), 1)


# ----------------------------------------------------------------------- browser
def open_app(pw, width=1600, height=1000):
    """Launch headless Chromium on the app; returns (browser, page)."""
    b = pw.chromium.launch(headless=True, args=LAUNCH_ARGS)
    pg = b.new_page(viewport={"width": width, "height": height})
    pg.goto(BASE, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_function("() => !!(window.app && window.app.graph)", timeout=90000)
    time.sleep(3)
    return b, pg


def add_read_node(pg, image=PANO, preview=None, width=None, **widgets):
    """Clear the graph, add a Read360Seb; `preview` = output slot to wire to a PreviewImage."""
    return pg.evaluate("""([image, widgets, preview, width]) => {
      const app = window.app; app.graph.clear();
      const n = LiteGraph.createNode("Read360Seb"); app.graph.add(n); n.pos = [30, 30];
      if (width) n.size = [width, n.size[1]];
      const g = k => n.widgets.find(w => w.name === k);
      g("image").value = image;
      for (const [k, v] of Object.entries(widgets)) { const w = g(k); if (w) w.value = v; }
      if (preview !== null && preview !== undefined) {
        const p = LiteGraph.createNode("PreviewImage"); app.graph.add(p); p.pos = [560, 30];
        n.connect(preview, p, 0);
      }
      app.graph.setDirtyCanvas(true, true);
      return n.id;
    }""", [image, widgets, preview, width])


def widget_values(pg, *names):
    return pg.evaluate("""(names) => {
      const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
      const out = {};
      for (const k of names) { const w = n.widgets.find(x => x.name === k); out[k] = w ? w.value : null; }
      return out;
    }""", list(names))


def set_widget(pg, name, value, fire_callback=True):
    """Set a widget the way a user edit does: value, then its callback."""
    pg.evaluate("""([k, v, fire]) => {
      const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
      const w = n.widgets.find(x => x.name === k); w.value = v;
      if (fire) { try { w.callback && w.callback(v); } catch (e) { /* frontend cb wants more args */ } }
    }""", [name, value, fire_callback])


def queue(pg, wait=10):
    pg.evaluate("async () => { await window.app.queuePrompt(0, 1); }")
    time.sleep(wait)


def open_editor(pg, wait=7):
    pg.evaluate("""() => {
      const n = window.app.graph._nodes.find(x => x.type === 'Read360Seb');
      const b = n.widgets.find(w => /Open Pano Editor/.test(w.name || ''));
      b && b.callback && b.callback();
    }""")
    time.sleep(wait)


def editor_open(pg):
    return pg.evaluate("() => document.querySelectorAll('[class*=\"pano\"]').length > 50")


def set_editor_camera(pg, yaw, pitch, hfov, vfov):
    """Fill the Transform panel; adds a frame first if the state has none."""
    add = pg.get_by_role("button", name="Add Frame")
    if add.count() and add.first.is_visible():
        add.first.click()
        time.sleep(2)
    for key, val in {"yaw_deg": yaw, "pitch_deg": pitch,
                     "hFOV_deg": hfov, "vFOV_deg": vfov}.items():
        el = pg.locator(
            f'input[data-param-key="{key}"][data-input-kind="number"]:not([disabled])').first
        el.scroll_into_view_if_needed()
        el.fill(str(val))
        el.press("Enter")
        el.dispatch_event("change")
        el.blur()
        time.sleep(0.5)


def editor_save(pg, wait=6):
    pg.get_by_role("button", name="Save", exact=True).last.click()
    time.sleep(wait)


def editor_cancel(pg, wait=2):
    pg.get_by_role("button", name="Cancel", exact=True).last.click()
    time.sleep(wait)


def editor_canvas_box(pg):
    return pg.evaluate("""() => {
      const cs = [...document.querySelectorAll('canvas')].filter(c => c.width > 600 && c.height > 400);
      cs.sort((a, b) => b.width * b.height - a.width * a.height);
      const r = cs[0].getBoundingClientRect();
      return {x: r.x, y: r.y, w: r.width, h: r.height};
    }""")


def state_json(pg):
    return pg.evaluate("""() => window.app.graph._nodes.find(x => x.type === 'Read360Seb')
        .widgets.find(w => w.name === 'state_json').value""")


def screenshot_stats(pg, path, box):
    pg.screenshot(path=path)
    im = Image.open(path).convert("RGB").crop(box)
    s = ImageStat.Stat(im)
    return {"mean": [round(v, 1) for v in s.mean], "stddev": [round(v, 1) for v in s.stddev]}


# ------------------------------------------------------------------------ result
def finish(report, ok):
    report["PASS"] = bool(ok)
    print(json.dumps(report, indent=1, default=str))
    sys.exit(0 if ok else 1)


def require_server():
    if not server_up():
        print(json.dumps({"SKIP": f"no ComfyUI on {BASE}; see tests/README.md"}))
        sys.exit(2)

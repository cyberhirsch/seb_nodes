"""Full autonomous round trip:
   run node -> open editor -> Add Frame -> set camera -> Save -> node widgets follow.
"""
import json, os, time
from playwright.sync_api import sync_playwright

PORT = int(os.environ.get("PANO_PORT", "8189"))
OUT = os.path.dirname(os.path.abspath(__file__))
WANT = {"yaw_deg": "113", "pitch_deg": "-27", "hFOV_deg": "64", "vFOV_deg": "40"}

READ = """
() => {
  const n = window.app.graph._nodes.find(x=>x.type==='Read360Seb');
  const g = k => n.widgets.find(w=>w.name===k);
  let shot=null;
  try {
    const st=JSON.parse(g("state_json").value||"{}");
    const shots=st.shots||[];
    const sel=st.active && st.active.selected_shot_id;
    shot=shots.find(s=>s&&s.id===sel)||shots[0]||null;
  } catch(e){}
  return {yaw:g("yaw").value, pitch:g("pitch").value, fov:g("fov").value,
          view_w:g("view_width").value, view_h:g("view_height").value,
          shot: shot && {yaw:shot.yaw_deg,pitch:shot.pitch_deg,h:shot.hFOV_deg,v:shot.vFOV_deg}};
}
"""

def main():
    rep = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=[
            "--use-gl=swiftshader", "--enable-unsafe-swiftshader",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding", "--disable-background-timer-throttling"])
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        pg.goto(f"http://127.0.0.1:{PORT}", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_function("() => !!(window.app && window.app.graph)", timeout=90000)
        time.sleep(3)

        pg.evaluate("""async () => {
          const app=window.app; app.graph.clear();
          const n=LiteGraph.createNode("Read360Seb"); app.graph.add(n); n.pos=[40,40];
          const p=LiteGraph.createNode("PreviewImage"); app.graph.add(p); p.pos=[620,40];
          n.connect(0,p,0);
          const g=k=>n.widgets.find(w=>w.name===k);
          g("image").value="seb_360_testpano.png"; g("canvas_width").value=2048;
          g("view_width").value=768; g("view_height").value=768;
          g("fov").value=90; g("yaw").value=0; g("pitch").value=0; g("state_json").value="";
          await app.queuePrompt(0,1);}""")
        time.sleep(9)
        rep["before"] = pg.evaluate(READ)

        pg.evaluate("""() => {const n=window.app.graph._nodes.find(x=>x.type==='Read360Seb');
          const b=n.widgets.find(w=>/Open Pano Editor/.test(w.name||'')); b&&b.callback&&b.callback();}""")
        time.sleep(6)

        pg.get_by_role("button", name="Add Frame").first.click()
        time.sleep(2)
        rep["frame_added"] = True

        for key, val in WANT.items():
            el = pg.locator(
                f'input[data-param-key="{key}"][data-input-kind="number"]:not([disabled])').first
            el.scroll_into_view_if_needed()
            el.fill(val)
            el.press("Enter")
            el.dispatch_event("change")
            el.blur()
            time.sleep(0.6)
        rep["editor_values"] = {
            k: pg.locator(f'input[data-param-key="{k}"][data-input-kind="number"]').first.input_value()
            for k in WANT}

        pg.screenshot(path=os.path.join(OUT, "pano_framed.png"))
        pg.get_by_role("button", name="Save", exact=True).last.click()
        time.sleep(5)
        rep["after"] = pg.evaluate(READ)
        pg.screenshot(path=os.path.join(OUT, "pano_after_save.png"))
        b.close()

    a = rep.get("after") or {}
    v = {"shot_written": bool(a.get("shot")),
         "yaw_113": a.get("yaw") == 113.0,
         "pitch_-27": a.get("pitch") == -27.0,
         "fov_64": a.get("fov") == 64.0}
    # vFOV 40 with hFOV 64 -> aspect 1.712 -> height = 768/1.712 rounded to /8
    import math
    asp = math.tan(math.radians(64)/2)/math.tan(math.radians(40)/2)
    v["view_height_follows_aspect"] = a.get("view_h") == max(64, round(768/asp/8)*8)
    v["all"] = all(v.values())
    rep["VERDICT"] = v
    rep["expected_height"] = max(64, round(768/asp/8)*8)
    print(json.dumps(rep, indent=1))
    import sys
    sys.exit(0 if v["all"] else 1)


if __name__ == "__main__":
    main()

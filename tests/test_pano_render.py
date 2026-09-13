"""Autonomous end-to-end check of Read360Seb + the vendored Pano Editor.

Runs headless Chromium (which actually composites, unlike the embedded pane, so
requestAnimationFrame fires and the editor paints), builds a graph, executes it,
opens the editor and measures whether the panorama is really on screen.
"""
import json, sys, time, os
from playwright.sync_api import sync_playwright

PORT = int(os.environ.get("PANO_PORT", "8189"))
URL = f"http://127.0.0.1:{PORT}"
OUT = os.path.dirname(os.path.abspath(__file__))
IMAGE = os.environ.get("PANO_IMAGE", "seb_360_testpano.png")

BUILD = """
async ({image}) => {
  const app = window.app;
  app.graph.clear();
  const n = LiteGraph.createNode("Read360Seb"); app.graph.add(n); n.pos=[40,40];
  const p = LiteGraph.createNode("PreviewImage"); app.graph.add(p); p.pos=[620,40];
  n.connect(0, p, 0);
  const g = k => n.widgets.find(w => w.name === k);
  g("image").value = image;
  g("canvas_width").value = 2048;
  g("view_width").value = 768; g("view_height").value = 768;
  g("fov").value = 60; g("yaw").value = 0; g("pitch").value = 0;
  app.graph.setDirtyCanvas(true, true);
  await app.queuePrompt(0, 1);
  return {nodeId: n.id};
}
"""

SAMPLE = """
() => {
  const out = [];
  for (const c of document.querySelectorAll('canvas')) {
    if (c.width < 200 || c.height < 150) continue;
    let mean = null, mode = '';
    try {
      const g2 = c.getContext('2d');
      if (g2) {
        mode = '2d';
        const w = Math.min(120, c.width), h = Math.min(120, c.height);
        const d = g2.getImageData((c.width-w)>>1, (c.height-h)>>1, w, h).data;
        let s = 0, n = 0;
        for (let i = 0; i < d.length; i += 4) { s += d[i]+d[i+1]+d[i+2]; n += 3; }
        mean = +(s/n).toFixed(1);
      }
    } catch (e) { mode = 'err'; }
    if (mean === null) {
      const gl = c.getContext('webgl2') || c.getContext('webgl');
      if (gl) {
        mode = 'webgl';
        const px = new Uint8Array(4*400);
        gl.readPixels((c.width>>1)-10, (c.height>>1)-10, 20, 20, gl.RGBA, gl.UNSIGNED_BYTE, px);
        let s=0,n=0; for (let i=0;i<px.length;i+=4){s+=px[i]+px[i+1]+px[i+2];n+=3;}
        mean = +(s/n).toFixed(1);
      }
    }
    out.push({w:c.width, h:c.height, mode, mean});
  }
  return out;
}
"""

def main():
    report = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=[
            "--use-gl=swiftshader", "--enable-unsafe-swiftshader",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
        ])
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        logs = []
        pg.on("console", lambda m: logs.append(f"{m.type}: {m.text[:160]}"))
        pg.on("pageerror", lambda e: logs.append(f"pageerror: {str(e)[:160]}"))

        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_function("() => !!(window.app && window.app.graph)", timeout=90000)
        time.sleep(3)

        report["build"] = pg.evaluate(BUILD, {"image": IMAGE})
        # wait for execution to land
        for _ in range(60):
            got = pg.evaluate("(id)=>{const o=window.app.nodeOutputs||{};return o[id]||o[String(id)]||null;}",
                              report["build"]["nodeId"])
            if got:
                report["executed"] = {k: got[k] for k in got if k != "images"}
                break
            time.sleep(1)
        else:
            report["executed"] = None

        report["before_editor"] = pg.evaluate(SAMPLE)
        pg.screenshot(path=os.path.join(OUT, "pano_node.png"))

        pg.evaluate("""() => {
            const n = window.app.graph._nodes.find(x=>x.type==='Read360Seb');
            const b = n.widgets.find(w=>/Open Pano Editor/.test(w.name||''));
            if (b && b.callback) b.callback();
        }""")
        time.sleep(7)

        report["editor_open"] = pg.evaluate(
            "() => document.querySelectorAll('[class*=\"pano\"]').length > 50")
        report["after_editor"] = pg.evaluate(SAMPLE)
        pg.screenshot(path=os.path.join(OUT, "pano_editor.png"))
        report["console_tail"] = logs[-8:]
        b.close()

    lit = [c for c in report.get("after_editor", []) if (c.get("mean") or 0) > 8]
    report["VERDICT_editor_shows_content"] = bool(lit)
    report["lit_canvases"] = lit
    print(json.dumps(report, indent=1)[:2600])
    sys.exit(0 if report["VERDICT_editor_shows_content"] else 1)


if __name__ == "__main__":
    main()

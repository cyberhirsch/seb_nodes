"""The editor must show the panorama on a graph that has never been run,
and follow an image swap without a run in between.
"""
import os
import time

from playwright.sync_api import sync_playwright

from _common import (HERE, PANO, PANO_B, add_read_node, delta, editor_cancel, finish,
                     open_app, open_editor, require_server, screenshot_stats, set_widget)

require_server()
CENTRE = (450, 250, 1250, 750)   # the editor's main canvas, at 1600x1000

rep = {}
with sync_playwright() as pw:
    b, pg = open_app(pw)
    add_read_node(pg, PANO, canvas_width=2048)
    time.sleep(3)
    open_editor(pg)
    rep["fresh"] = screenshot_stats(pg, os.path.join(HERE, "_editor_fresh.png"), CENTRE)
    editor_cancel(pg)
    set_widget(pg, "image", PANO_B)
    time.sleep(3)
    open_editor(pg)
    rep["after_swap"] = screenshot_stats(pg, os.path.join(HERE, "_editor_swapped.png"), CENTRE)
    b.close()

rep["swap_delta"] = delta(rep["fresh"]["mean"], rep["after_swap"]["mean"])
rep["VERDICT"] = {
    "shows_content_without_a_run": max(rep["fresh"]["stddev"]) > 30,
    "follows_image_swap": rep["swap_delta"] > 25,
}
finish(rep, all(rep["VERDICT"].values()))

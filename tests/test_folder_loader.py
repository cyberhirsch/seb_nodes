"""Load Images From Folder (Seb), both modes.

'one per run' (the loop): one prompt is queued with index 0; the node must
process image 0, then queue index 1 itself once that run has finished, and so
on, stopping cleanly after the last image -- each file on disk before the next
starts. Also: an interrupted/failed run must NOT queue the next one.

'all in one run' (list mode): every image in a single run; source names kept;
alpha -> mask; non-images ignored; chunking; unchanged folder is cached.
"""
import glob
import json
import os
import shutil
import tempfile
import time
import urllib.request

import numpy as np
from PIL import Image, ImageDraw

from _common import BASE, finish, get, post, require_server, run_prompt

require_server()

ROOT = tempfile.mkdtemp(prefix="seb_folder_")
IN, OUT = os.path.join(ROOT, "in"), os.path.join(ROOT, "out")
os.makedirs(IN)
os.makedirs(OUT)

im = Image.new("RGB", (640, 480), (200, 60, 60))
ImageDraw.Draw(im).text((20, 20), "one", fill=(255, 255, 255))
im.save(os.path.join(IN, "a_photo 01.jpg"), quality=90)
ramp = np.zeros((200, 300, 4), np.uint8)
ramp[..., :3] = (60, 200, 60)
ramp[..., 3] = np.tile(np.linspace(0, 255, 300).astype(np.uint8), (200, 1))
Image.fromarray(ramp, "RGBA").save(os.path.join(IN, "b_alpha.png"))
Image.new("RGB", (512, 512), (60, 60, 200)).save(os.path.join(IN, "c_third.png"))
open(os.path.join(IN, "notes.txt"), "w").write("not an image\n")


def prompt(sub, mode="all in one run", index=0, start=0, limit=0, masks=True):
    p = {
        "1": {"class_type": "LoadImagesFromFolderSeb", "inputs": {
            "folder": IN, "mode": mode, "index": index,
            "extensions": "png,jpg,jpeg,webp", "include_subfolders": False,
            "sort_by": "name", "start_index": start, "limit": limit}},
        "2": {"class_type": "SaveImageSeb", "inputs": {
            "images": ["1", 0], "base_output_folder": OUT, "subfolder_pattern": sub,
            "filename_core": ["1", 2], "filename_separator": "_",
            "include_timestamp_in_filename": False, "counter_digits": 5,
            "save_workflow_data": False, "overwrite_existing": False}},
    }
    if masks:
        p["3"] = {"class_type": "MaskToImage", "inputs": {"mask": ["1", 1]}}
        p["4"] = {"class_type": "SaveImageSeb", "inputs": {
            "images": ["3", 0], "base_output_folder": OUT, "subfolder_pattern": sub + "_mask",
            "filename_core": ["1", 2], "filename_separator": "_",
            "include_timestamp_in_filename": False, "counter_digits": 5,
            "save_workflow_data": False, "overwrite_existing": False}}
    return p


def saved(sub):
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(OUT, sub, "*.png")))


def history_count():
    return len(get("/history"))


def wait_until(pred, timeout, step=0.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(step)
    return pred()


rep = {}
try:
    # ---------------------------------------------------------------- list mode
    run_prompt(prompt("list"))
    rep["list_files"] = saved("list")
    rep["list_masks"] = saved("list_mask")
    rep["list_sizes"] = {f: Image.open(os.path.join(OUT, "list", f)).size for f in rep["list_files"]}
    m = np.asarray(Image.open(os.path.join(OUT, "list_mask", "b_alpha_00001.png")).convert("L"),
                   dtype=np.float32) / 255.0
    rep["b_alpha_mask"] = {"left": round(float(m[:, :10].mean()), 2),
                           "right": round(float(m[:, -10:].mean()), 2)}
    run_prompt(prompt("list"))                       # unchanged folder -> cached
    rep["list_files_after_rerun"] = saved("list")
    run_prompt(prompt("chunk", start=1, limit=1))
    rep["chunk_files"] = saved("chunk")

    # ---------------------------------------------------------------- loop mode
    before = history_count()
    t0 = time.time()
    first = post("/prompt", {"prompt": prompt("loop", mode="one per run", index=0, masks=False),
                             "client_id": "seb_tests"})["prompt_id"]
    # the loop is done when three files exist and nothing more arrives for a while
    wait_until(lambda: len(saved("loop")) >= 3, timeout=90)
    settled_at = len(saved("loop"))
    time.sleep(6)
    rep["loop_files"] = saved("loop")
    rep["loop_extra_after_settle"] = len(saved("loop")) - settled_at
    rep["loop_runs_queued"] = history_count() - before
    rep["loop_seconds"] = round(time.time() - t0, 1)
    # order: each file must have been written after the previous one (sequential)
    times = [os.path.getmtime(os.path.join(OUT, "loop", f)) for f in rep["loop_files"]]
    rep["loop_sequential"] = all(b >= a for a, b in zip(times, times[1:]))

    # a run that does not succeed must not continue the chain. Core SaveImage
    # refuses a prefix that escapes the output folder and raises, so run 0
    # ends in error -- index 1 must then never be queued.
    before = history_count()
    bad = prompt("loopfail", mode="one per run", index=0, masks=False)
    bad["2"] = {"class_type": "SaveImage", "inputs": {
        "images": ["1", 0], "filename_prefix": "../../seb_escape_test"}}
    bad_id = post("/prompt", {"prompt": bad, "client_id": "seb_tests"})["prompt_id"]
    wait_until(lambda: history_count() - before >= 1, timeout=60)
    time.sleep(6)                                     # room for a wrongly queued index 1
    rep["failed_run_chain_runs"] = history_count() - before
    rep["failed_run_status"] = ((get("/history/" + bad_id).get(bad_id) or {})
                                .get("status", {}).get("status_str"))

    # past the end: a clear error, nothing saved
    try:
        run_prompt(prompt("past", mode="one per run", index=99, masks=False))
        rep["past_end"] = "ran?!"
    except RuntimeError as exc:
        rep["past_end"] = str(exc)[:160]
finally:
    shutil.rmtree(ROOT, ignore_errors=True)

want = ["a_photo 01_00001.png", "b_alpha_00001.png", "c_third_00001.png"]
rep["VERDICT"] = {
    # list mode
    "list_three_saved_with_source_names": rep.get("list_files") == want,
    "list_non_image_ignored": "notes_00001.png" not in rep.get("list_files", []),
    "list_sizes_kept": rep.get("list_sizes", {}).get("a_photo 01_00001.png") == (640, 480),
    "list_alpha_became_inverted_mask": rep.get("b_alpha_mask", {}).get("left", 0) > 0.9
                                       and rep.get("b_alpha_mask", {}).get("right", 1) < 0.1,
    "list_unchanged_folder_is_cached": rep.get("list_files_after_rerun") == want,
    "list_chunking": rep.get("chunk_files") == ["b_alpha_00001.png"],
    # loop mode
    "loop_processed_all_three": rep.get("loop_files") == want,
    "loop_one_run_per_image": rep.get("loop_runs_queued") == 3,
    "loop_stops_after_last": rep.get("loop_extra_after_settle") == 0,
    "loop_is_sequential": bool(rep.get("loop_sequential")),
    "failed_run_does_not_continue": rep.get("failed_run_chain_runs") == 1,
    "past_end_is_a_clear_error": "index" in str(rep.get("past_end", "")).lower(),
}
finish(rep, all(rep["VERDICT"].values()))

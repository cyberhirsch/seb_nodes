"""Save Image (Seb) source modes, fed by Load Images From Folder's `path`.

same folder as source: PNG lands next to the original, named after it plus the
suffix, and never over it -- even for a PNG source with overwrite on and no
suffix. replace source file: the original is overwritten in place, same name
and format (a JPEG stays a JPEG); proven by halving the image first and
checking the file's size changed. ignore source: unchanged behaviour.
"""
import os
import shutil
import tempfile

from PIL import Image

from _common import finish, require_server, run_prompt

require_server()

ROOT = tempfile.mkdtemp(prefix="seb_srcmode_")
IN, OUT = os.path.join(ROOT, "in"), os.path.join(ROOT, "out")
os.makedirs(IN)
os.makedirs(OUT)
Image.new("RGB", (640, 480), (200, 60, 60)).save(os.path.join(IN, "photo 01.jpg"), quality=90)
Image.new("RGB", (300, 200), (60, 200, 60)).save(os.path.join(IN, "shot.png"))
Image.new("RGB", (256, 256), (60, 60, 200)).save(os.path.join(IN, "clip.webp"), quality=90)


def prompt(mode, suffix="", overwrite=False, scale=1.0):
    p = {
        "1": {"class_type": "LoadImagesFromFolderSeb", "inputs": {
            "folder": IN, "mode": "all in one run", "index": 0,
            "extensions": "png,jpg,jpeg,webp", "include_subfolders": False,
            "sort_by": "name", "start_index": 0, "limit": 0}},
        "2": {"class_type": "ImageScaleBy", "inputs": {
            "image": ["1", 0], "upscale_method": "area", "scale_by": scale}},
        "3": {"class_type": "SaveImageSeb", "inputs": {
            "images": ["2", 0], "base_output_folder": OUT, "subfolder_pattern": "default",
            "filename_core": ["1", 2], "filename_separator": "_",
            "include_timestamp_in_filename": False, "counter_digits": 5,
            "save_workflow_data": False, "overwrite_existing": overwrite,
            "source_mode": mode, "source_suffix": suffix, "source_path": ["1", 3]}},
    }
    return p


def listing(d):
    return sorted(os.listdir(d))


rep = {}
try:
    run_prompt(prompt("ignore source"))
    rep["ignore_out"] = listing(os.path.join(OUT, "default"))
    rep["ignore_in"] = listing(IN)

    run_prompt(prompt("same folder as source", suffix="_4x"))
    rep["same_in"] = listing(IN)

    # PNG source, no suffix, overwrite on: must NOT land on shot.png itself
    run_prompt(prompt("same folder as source", suffix="", overwrite=True))
    rep["same_nosuffix_in"] = listing(IN)
    rep["shot_png_size_untouched"] = Image.open(os.path.join(IN, "shot.png")).size

    before = {f: Image.open(os.path.join(IN, f)).size for f in ("photo 01.jpg", "shot.png", "clip.webp")}
    run_prompt(prompt("replace source file", scale=0.5))
    after = {f: Image.open(os.path.join(IN, f)).size for f in ("photo 01.jpg", "shot.png", "clip.webp")}
    fmts = {f: Image.open(os.path.join(IN, f)).format for f in ("photo 01.jpg", "shot.png", "clip.webp")}
    rep["replace_before"], rep["replace_after"], rep["replace_formats"] = before, after, fmts
    rep["replace_in"] = listing(IN)
finally:
    shutil.rmtree(ROOT, ignore_errors=True)

rep["VERDICT"] = {
    "ignore_saves_to_output_only": rep.get("ignore_out") == ["clip_00001.png", "photo 01_00001.png", "shot_00001.png"]
                                   and rep.get("ignore_in") == ["clip.webp", "photo 01.jpg", "shot.png"],
    "same_folder_named_after_source": all(f in rep.get("same_in", []) for f in
                                          ("clip_4x.png", "photo 01_4x.png", "shot_4x.png")),
    "same_folder_never_over_source": "shot_00001.png" in rep.get("same_nosuffix_in", [])
                                     and rep.get("shot_png_size_untouched") == (300, 200),
    "replace_overwrites_in_place": rep.get("replace_after") == {"photo 01.jpg": (320, 240),
                                                                "shot.png": (150, 100),
                                                                "clip.webp": (128, 128)},
    "replace_keeps_format": rep.get("replace_formats") == {"photo 01.jpg": "JPEG", "shot.png": "PNG",
                                                           "clip.webp": "WEBP"},
    "replace_leaves_no_temp_files": not any(".seb_tmp" in f for f in rep.get("replace_in", [])),
}
finish(rep, all(rep["VERDICT"].values()))

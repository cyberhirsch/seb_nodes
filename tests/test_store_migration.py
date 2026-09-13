"""Changing canvas_width must not throw away committed work.

Commit an inverted patch at lon +90 on a 2048 canvas, then read the same
panorama at 4096: the patch has to still be there (magenta, not green).
"""
from _common import (PANO, centre_stats, finish, forget, read_node, require_server,
                     run_prompt, view_rgb)

require_server()
forget(PANO)

rep = {"before": centre_stats(view_rgb(yaw=90, canvas=2048))}
run_prompt({
    "1": read_node(yaw=90.0, canvas=2048),
    "2": {"class_type": "ImageInvert", "inputs": {"image": ["1", 0]}},
    "3": {"class_type": "Write360Seb", "inputs": {
        "pano_ref": ["1", 3], "image": ["2", 0], "view_info": ["1", 2],
        "blend_strength": 1.0, "mode": "commit", "update_reference": True, "feather": 0.0}},
})
rep["after_commit_2048"] = centre_stats(view_rgb(yaw=90, canvas=2048))
rep["after_resize_4096"] = centre_stats(view_rgb(yaw=90, canvas=4096))
rep["after_resize_1024"] = centre_stats(view_rgb(yaw=90, canvas=1024))
inverted = lambda s: s["rgb"][1] < 60 and s["rgb"][0] > 180   # magenta-ish, not green
rep["VERDICT"] = {
    "commit_visible": inverted(rep["after_commit_2048"]),
    "survives_upscale": inverted(rep["after_resize_4096"]),
    "survives_downscale": inverted(rep["after_resize_1024"]),
}
forget(PANO)
finish(rep, all(rep["VERDICT"].values()))

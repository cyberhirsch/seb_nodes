"""Write 360 must put a view back exactly where Read 360 took it from.

Read at yaw +90, invert, commit. The inverted patch has to land at lon +90
(green -> magenta) and lon -90 has to be untouched. A sign mismatch between
the two projections would paint the mirror longitude instead.
"""
from _common import (PANO, centre_stats, delta, finish, forget, read_node,
                     require_server, run_prompt, view_rgb)

require_server()
forget(PANO)

rep = {"before_+90": centre_stats(view_rgb(yaw=90)),
       "before_-90": centre_stats(view_rgb(yaw=-90))}

run_prompt({
    "1": read_node(yaw=90.0),
    "2": {"class_type": "ImageInvert", "inputs": {"image": ["1", 0]}},
    "3": {"class_type": "Write360Seb", "inputs": {
        "pano_ref": ["1", 3], "image": ["2", 0], "view_info": ["1", 2],
        "blend_strength": 1.0, "mode": "commit", "update_reference": True, "feather": 0.0}},
})

rep["after_+90"] = centre_stats(view_rgb(yaw=90))
rep["after_-90"] = centre_stats(view_rgb(yaw=-90))
rep["delta_+90"] = delta(rep["before_+90"]["rgb"], rep["after_+90"]["rgb"])
rep["delta_-90"] = delta(rep["before_-90"]["rgb"], rep["after_-90"]["rgb"])
rep["VERDICT"] = {"landed_where_framed": rep["delta_+90"] > 150,
                  "mirror_untouched": rep["delta_-90"] < 40}
forget(PANO)
finish(rep, all(rep["VERDICT"].values()))

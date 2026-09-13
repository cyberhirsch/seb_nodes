"""mask_mode 'core' keeps the margin as context, and Write feathers its edge.

With margin 7 on a 53.5-degree frame the extracted view is 67.5 wide. 'core'
must be white inside the framed FOV and black in the ring; 'full' all white.
Committing with that mask and feather 0.6 must leave a soft ring in the layer
alpha, not a hard step at the core boundary.
"""
import numpy as np

from _common import (PANO, finish, forget, read_node, require_server, run_prompt,
                     view_mask)

require_server()
forget(PANO)

CAM = dict(yaw=0.0, pitch=0.0, fov=53.5, w=512, h=512, margin=7.0)
rep = {}

core = view_mask(mask_mode="core", **CAM)
full = view_mask(mask_mode="full", **CAM)
h, w = core.shape
cy, cx = h // 2, w // 2
# core half-extent in px: f*tan(core/2) with f = (w/2)/tan(67.5/2)
f = 0.5 * w / np.tan(np.radians(67.5) / 2)
half = f * np.tan(np.radians(53.5) / 2)
rep["core_half_px"] = round(float(half), 1)
rep["core_centre"] = round(float(core[cy, cx]), 3)
rep["core_inside_edge"] = round(float(core[cy, int(cx + half - 6)]), 3)
rep["core_in_ring"] = round(float(core[cy, int(cx + half + 8)]), 3)
rep["core_corner"] = round(float(core[4, 4]), 3)
rep["full_min"] = round(float(full.min()), 3)

# Commit the (unchanged) view with the core mask and a feather, no reference
# update so the layer alpha stays readable through mask_mode 'painted'.
run_prompt({
    "1": read_node(mask_mode="core", **CAM),
    "2": {"class_type": "Write360Seb", "inputs": {
        "pano_ref": ["1", 3], "image": ["1", 0], "view_info": ["1", 2], "mask": ["1", 1],
        "blend_strength": 1.0, "mode": "commit", "update_reference": False, "feather": 0.6}},
})
painted = view_mask(mask_mode="painted", **CAM)
ring = painted[cy, int(cx + half): int(cx + half + 0.6 * (w / 2 - half))]
rep["painted_centre"] = round(float(painted[cy, cx]), 3)
rep["painted_corner"] = round(float(painted[4, 4]), 3)
rep["painted_ring_min_max"] = [round(float(ring.min()), 3), round(float(ring.max()), 3)]
soft = bool(((ring > 0.08) & (ring < 0.92)).any())

rep["VERDICT"] = {
    "core_white_inside": rep["core_centre"] > 0.99 and rep["core_inside_edge"] > 0.99,
    "core_black_in_ring": rep["core_in_ring"] < 0.01 and rep["core_corner"] < 0.01,
    "full_all_white": rep["full_min"] > 0.99,
    "commit_reaches_core": rep["painted_centre"] > 0.95,
    "commit_stops_at_margin": rep["painted_corner"] < 0.05,
    "commit_edge_is_feathered": soft,
}
forget(PANO)
finish(rep, all(rep["VERDICT"].values()))

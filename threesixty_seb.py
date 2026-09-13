"""360 panorama tools: framed extraction, staged write-back, and a feedback loop.

The sphere lives in PANO_STORE; only the framed view travels the graph. The
vendored Pano Editor (js/pano_editor.js) frames, paints and masks on the sphere
and hands all of it to Read 360 through state_json.
"""

import numpy as np
import torch
import cv2
import folder_paths
import os
import json
import random
import hashlib
from collections import OrderedDict
from server import PromptServer
from aiohttp import web
import io
from PIL import Image
import datetime

# --- Global State ---
# {"id": {"base": RGB uint8, "layer": RGBA uint8, "pending": [RGBA uint8, ...]}}
# "pending" holds staged candidates that have been warped into equirect space but
# not yet merged into "layer" -- that is what makes review-before-commit possible.
# An 8K equirect base+layer pair is ~230MB, so keep only the most recent few.
PANO_STORE = OrderedDict()
MAX_STORED_PANOS = 4
MAX_PENDING = 8
# The Pano Editor only needs something to look at; full 8K would be wasteful.
EDITOR_PREVIEW_WIDTH = 2048
# Node-face texture. Full 8K is ~134MB of GPU per Read node and a multi-second
# JPEG encode on every refresh, for a preview a few hundred px wide.
PREVIEW_MAX_WIDTH = 4096


def _touch_pano(unique_id):
    PANO_STORE.move_to_end(unique_id)
    while len(PANO_STORE) > MAX_STORED_PANOS:
        PANO_STORE.popitem(last=False)


# The store is float16 in nominal 0..1. Nothing clamps on the way in, so values
# above 1 survive a commit -- which is what keeps a log-encoded HDR route open.
# cv2 cannot remap/resize float16, so every op widens to float32 and narrows back.
STORE_DTYPE = np.float16


def _composite(base, layer):
    b = base.astype(np.float32)
    l = layer.astype(np.float32)
    a = l[..., 3:4]
    return l[..., :3] * a + b * (1.0 - a)


def _over(dst_layer, src_rgba):
    src = src_rgba.astype(np.float32)
    dst = dst_layer.astype(np.float32)
    src_rgb, src_a = src[..., :3], src[..., 3:4]
    dst_rgb, dst_a = dst[..., :3], dst[..., 3:4]

    out_a = src_a + dst_a * (1.0 - src_a)
    out_a_safe = np.where(out_a == 0, 1.0, out_a)
    out_rgb = (src_rgb * src_a + dst_rgb * dst_a * (1.0 - src_a)) / out_a_safe

    update = (src_a[..., 0] > 0)[..., None]
    final_rgb = dst_rgb.copy()
    final_a = dst_a.copy()
    np.copyto(final_rgb, out_rgb, where=update)
    np.copyto(final_a, out_a, where=update)
    return np.concatenate((final_rgb, final_a), axis=-1).astype(STORE_DTYPE)


def _flatten(data):
    """Bake the painted layer into the base and start a fresh layer.

    This closes the feedback loop: what was generated becomes the reference the
    next pass reads from. Side effect is that the layer alpha resets, so the
    'unpainted' mask goes fully white again -- every view is re-workable rather
    than locked as already-done.
    """
    data["base"] = _composite(data["base"], data["layer"]).astype(STORE_DTYPE)
    data["layer"] = np.zeros_like(data["layer"])


def _core_falloff(h, w, extract_fov, core_fov, feather):
    """Alpha ramp: opaque across the framed core, fading out through the margin.

    Works in the view's own rectilinear coordinates (u = x/f), so the boundary
    follows the actual projection rather than a pixel rectangle.
    """
    if core_fov >= extract_fov or extract_fov <= 0:
        return np.ones((h, w), dtype=np.float32)

    f = 0.5 * w / np.tan(np.radians(extract_fov) / 2.0)
    ys, xs = np.mgrid[0:h, 0:w]
    u = np.abs(xs - (w - 1) / 2.0) / f
    v = np.abs(ys - (h - 1) / 2.0) / f

    tu = np.tan(np.radians(core_fov) / 2.0)      # core half-extent, horizontal
    tv = tu * (h / float(w))                     # same aspect as the view
    ex, ey = (w / 2.0) / f, (h / 2.0) / f        # extracted half-extents

    def ramp(d, inner, outer):
        if outer <= inner:
            return (d <= inner).astype(np.float32)
        t = np.clip((d - inner) / (outer - inner), 0.0, 1.0)
        return (1.0 - (t * t * (3.0 - 2.0 * t))).astype(np.float32)   # smoothstep

    fe = float(np.clip(feather, 0.0, 1.0))
    return ramp(u, tu, tu + fe * (ex - tu)) * ramp(v, tv, tv + fe * (ey - tv))


def _encode_jpeg(rgb, quality=85):
    # Preview only, so clamping to display range is correct here.
    u8 = np.clip(rgb.astype(np.float32) * 255.0, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(u8, cv2.COLOR_RGB2BGR),
                           [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buf.tobytes() if ok else None


# --- API Routes ---
@PromptServer.instance.routes.get("/seb/360/view")
async def get_pano_view(request):
    unique_id = request.rel_url.query.get("id", None)
    if not unique_id or unique_id not in PANO_STORE:
        return web.Response(status=404)

    data = PANO_STORE[unique_id]
    layer = data["layer"]

    # ?candidate=N previews a staged candidate on top of the committed layer
    # without merging it, so the panel can show exactly what commit would produce.
    idx = request.rel_url.query.get("candidate", None)
    if idx not in (None, "", "-1"):
        pending = data.get("pending", [])
        try:
            i = int(idx)
        except ValueError:
            return web.Response(status=400)
        if 0 <= i < len(pending):
            layer = _over(layer, pending[i])

    comp = _composite(data["base"], layer)
    if comp.shape[1] > PREVIEW_MAX_WIDTH:
        scale = PREVIEW_MAX_WIDTH / float(comp.shape[1])
        comp = cv2.resize(comp, (PREVIEW_MAX_WIDTH, max(1, int(comp.shape[0] * scale))),
                          interpolation=cv2.INTER_AREA)
    body = _encode_jpeg(comp)
    if body is None:
        return web.Response(status=500)
    return web.Response(body=body, content_type='image/jpeg')


@PromptServer.instance.routes.get("/seb/360/pending")
async def list_pending(request):
    unique_id = request.rel_url.query.get("id", None)
    if not unique_id or unique_id not in PANO_STORE:
        return web.json_response({"count": 0})
    return web.json_response({"count": len(PANO_STORE[unique_id].get("pending", []))})


@PromptServer.instance.routes.post("/seb/360/commit")
async def commit_pending(request):
    json_data = await request.json()
    unique_id = json_data.get("id", None)
    index = json_data.get("index", 0)
    if not unique_id or unique_id not in PANO_STORE:
        return web.json_response({"error": "unknown panorama"}, status=404)

    data = PANO_STORE[unique_id]
    pending = data.get("pending", [])
    if not isinstance(index, int) or not (0 <= index < len(pending)):
        return web.json_response({"error": "no such candidate"}, status=400)

    data["layer"] = _over(data["layer"], pending[index])
    data["pending"] = []

    # The flag is captured when the node stages, so the commit honours the
    # checkbox as it was set for this generation.
    flattened = bool(data.get("update_reference"))
    if flattened:
        _flatten(data)

    print(f"[Seb 360] Committed candidate {index} to {unique_id}"
          f"{' and folded into reference' if flattened else ''}")
    return web.json_response({"committed": index, "flattened": flattened})


@PromptServer.instance.routes.post("/seb/360/discard")
async def discard_pending(request):
    json_data = await request.json()
    unique_id = json_data.get("id", None)
    if not unique_id or unique_id not in PANO_STORE:
        return web.json_response({"error": "unknown panorama"}, status=404)
    PANO_STORE[unique_id]["pending"] = []
    return web.json_response({"discarded": True})


@PromptServer.instance.routes.post("/seb/360/save")
async def save_pano(request):
    json_data = await request.json()
    unique_id = json_data.get("id", None)

    if not unique_id or unique_id not in PANO_STORE:
        return web.Response(status=404)

    data = PANO_STORE[unique_id]
    comp = _composite(data["base"], data["layer"])          # float32, may exceed 1

    output_dir = folder_paths.get_output_directory()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Seb_360_Export_{timestamp}.png"
    full_path = os.path.join(output_dir, filename)

    # 16-bit PNG: the store is float, so 8 bits would throw away most of what a
    # feathered multi-tile sweep accumulated. cv2 handles 3-channel uint16, PIL
    # does not. Above-range values still clip here -- use EXR for those.
    peak = float(comp.max()) if comp.size else 1.0
    u16 = np.clip(comp, 0.0, 1.0) * 65535.0
    cv2.imwrite(full_path, cv2.cvtColor(u16.astype(np.uint16), cv2.COLOR_RGB2BGR))

    return web.json_response({"filename": filename, "peak": round(peak, 3),
                              "clipped": peak > 1.0})


@PromptServer.instance.routes.post("/seb/360/forget")
async def forget_pano(request):
    """Drop a panorama from the store. The next run re-reads it from disk.

    The store is keyed by filename so committed work survives across runs; this
    is the way out when the file itself was replaced, or to start over.
    """
    json_data = await request.json()
    unique_id = json_data.get("id", None)
    existed = bool(unique_id) and PANO_STORE.pop(unique_id, None) is not None
    return web.json_response({"forgotten": existed})


def _camera_from_state(state_json, shot_index=0):
    """Pull a camera out of Panorama-Stickers' state JSON, or None if absent."""
    if not state_json or not str(state_json).strip():
        return None
    try:
        data = json.loads(state_json)
    except (ValueError, TypeError):
        return None

    pose = data.get("pose") if isinstance(data.get("pose"), dict) else None
    if pose is None:
        shots = [x for x in (data.get("shots") or []) if isinstance(x, dict)]
        if not shots:
            return None
        # The frame selected in the editor is the camera -- the same rule the
        # node-face sync applies, so what the face shows is what gets extracted.
        active = data.get("active") if isinstance(data.get("active"), dict) else {}
        sel = active.get("selected_shot_id")
        pose = next((x for x in shots if x.get("id") == sel), None)
        if pose is None:
            pose = shots[min(max(int(shot_index), 0), len(shots) - 1)]

    yaw = ((float(pose.get("yaw_deg", 0.0)) + 180.0) % 360.0) - 180.0
    pitch = max(-90.0, min(90.0, float(pose.get("pitch_deg", 0.0))))
    fov = float(pose.get("hFOV_deg", 90.0))
    h, v = pose.get("hFOV_deg"), pose.get("vFOV_deg")
    aspect = (np.tan(np.radians(float(h)) / 2) / np.tan(np.radians(float(v)) / 2)
              if h and v else float(data.get("source_aspect", 1.0) or 1.0))
    return {"yaw": yaw, "pitch": pitch, "fov": fov,
            "roll": float(pose.get("roll_deg", 0.0)), "aspect": aspect}


def _painting_layer_paths(state_json):
    """Where the editor rasterised its paint and mask layers, if it has.

    On close the editor uploads both as 2:1 equirect PNGs (the mask lives in the
    alpha channel) and records them under painting_layer. Until it has been
    closed once after painting, that entry is null and there is nothing to read.
    """
    try:
        data = json.loads(state_json) if state_json and str(state_json).strip() else {}
    except (ValueError, TypeError):
        return {}
    layer = data.get("painting_layer")
    if not isinstance(layer, dict):
        return {}
    roots = {"input": folder_paths.get_input_directory(),
             "temp": folder_paths.get_temp_directory(),
             "output": folder_paths.get_output_directory()}
    out = {}
    for key in ("mask", "paint"):
        rec = layer.get(key)
        if not isinstance(rec, dict) or not rec.get("filename"):
            continue
        root = roots.get(str(rec.get("storage") or "input"))
        parts = [x for x in (str(rec.get("subfolder") or ""), str(rec["filename"])) if x]
        if root is None or any(".." in x for x in parts):
            continue
        path = os.path.join(root, *parts)
        if os.path.isfile(path):
            out[key] = path
    return out


def _load_erp_rgba(path):
    """An editor raster as float32 RGBA 0..1, or None if unreadable."""
    try:
        return np.array(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0
    except Exception as exc:
        print(f"[Seb 360] Could not read editor layer {path}: {exc}")
        return None


def _resize_store(data, w, h):
    """canvas_width changed: carry the committed work over instead of dropping it."""
    def rs(a):
        interp = cv2.INTER_AREA if w < a.shape[1] else cv2.INTER_CUBIC
        return cv2.resize(a.astype(np.float32), (w, h), interpolation=interp).astype(STORE_DTYPE)
    old_w = data["base"].shape[1]
    data["base"] = rs(data["base"])
    data["layer"] = rs(data["layer"])
    data["pending"] = [rs(x) for x in data.get("pending", [])]
    print(f"[Seb 360] Canvas {old_w} -> {w}: resampled base, layer and "
          f"{len(data['pending'])} staged candidate(s)")


def _feather_mask_edge(alpha, w, extract_fov, core_fov, feather):
    """Soften a commit mask's outer edge by the same ring the falloff uses.

    A hard mask -- the 'core' mode, or one painted in the editor -- would
    otherwise stop the commit dead at its boundary, and the feather ring that
    hides the seam would never get to blend anything.
    """
    if feather <= 0 or core_fov >= extract_fov or extract_fov <= 0:
        return alpha
    f = 0.5 * w / np.tan(np.radians(extract_fov) / 2.0)
    ring_px = 0.5 * w - f * np.tan(np.radians(core_fov) / 2.0)
    r = int(round(float(np.clip(feather, 0.0, 1.0)) * ring_px))
    if r < 1:
        return alpha
    grown = cv2.dilate(alpha.astype(np.float32), np.ones((2 * r + 1, 2 * r + 1), np.uint8))
    return cv2.GaussianBlur(grown, (0, 0), sigmaX=max(0.5, r / 2.0)).astype(np.float32)


def tensor_to_numpy(tensor):
    # ComfyUI Tensor (B, H, W, C) -> Numpy (H, W, C) float32 in 0..1.
    # Deliberately unclamped: clamping here would discard any above-range values.
    return tensor.cpu().numpy().squeeze().astype(np.float32)

def numpy_to_tensor(array):
    # Numpy (H, W, C) float 0..1 -> ComfyUI Tensor (B, H, W, C)
    return torch.from_numpy(np.ascontiguousarray(array.astype(np.float32))).unsqueeze(0)

# --- Projection Math Helpers ---

def get_rotation_matrix(yaw_deg, pitch_deg, roll_deg=0):
    # Yaw is NOT negated: positive yaw looks east (+longitude), matching the
    # editor's yaw_deg and standard equirect layout (x = (lon/360 + 0.5) * W).
    # The negation that used to be here mirrored every extraction, so framing at
    # yaw +90 in the editor cut out longitude -90.
    yaw = np.radians(yaw_deg)
    pitch = np.radians(pitch_deg)
    roll = np.radians(roll_deg)

    Rx = np.array([[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)], [0, np.sin(pitch), np.cos(pitch)]])
    Ry = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
    Rz = np.array([[np.cos(roll), -np.sin(roll), 0], [np.sin(roll), np.cos(roll), 0], [0, 0, 1]])
    
    R = Ry @ Rx @ Rz 
    return R

def equirect_to_perspective(img_equi, fov, yaw, pitch, out_w, out_h):
    # 1. Calculate focal length
    f = 0.5 * out_w / np.tan(0.5 * np.radians(fov))

    # 2. Grid for perspective plane
    cx, cy = out_w / 2, out_h / 2
    x_range = np.arange(out_w) - cx
    y_range = np.arange(out_h) - cy
    xv, yv = np.meshgrid(x_range, y_range)
    z_val = f
    
    xyz = np.stack([xv, yv, np.full_like(xv, z_val)], axis=-1)
    norm = np.linalg.norm(xyz, axis=2, keepdims=True)
    xyz /= norm

    # 3. Rotate rays
    R = get_rotation_matrix(yaw, pitch)
    xyz_rot = xyz @ R.T

    # 4. Convert to Spherical -> UV
    x_3d = xyz_rot[:, :, 0]
    y_3d = xyz_rot[:, :, 1]
    z_3d = xyz_rot[:, :, 2]
    
    lon = np.arctan2(x_3d, z_3d)
    lat = np.arcsin(np.clip(y_3d, -1.0, 1.0))

    u = (lon / (2 * np.pi)) + 0.5
    v = (lat / np.pi) + 0.5

    src_h, src_w = img_equi.shape[:2]
    # Longitude wraps at +/-180, latitude must not: clamping y stops the poles
    # from sampling across to the opposite side of the sphere.
    map_x = np.mod(u * src_w, src_w).astype(np.float32)
    map_y = np.clip(v * src_h, 0, src_h - 1).astype(np.float32)

    # 5. Remap
    return cv2.remap(img_equi, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

def perspective_to_equirect_map(persp_img, fov, yaw, pitch, out_w, out_h):
    # Grid for Equirectangular target
    lon_range = np.linspace(-np.pi, np.pi, num=out_w, endpoint=False) 
    lat_range = np.linspace(-np.pi/2, np.pi/2, num=out_h, endpoint=True)
    lon_v, lat_v = np.meshgrid(lon_range, lat_range)
    
    # Spherical to Cartesian
    cos_lat = np.cos(lat_v)
    x_3d = cos_lat * np.sin(lon_v)
    y_3d = np.sin(lat_v)
    z_3d = cos_lat * np.cos(lon_v)
    
    xyz = np.stack([x_3d, y_3d, z_3d], axis=-1)
    
    # Inverse Rotation (R is orthonormal, so its inverse is its transpose)
    R = get_rotation_matrix(yaw, pitch)
    xyz_cam = xyz @ R
    
    # Project to 2D
    valid_mask = xyz_cam[:, :, 2] > 0
    
    f = 0.5 * persp_img.shape[1] / np.tan(0.5 * np.radians(fov))
    cx, cy = persp_img.shape[1] / 2, persp_img.shape[0] / 2
    
    z_safe = xyz_cam[:, :, 2].copy()
    z_safe[z_safe == 0] = 0.0001
    
    u_proj = (f * xyz_cam[:, :, 0] / z_safe) + cx
    v_proj = (f * xyz_cam[:, :, 1] / z_safe) + cy
    
    h_p, w_p = persp_img.shape[:2]
    valid_mask = valid_mask & (u_proj >= 0) & (u_proj < w_p) & (v_proj >= 0) & (v_proj < h_p)
    
    map_x = u_proj.astype(np.float32)
    map_y = v_proj.astype(np.float32)
    
    warped_img = cv2.remap(persp_img, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0,0))
    
    warped_img[~valid_mask] = 0

    return warped_img, valid_mask


# --- Nodes ---


class Read360Seb:
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True}),
                "projection": (["perspective", "equirectangular"],),
                "yaw": ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "pitch": ("FLOAT", {"default": 0.0, "min": -90.0, "max": 90.0, "step": 1.0}),
                "fov": ("FLOAT", {"default": 90.0, "min": 10.0, "max": 160.0}),
                "view_width": ("INT", {"default": 1024}),
                "view_height": ("INT", {"default": 1024}),
                "mask_mode": (["core", "full", "editor", "unpainted", "painted"],
                              {"tooltip": "White = generate. core: the framed FOV, the "
                                          "margin stays as context. full: everything "
                                          "extracted. editor: what you painted with the "
                                          "Pano Editor's Mask tool, clipped to the core. "
                                          "unpainted / painted: by the committed layer."}),
                "margin_deg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 45.0, "step": 0.5,
                                        "tooltip": "Extra FOV per side, extracted as inpainting "
                                                   "context but NOT committed. The generation "
                                                   "boundary lands here and is discarded."}),
                # Written by the vendored Pano Editor, which is bound to this node. It
                # carries the framed shot and, once the editor has been closed after
                # painting, the rasterised paint/mask layers. extract() reads all of
                # it -- no adapter node, no links.
                "coverage": (["360", "180"],),
                "state_json": ("STRING", {"multiline": True, "default": "",
                                          "tooltip": "Written by the Pano Editor. "
                                                     "Leave empty to use the yaw/pitch/fov "
                                                     "widgets instead."}),
                "canvas_width": ("INT", {"default": 0, "min": 0, "max": 16384, "step": 256,
                                         "tooltip": "Resample the panorama to this width on load "
                                                    "(height = width/2). 0 keeps the source size. "
                                                    "Set it larger than the seed so committed "
                                                    "detail has somewhere to live."}),
            },
            "optional": {
                "pano_image_override": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "PANO_VIEW_INFO", "PANO_REF")
    RETURN_NAMES = ("view_image", "mask", "view_info", "pano_ref")
    FUNCTION = "extract"
    CATEGORY = "Seb/360"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # The output depends on the painted layer, which Write 360 mutates
        # between runs, so a cached result is never safe to reuse.
        return float("nan")

    def extract(self, image, projection, yaw, pitch, fov, view_width, view_height,
                mask_mode="unpainted", margin_deg=7.0, coverage="360", state_json="",
                canvas_width=0, pano_image_override=None):
        cam = _camera_from_state(state_json)
        if cam:
            yaw, pitch, fov = cam["yaw"], cam["pitch"], cam["fov"]
            # The framed aspect as well, so the vertical FOV is the editor's even
            # when the widget sync has not run yet (API use, a queue right after
            # Save). Same rounding the JS applies, so the two never disagree.
            if cam.get("aspect") and cam["aspect"] > 0:
                view_height = max(64, int(round(view_width / cam["aspect"] / 8.0)) * 8)
        core_fov = float(fov)
        fov = min(179.0, core_fov + 2.0 * float(margin_deg))
        if pano_image_override is not None:
            if len(pano_image_override.shape) == 4:
                img_np = tensor_to_numpy(pano_image_override[0])
            else:
                img_np = tensor_to_numpy(pano_image_override)
        else:
            image_path = folder_paths.get_annotated_filepath(image)
            i = Image.open(image_path).convert("RGB")
            img_np = np.array(i).astype(np.float32) / 255.0

        # Ensure 3 channels
        if img_np.shape[-1] == 4:
            img_np = img_np[..., :3]

        # Resample the sphere before the layer is allocated: the layer is sized to
        # the base, so this is what decides how much committed detail can survive.
        if canvas_width and canvas_width != img_np.shape[1]:
            target = (int(canvas_width), int(canvas_width) // 2)
            interp = cv2.INTER_AREA if canvas_width < img_np.shape[1] else cv2.INTER_CUBIC
            img_np = cv2.resize(img_np, target, interpolation=interp)

        img_np = img_np.astype(STORE_DTYPE)
        h, w, c = img_np.shape

        # The id must be derived from the panorama itself: it is what lets the
        # painted layer survive across executions so views can accumulate.
        if pano_image_override is not None:
            # A strided sample is plenty to tell panoramas apart; hashing the
            # whole 8K buffer (~200MB) on every run is not worth it.
            probe = img_np[::16, ::16].tobytes() + str(img_np.shape).encode()
            unique_id = "override_" + hashlib.sha1(probe).hexdigest()[:16]
        else:
            unique_id = image

        # Keyed by the source, so the painted layer survives across runs. That
        # also means a file edited on disk under the same name is not re-read
        # until the entry is evicted -- the price of the feedback loop.
        if unique_id not in PANO_STORE:
            PANO_STORE[unique_id] = {
                "base": img_np,
                "layer": np.zeros((h, w, 4), dtype=STORE_DTYPE),
                "pending": []
            }
        elif PANO_STORE[unique_id]["base"].shape != img_np.shape:
            _resize_store(PANO_STORE[unique_id], w, h)
        PANO_STORE[unique_id].setdefault("pending", [])
        _touch_pano(unique_id)

        data = PANO_STORE[unique_id]
        
        # 1. Extract Views
        if projection == "equirectangular":
            # Rotate the sphere: for each output pixel, undo the yaw/pitch to find
            # where it came from in the source panorama.
            lon_range = np.linspace(-np.pi, np.pi, num=view_width, endpoint=False)
            lat_range = np.linspace(-np.pi/2, np.pi/2, num=view_height, endpoint=True)
            lon_v, lat_v = np.meshgrid(lon_range, lat_range)
            
            # Spherical to Cartesian
            cos_lat = np.cos(lat_v)
            x_3d = cos_lat * np.sin(lon_v)
            y_3d = np.sin(lat_v)
            z_3d = cos_lat * np.cos(lon_v)
            
            xyz = np.stack([x_3d, y_3d, z_3d], axis=-1)
            
            R = get_rotation_matrix(yaw, pitch)
            xyz_orig = xyz @ R.T
            
            # Cartesian -> Spherical -> UV
            x_o = xyz_orig[:, :, 0]
            y_o = xyz_orig[:, :, 1]
            z_o = xyz_orig[:, :, 2]
            
            lon_o = np.arctan2(x_o, z_o)
            lat_o = np.arcsin(np.clip(y_o, -1.0, 1.0))

            u = (lon_o / (2 * np.pi)) + 0.5
            v = (lat_o / np.pi) + 0.5

            src_h, src_w = data["base"].shape[:2]
            map_x = np.mod(u * src_w, src_w).astype(np.float32)
            map_y = np.clip(v * src_h, 0, src_h - 1).astype(np.float32)
            
            def project(img):
                return cv2.remap(img.astype(np.float32), map_x, map_y,
                                 interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            # No rectilinear core on a full-sphere output: the whole thing is the view.
            core_mask = np.ones((view_height, view_width), dtype=np.float32)
            
        else:
            def project(img):
                return equirect_to_perspective(img.astype(np.float32), fov, yaw, pitch,
                                               view_width, view_height)
            core_mask = _core_falloff(view_height, view_width, fov, core_fov, 0.0)

        base_view = project(data["base"])
        layer_view = project(data["layer"])
        
        # 2. Composite -- views are already float 0..1, so no /255 rescale
        base_f = base_view
        layer_rgb_f = layer_view[..., :3]
        layer_a_f = layer_view[..., 3:]
        
        final_view = (layer_rgb_f * layer_a_f) + (base_f * (1.0 - layer_a_f))
        
        # 2b. Editor layers. They were painted on the sphere, so they project
        # through exactly the same camera as the store. Paint (placed images,
        # brush strokes) is composited over the view: it is the guide the model
        # integrates, and it reaches the panorama by being generated over, not
        # by being pasted. The mask is a candidate for mask_mode below.
        editor = _painting_layer_paths(state_json)
        editor_mask = None
        if "mask" in editor:
            m = _load_erp_rgba(editor["mask"])
            if m is not None:
                editor_mask = np.clip(project(m[..., 3]), 0.0, 1.0).astype(np.float32)
        if "paint" in editor:
            pnt = _load_erp_rgba(editor["paint"])
            if pnt is not None:
                pv = project(pnt)
                pa = pv[..., 3:4]
                final_view = pv[..., :3] * pa + final_view * (1.0 - pa)

        # 3. Outputs
        out_image = torch.from_numpy(np.ascontiguousarray(final_view)).unsqueeze(0)
        # White = the region to generate, matching ComfyUI's inpaint convention.
        painted = layer_a_f[..., 0]
        if mask_mode == "full":
            mask_np = np.ones_like(painted)
        elif mask_mode == "painted":
            mask_np = painted
        elif mask_mode == "unpainted":
            mask_np = 1.0 - painted
        elif mask_mode == "editor":
            if editor_mask is None:
                print("[Seb 360] mask_mode 'editor' but the editor has no mask layer yet "
                      "(paint one, then close the editor) -- using 'core'")
                mask_np = core_mask
            else:
                # Clipped to the core: the margin is context and is never generated.
                mask_np = editor_mask * core_mask
        else:
            mask_np = core_mask
        out_mask = torch.from_numpy(np.ascontiguousarray(mask_np.astype(np.float32))).unsqueeze(0)
        
        # "fov" is the extracted (wide) FOV -- Write 360 needs it to back-project.
        # "core_fov" is what was framed, and the only part that gets committed.
        view_info = {
            "id": unique_id, "yaw": yaw, "pitch": pitch, "fov": fov,
            "core_fov": core_fov, "margin_deg": float(margin_deg),
            "w": view_width, "h": view_height, "projection": projection
        }

        # How many real source pixels back this view. Ratio > 1 means the view is
        # being upscaled from the sphere and no generator can recover that detail.
        src_px = w * (fov / 360.0)
        ratio = view_width / src_px if src_px else 0.0
        density = (f"{w}x{h} sphere | {src_px:.0f}px source -> {view_width}px view "
                   f"| {ratio:.2f}x {'UPSCALE' if ratio > 1.05 else 'native' if ratio > 0.95 else 'downscale'} "
                   f"| {w / 360.0:.1f} px/deg")

        # The Pano Editor reads the panorama from ui["pano_input_images"] -- the same
        # channel their own nodes use. Without it the editor opens on an empty sphere
        # and edits content unrelated to this node. Downscaled: the editor only needs
        # something to look at, and writing an 8K PNG every run is not worth it.
        pano_preview = []
        try:
            comp = _composite(data["base"], data["layer"])
            ph, pw = comp.shape[:2]
            if pw > EDITOR_PREVIEW_WIDTH:
                scale = EDITOR_PREVIEW_WIDTH / float(pw)
                comp = cv2.resize(comp, (EDITOR_PREVIEW_WIDTH, max(1, int(ph * scale))),
                                  interpolation=cv2.INTER_AREA)
            comp8 = np.clip(comp * 255.0, 0, 255).astype(np.uint8)
            fname = f"seb_360_erp_{unique_id[:16]}_{random.randint(0, 1 << 30)}.png"
            cv2.imwrite(os.path.join(folder_paths.get_temp_directory(), fname),
                        cv2.cvtColor(comp8, cv2.COLOR_RGB2BGR))
            pano_preview = [{"filename": fname, "subfolder": "", "type": "temp"}]
        except Exception as exc:
            print(f"[Seb 360] Could not write editor preview: {exc}")

        # No "images" in the ui dict: the WebGL widget already shows this view, and
        # returning one made ComfyUI stack a second, differently-framed preview
        # under it. Wire a PreviewImage node if a static copy is wanted.
        return {
            "ui": {"pano_id": [unique_id], "density": [density],
                   "pano_input_images": pano_preview},
            "result": (out_image, out_mask, view_info, unique_id)
        }



class Write360Seb:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "pano_ref": ("PANO_REF",),
                "image": ("IMAGE",),
                "view_info": ("PANO_VIEW_INFO",),
                "blend_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "mode": (["stage", "commit"],),
                "update_reference": ("BOOLEAN", {"default": True}),
                "feather": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 1.0, "step": 0.05,
                                      "tooltip": "How much of the margin ring is used as a blend "
                                                 "ramp. 0 = hard edge at the framed FOV, "
                                                 "1 = fade all the way to the extracted edge."}),
            },
            "optional": {
                 "mask": ("MASK",),
            }
        }

    RETURN_TYPES = ("PANO_REF",)
    RETURN_NAMES = ("pano_ref",)
    FUNCTION = "save_to_layer"
    CATEGORY = "Seb/360"
    OUTPUT_NODE = True

    def save_to_layer(self, pano_ref, image, view_info, blend_strength, mode="stage",
                      update_reference=True, feather=0.6, mask=None):
        unique_id = pano_ref
        if unique_id not in PANO_STORE:
            return {"ui": {"pano_id": [unique_id], "pending": [0],
                           "update_reference": [bool(update_reference)]},
                    "result": (unique_id,)}

        batch = image if image.dim() == 4 else image.unsqueeze(0)
        target_h, target_w = PANO_STORE[unique_id]["layer"].shape[:2]

        staged = []
        for b in range(batch.shape[0]):
            img_np = tensor_to_numpy(batch[b])
            h, w = img_np.shape[:2]

            if mask is not None:
                m = mask[b] if (mask.dim() == 3 and mask.shape[0] == batch.shape[0]) else mask
                mask_np = m.cpu().numpy().squeeze()
                if mask_np.shape != (h, w):
                    mask_np = cv2.resize(mask_np, (w, h))
                alpha_channel = np.clip(mask_np * blend_strength, 0.0, 1.0).astype(np.float32)
                alpha_channel = _feather_mask_edge(
                    alpha_channel, w, view_info["fov"],
                    view_info.get("core_fov", view_info["fov"]), feather)
            else:
                alpha_channel = np.full((h, w), float(blend_strength), dtype=np.float32)

            # Commit only what was framed: the margin exists to give the model
            # context, and to let the generation boundary die outside the core.
            falloff = _core_falloff(h, w, view_info["fov"],
                                    view_info.get("core_fov", view_info["fov"]), feather)
            alpha_channel = alpha_channel.astype(np.float32) * falloff

            patch_rgba = np.dstack((img_np, alpha_channel))
            warped, _ = perspective_to_equirect_map(
                patch_rgba,
                view_info["fov"], view_info["yaw"], view_info["pitch"],
                target_w, target_h
            )
            staged.append(warped.astype(STORE_DTYPE))

        entry = PANO_STORE[unique_id]
        entry["update_reference"] = bool(update_reference)

        if mode == "commit":
            for warped in staged:
                entry["layer"] = _over(entry["layer"], warped)
            entry["pending"] = []
            pending_count = 0
            if update_reference:
                _flatten(entry)
            print(f"[Seb 360] Committed {len(staged)} view(s) to {unique_id}"
                  f"{' and folded into reference' if update_reference else ''}")
        else:
            entry["pending"] = staged[:MAX_PENDING]
            pending_count = len(entry["pending"])
            print(f"[Seb 360] Staged {pending_count} candidate(s) for {unique_id} "
                  f"-- review and commit from the node panel")

        _touch_pano(unique_id)
        return {"ui": {"images": [], "pano_id": [unique_id], "pending": [pending_count],
                       "update_reference": [bool(update_reference)]},
                "result": (unique_id,)}

class PanoState360Seb:
    """Read a camera out of ComfyUI-Panorama-Stickers' state JSON.

    Accepts either form that pack emits: the compact `sticker_state` from
    Panorama Cutout ({"pose": {...}}), or the full editor `state_json` carrying a
    `shots` list. Lets their modal drive extraction while the sphere stays in
    PANO_STORE, so the full panorama never travels through the graph.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "state_json": ("STRING", {"multiline": True, "default": ""}),
                "shot_index": ("INT", {"default": 0, "min": 0, "max": 63}),
            }
        }

    RETURN_TYPES = ("FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "STRING")
    RETURN_NAMES = ("yaw", "pitch", "fov", "roll", "aspect", "info")
    FUNCTION = "parse"
    CATEGORY = "Seb/360"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def parse(self, state_json, shot_index=0):
        yaw = pitch = roll = 0.0
        fov = 90.0
        aspect = 1.0
        note = "empty"

        try:
            data = json.loads(state_json) if state_json.strip() else {}
        except (ValueError, TypeError):
            return (0.0, 0.0, 90.0, 0.0, 1.0, "unparseable state_json")

        pose = None
        if isinstance(data.get("pose"), dict):
            pose = data["pose"]
            note = "cutout sticker_state"
        else:
            shots = data.get("shots") or []
            if shots:
                idx = min(max(int(shot_index), 0), len(shots) - 1)
                pose = shots[idx]
                note = f"shot {idx + 1} of {len(shots)}"

        if pose:
            yaw = float(pose.get("yaw_deg", 0.0))
            pitch = float(pose.get("pitch_deg", 0.0))
            roll = float(pose.get("roll_deg", 0.0))
            fov = float(pose.get("hFOV_deg", 90.0))
            h, v = pose.get("hFOV_deg"), pose.get("vFOV_deg")
            if h and v:
                # aspect that reproduces their vFOV: v = 2*atan(tan(h/2)/aspect)
                aspect = np.tan(np.radians(float(h)) / 2) / np.tan(np.radians(float(v)) / 2)
            else:
                aspect = float(data.get("source_aspect", 1.0) or 1.0)

        # Wrap yaw into the range Read360Seb's widget accepts.
        yaw = ((yaw + 180.0) % 360.0) - 180.0
        pitch = max(-90.0, min(90.0, pitch))

        info = (f"{note} | yaw {yaw:.1f} pitch {pitch:.1f} fov {fov:.1f} "
                f"roll {roll:.1f} aspect {aspect:.3f}")
        print(f"[Seb 360] PanoState: {info}")
        return (yaw, pitch, fov, roll, aspect, info)


def _sweep_positions(core_fov, overlap_pct, include_poles):
    """Yaw/pitch pairs covering the sphere with the given core FOV.

    Columns per row scale with cos(latitude); a fixed grid would bunch tiles
    near the poles and waste most of the sweep there.
    """
    step = max(1.0, core_fov * (1.0 - overlap_pct / 100.0))
    rows = max(1, int(np.ceil(180.0 / step)))
    pitches = [-90.0 + step * (r + 0.5) for r in range(rows)]
    pitches = [p for p in pitches if -90.0 < p < 90.0]

    out = []
    for p in pitches:
        span = max(0.15, np.cos(np.radians(p)))
        cols = max(1, int(np.ceil(360.0 * span / step)))
        for c in range(cols):
            yaw = -180.0 + (360.0 / cols) * (c + 0.5)
            out.append((round(yaw, 2), round(p, 2)))

    if include_poles:
        out.append((0.0, -89.9))
        out.append((0.0, 89.9))
    return out


class PanoSweep360Seb:
    """Turn a running index into a camera that walks the whole sphere.

    Set control_after_generate on `index` to 'increment' and queue `total` runs:
    each execution advances one tile. Pair with Write 360 in commit mode for an
    unattended pass, or stage mode to approve each one.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "index": ("INT", {"default": 0, "min": 0, "max": 4096}),
                "core_fov": ("FLOAT", {"default": 53.5, "min": 5.0, "max": 170.0, "step": 0.5}),
                "overlap_pct": ("FLOAT", {"default": 15.0, "min": 0.0, "max": 60.0, "step": 1.0}),
                "include_poles": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("FLOAT", "FLOAT", "INT", "INT", "STRING")
    RETURN_NAMES = ("yaw", "pitch", "total", "wrapped_index", "info")
    FUNCTION = "step"
    CATEGORY = "Seb/360"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def step(self, index, core_fov, overlap_pct, include_poles):
        pos = _sweep_positions(core_fov, overlap_pct, include_poles)
        total = len(pos)
        i = int(index) % total
        yaw, pitch = pos[i]
        info = (f"tile {i + 1}/{total} | yaw {yaw:.1f} pitch {pitch:.1f} "
                f"| core {core_fov:.1f} overlap {overlap_pct:.0f}%")
        print(f"[Seb 360] Sweep {info}")
        return (float(yaw), float(pitch), total, i, info)


NODE_CLASS_MAPPINGS = {
    "Read360Seb": Read360Seb,
    "Write360Seb": Write360Seb,
    "PanoState360Seb": PanoState360Seb,
    "PanoSweep360Seb": PanoSweep360Seb
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Read360Seb": "Read 360 (Seb)",
    "Write360Seb": "Write 360 (Seb)",
    "PanoState360Seb": "Pano State to Camera (Seb)",
    "PanoSweep360Seb": "Pano Sweep (Seb)"
}
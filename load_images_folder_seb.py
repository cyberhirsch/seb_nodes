"""Load a folder of images: one image per run (the loop), or all at once (a list).

one per run     The default. Each run handles the image at `index`. When that run
                has *finished successfully* the node queues the next index itself,
                until the folder is done. So every result reaches disk before the
                next image starts, RAM stays flat, and Cancel stops the chain --
                the next image is only ever queued after a successful run.

all in one run  Every image as one ComfyUI list. Downstream nodes run once per
                item, but node by node (all encodes, then all samples, then all
                decodes, then all saves), so everything sits in RAM until the end
                and nothing is on disk before the last image. Fine for a handful.

`filename` carries the source name along so a save node can keep it.
"""
import copy
import hashlib
import json
import os
import threading
import time
import urllib.request

import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence

import folder_paths
import node_helpers
from server import PromptServer

IMAGE_EXTS = "png,jpg,jpeg,webp,bmp,tif,tiff"
MODE_LOOP = "one per run"
MODE_LIST = "all in one run"
TAG = "[Seb] Load Images From Folder"


def _resolve_folder(folder):
    folder = os.path.expandvars(os.path.expanduser(str(folder or "").strip().strip('"')))
    if not folder:
        return None
    if not os.path.isabs(folder):
        folder = os.path.join(folder_paths.get_input_directory(), folder)
    return os.path.normpath(folder)


def _list_images(folder, extensions, include_subfolders, sort_by):
    exts = {"." + e.strip().lower().lstrip(".") for e in str(extensions).split(",") if e.strip()}
    found = []
    if include_subfolders:
        for root, _dirs, files in os.walk(folder):
            found += [os.path.join(root, f) for f in files if os.path.splitext(f)[1].lower() in exts]
    else:
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and os.path.splitext(f)[1].lower() in exts:
                found.append(p)
    if sort_by == "date":
        found.sort(key=lambda p: (os.path.getmtime(p), p.lower()))
    else:
        found.sort(key=lambda p: p.lower())
    return found


def _load_one(path):
    """Same decode as core LoadImage: EXIF-rotated RGB, mask = inverted alpha."""
    img = node_helpers.pillow(Image.open, path)
    frame = next(ImageSequence.Iterator(img))          # first frame of animated formats
    frame = node_helpers.pillow(ImageOps.exif_transpose, frame)
    rgb = np.array(frame.convert("RGB")).astype(np.float32) / 255.0
    image = torch.from_numpy(rgb)[None,]
    if "A" in frame.getbands():
        alpha = np.array(frame.getchannel("A")).astype(np.float32) / 255.0
        mask = 1.0 - torch.from_numpy(alpha)
    else:
        mask = torch.zeros((64, 64), dtype=torch.float32)  # core's "no alpha" placeholder
    return image, mask.unsqueeze(0)


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0]


# ----------------------------------------------------------------- the loop
def _running_item(unique_id, inputs):
    """(prompt_id, extra_data) of the prompt executing right now -- ours."""
    queue = PromptServer.instance.prompt_queue
    with queue.mutex:
        items = list(queue.currently_running.values())
    for item in items:
        node = (item[2] or {}).get(str(unique_id)) or {}
        if node.get("inputs") == inputs:
            return item[1], dict(item[3] or {})
    if len(items) == 1:            # only one prompt ever runs at a time
        return items[0][1], dict(items[0][3] or {})
    return None, None


def _server_url():
    srv = PromptServer.instance
    host = srv.address if srv.address not in (None, "", "0.0.0.0", "::", "[::]") else "127.0.0.1"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{srv.port}"


def _queue_next_when_done(prompt_id, next_prompt, extra_data, label):
    """Wait for the current run to land in the history; queue the next index
    only if it succeeded. An error or an interrupt ends the chain."""
    queue = PromptServer.instance.prompt_queue
    deadline = time.time() + 24 * 3600
    while time.time() < deadline:
        time.sleep(0.5)
        entry = (queue.get_history(prompt_id=prompt_id) or {}).get(prompt_id)
        if not entry:
            continue                                   # still running
        status = entry.get("status") or {}
        if status.get("status_str") != "success":
            print(f"{TAG}: run ended with '{status.get('status_str')}' -- stopping the loop")
            return
        body = {"prompt": next_prompt, "extra_data": extra_data}
        if extra_data.get("client_id"):
            body["client_id"] = extra_data["client_id"]
        req = urllib.request.Request(_server_url() + "/prompt", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
            print(f"{TAG}: queued {label}")
        except Exception as exc:
            print(f"{TAG}: could not queue {label}: {exc}")
        return
    print(f"{TAG}: gave up waiting for the run to finish")


class LoadImagesFromFolderSeb:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {
                    "default": "", "multiline": False,
                    "placeholder": "absolute path, or a folder inside ComfyUI's input directory",
                    "tooltip": "Every matching image in here goes through the rest of the graph. "
                               "Absolute path, or relative to the input folder."}),
                "mode": ([MODE_LOOP, MODE_LIST], {
                    "tooltip": "one per run: press Run once; each run handles one image and "
                               "queues the next when it has finished -- results land on disk "
                               "one by one, RAM stays flat, Cancel stops it. "
                               "all in one run: everything in a single run as a list; nothing "
                               "is saved until the last image is done."}),
                "index": ("INT", {"default": 0, "min": 0, "max": 100000,
                                  "tooltip": "one per run: the image this run handles, 0 = first. "
                                             "Leave it at 0 -- the node advances it by itself. "
                                             "Ignored by 'all in one run'."}),
                "extensions": ("STRING", {"default": IMAGE_EXTS,
                                          "tooltip": "Comma-separated, case-insensitive."}),
                "include_subfolders": ("BOOLEAN", {"default": False}),
                "sort_by": (["name", "date"],),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 100000,
                                        "tooltip": "Skip this many files (after sorting)."}),
                "limit": ("INT", {"default": 0, "min": 0, "max": 100000,
                                  "tooltip": "0 = all. Caps how many files are in play."}),
            },
            "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("image", "mask", "filename", "path", "index", "count")
    OUTPUT_IS_LIST = (True, True, True, True, True, True)
    FUNCTION = "load"
    CATEGORY = "image"
    DESCRIPTION = ("Walks a folder of images. One per run (default): press Run once and it "
                   "processes them one after another, queueing the next image itself when the "
                   "current run has finished. Wire `filename` into a save node to keep the names.")

    def load(self, folder, mode, index, extensions, include_subfolders, sort_by,
             start_index, limit, prompt=None, unique_id=None):
        root = _resolve_folder(folder)
        if not root or not os.path.isdir(root):
            raise ValueError(f"{TAG}: not a folder: {folder!r}")
        paths = _list_images(root, extensions, include_subfolders, sort_by)[start_index:]
        if limit > 0:
            paths = paths[:limit]
        n = len(paths)
        if not n:
            raise ValueError(f"{TAG}: no images matching '{extensions}' in {root} "
                             f"(start_index {start_index}, limit {limit})")

        if mode == MODE_LIST:
            images, masks, names, fulls, idxs = [], [], [], [], []
            for i, p in enumerate(paths):
                try:
                    img, m = _load_one(p)
                except Exception as exc:
                    print(f"{TAG}: skipping unreadable {p}: {exc}")
                    continue
                images.append(img); masks.append(m); names.append(_stem(p))
                fulls.append(p); idxs.append(i)
            k = len(images)
            if not k:
                raise ValueError(f"{TAG}: none of {n} file(s) in {root} could be read")
            print(f"{TAG}: {k} image(s) from {root}, all in this run")
            return {"ui": {"progress": [f"all {k} in this run"]},
                    "result": (images, masks, names, fulls, idxs, [k] * k)}

        # ---- one per run
        i = int(index)
        if i >= n:
            raise ValueError(f"{TAG}: index {i} is past the end -- {n} image(s) in {root}. "
                             f"Set index back to 0 to run the folder again.")
        while i < n:
            try:
                img, m = _load_one(paths[i])
                break
            except Exception as exc:
                print(f"{TAG}: skipping unreadable {paths[i]}: {exc}")
                i += 1
        else:
            raise ValueError(f"{TAG}: nothing readable from index {index} on in {root}")

        name = _stem(paths[i])
        nxt = i + 1
        if nxt < n:
            if prompt is None or unique_id is None:
                print(f"{TAG}: no prompt context, cannot queue the next image")
            else:
                own_inputs = (prompt.get(str(unique_id)) or {}).get("inputs")
                prompt_id, extra = _running_item(unique_id, own_inputs)
                if prompt_id is None:
                    print(f"{TAG}: could not find the running prompt, not continuing")
                else:
                    next_prompt = copy.deepcopy(prompt)
                    next_prompt[str(unique_id)]["inputs"]["index"] = nxt
                    threading.Thread(
                        target=_queue_next_when_done,
                        args=(prompt_id, next_prompt, extra, f"{nxt + 1}/{n} {_stem(paths[nxt])}"),
                        daemon=True).start()
        progress = f"{i + 1} / {n}  {name}" + ("" if nxt < n else "  (done)")
        print(f"{TAG}: {progress}")
        return {"ui": {"progress": [progress]},
                "result": ([img], [m], [name], [paths[i]], [i], [n])}

    @classmethod
    def IS_CHANGED(cls, folder, mode, index, extensions, include_subfolders, sort_by,
                   start_index, limit, **_hidden):
        # **_hidden: ComfyUI passes the hidden prompt/unique_id here too; without
        # accepting them the call raises and the node counts as always-changed.
        if mode == MODE_LOOP:
            return float("nan")     # the loop driver must run every time it is queued
        # list mode: re-run when the folder's contents change, otherwise cached
        root = _resolve_folder(folder)
        if not root or not os.path.isdir(root):
            return float("nan")
        h = hashlib.sha1()
        for p in _list_images(root, extensions, include_subfolders, sort_by):
            st = os.stat(p)
            h.update(f"{p}|{st.st_mtime_ns}|{st.st_size}\n".encode("utf-8", "replace"))
        return h.hexdigest()

    @classmethod
    def VALIDATE_INPUTS(cls, folder, **_):
        root = _resolve_folder(folder)
        if not root or not os.path.isdir(root):
            return f"Not a folder: {folder!r}"
        return True


NODE_CLASS_MAPPINGS = {"LoadImagesFromFolderSeb": LoadImagesFromFolderSeb}
NODE_DISPLAY_NAME_MAPPINGS = {"LoadImagesFromFolderSeb": "Load Images From Folder (Seb)"}

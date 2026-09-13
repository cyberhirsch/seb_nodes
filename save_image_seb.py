"""Save Image (Seb): named, counted PNG saves with an "open folder" button.

Optionally follows the image it came from: connect `source_path` (for example
the `path` output of Load Images From Folder) and pick a `source_mode` --
save next to the source under its own name, or replace the source file itself.
"""
import os
import datetime
import shutil
import folder_paths
import server
import subprocess
import sys
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import numpy as np
import json
import re
import traceback
import asyncio

LAST_SAVED_TO_FOLDER_SEB = None

SOURCE_IGNORE = "ignore source"
SOURCE_SAME_FOLDER = "same folder as source"
SOURCE_REPLACE = "replace source file"
# formats that need explicit save arguments when a source file is replaced in place
_LOSSY = {".jpg": ("JPEG", {"quality": 95}), ".jpeg": ("JPEG", {"quality": 95}),
          ".webp": ("WEBP", {"quality": 95})}


def process_text_pattern(text, date_format_mapping=None):
    if date_format_mapping is None:
        date_format_mapping = {
            "yyyy-MM-dd": "%Y-%m-%d", "MM-dd-yyyy": "%m-%d-%Y", "dd-MM-yyyy": "%d-%m-%Y",
            "yyyyMMdd": "%Y%m%d", "yyMMdd": "%y%m%d",
            "HH-mm-ss": "%H-%M-%S", "HHmmss": "%H%M%S",
            "yyyy-MM-dd_HH-mm-ss": "%Y-%m-%d_%H-%M-%S",
        }
    now = datetime.datetime.now()
    def replace_date(match):
        format_key = match.group(1)
        strftime_format = date_format_mapping.get(format_key)
        return now.strftime(strftime_format) if strftime_format else match.group(0)
    processed_text = re.sub(r"%date:([\w-]+)%", replace_date, text)
    processed_text = processed_text.replace("%timestamp%", str(int(now.timestamp())))
    return processed_text


def _same_file(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _unique_target(folder, base, sep, digits, overwrite, batch, i, avoid=None, prefer_plain=False):
    """The naming rules this node has always used, plus two things for saving next
    to a source: `avoid` is a path that must never come out of here (the source
    file), and `prefer_plain` takes the un-numbered name whenever it is free."""
    name = base if not (batch > 1 and i > 0) else f"{base}{sep}{i:0{digits}}"
    plain = os.path.join(folder, f"{name}.png")
    plain_ok = avoid is None or not _same_file(plain, avoid)
    if plain_ok and (overwrite or (prefer_plain and not os.path.exists(plain))):
        return plain
    # otherwise a counted name (also when the plain one would land on the source)
    scan_prefix = base + sep if base else ""
    current_max = 0
    try:
        for f_name in os.listdir(folder):
            if f_name.startswith(scan_prefix) and f_name.lower().endswith(".png"):
                name_part = f_name[len(scan_prefix):].lower()[:-4]
                token = name_part.split(sep)[0] if sep else name_part
                if token.isdigit():
                    current_max = max(current_max, int(token))
    except FileNotFoundError:
        pass
    except Exception as e_scan:
        print(f"[SaveImageSeb] Error scanning directory for counter: {e_scan}")
    counter = current_max + 1
    for _ in range(1000):
        name = f"{base}{sep}{counter:0{digits}}" + (f"{sep}b{i:02}" if batch > 1 else "")
        target = os.path.join(folder, f"{name}.png")
        if not os.path.exists(target) and (avoid is None or not _same_file(target, avoid)):
            return target
        counter += 1
    return None


class SaveImageSeb:
    _routes_initialized_seb = False

    def __init__(self):
        if not SaveImageSeb._routes_initialized_seb:
            SaveImageSeb._setup_routes_seb()
            SaveImageSeb._routes_initialized_seb = True

    @staticmethod
    @server.PromptServer.instance.routes.get("/comfy_save_seb/open_folder")
    async def route_open_folder_seb(request):
        global LAST_SAVED_TO_FOLDER_SEB
        path_to_open = LAST_SAVED_TO_FOLDER_SEB
        if not path_to_open or not os.path.isdir(path_to_open):
            return server.PromptServer.instance.json_response(
                {"status": "error", "message": f"Folder path not set or invalid for SaveImageSeb: {path_to_open}"}, status=404)
        try:
            loop = asyncio.get_event_loop()
            if sys.platform == "win32":
                await loop.run_in_executor(None, os.startfile, path_to_open)
            elif sys.platform == "darwin":
                await loop.run_in_executor(None, lambda: subprocess.Popen(["open", path_to_open]))
            else:
                await loop.run_in_executor(None, lambda: subprocess.Popen(["xdg-open", path_to_open]))
            return server.PromptServer.instance.json_response({"status": "opened", "path": path_to_open})
        except Exception as e:
            print(f"[SaveImageSeb] Error opening folder: {e}\n{traceback.format_exc()}")
            return server.PromptServer.instance.json_response({"status": "error", "message": str(e)}, status=500)

    @classmethod
    def _setup_routes_seb(cls):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "base_output_folder": ("STRING", {
                    "default": folder_paths.get_output_directory(),
                    "multiline": False,
                }),
                "subfolder_pattern": ("STRING", {
                    "default": "ComfyUI_Seb/%date:yyyy-MM-dd%",
                    "multiline": False,
                    "placeholder": "e.g., MyProject/%date:yyyy-MM-dd% or leave empty"
                }),
                "filename_core": ("STRING", {"default": "Image_Seb"}),
                "filename_separator": ("STRING", {"default": "_"}),
                "include_timestamp_in_filename": ("BOOLEAN", {"default": False}),
                "counter_digits": ("INT", {"default": 5, "min": 1, "max": 10}),
                "save_workflow_data": ("BOOLEAN", {"default": True}),
                "overwrite_existing": ("BOOLEAN", {"default": False}),
            },
            # Optional, so prompts and workflows from before these existed still
            # validate. They render as widgets after the required ones, so saved
            # widget values keep their positions.
            "optional": {
                "source_path": ("STRING", {"forceInput": True,
                                           "tooltip": "Full path of the file this image came from."}),
                "source_mode": ([SOURCE_IGNORE, SOURCE_SAME_FOLDER, SOURCE_REPLACE], {
                    "tooltip": "Needs source_path connected (e.g. the loader's `path`). "
                               "same folder as source: save a PNG next to the source, named "
                               "after it plus source_suffix -- never over it. "
                               "replace source file: overwrite the source itself, same name "
                               "and format, written atomically. ignore source: the usual "
                               "base folder / subfolder / filename_core."}),
                "source_suffix": ("STRING", {"default": "",
                                             "tooltip": "same-folder mode: appended to the source "
                                                        "name, e.g. _4x"}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION = "execute_save_refined_seb"
    OUTPUT_NODE = True
    CATEGORY = "image/save"

    def execute_save_refined_seb(self, images, base_output_folder,
                             subfolder_pattern,
                             filename_core, filename_separator,
                             include_timestamp_in_filename,
                             counter_digits,
                             save_workflow_data,
                             overwrite_existing,
                             source_path=None, source_mode=SOURCE_IGNORE, source_suffix="",
                             prompt=None, extra_pnginfo=None):
        global LAST_SAVED_TO_FOLDER_SEB

        src = str(source_path or "").strip().strip('"')
        use_source = source_mode != SOURCE_IGNORE
        if use_source and not src:
            print(f"[SaveImageSeb] source_mode is '{source_mode}' but source_path is not connected "
                  f"-- saving to the output folder instead")
            use_source = False
        elif use_source and not os.path.isfile(src):
            print(f"[SaveImageSeb] source_path is not a file: {src} -- saving to the output folder instead")
            use_source = False

        if use_source:
            src = os.path.abspath(src)
            current_output_path = os.path.dirname(src)
        else:
            processed_subfolder = process_text_pattern(subfolder_pattern.strip()) if subfolder_pattern.strip() else ""
            if not os.path.isabs(base_output_folder):
                base_output_folder = os.path.join(folder_paths.get_output_directory(), base_output_folder)
            base_output_folder = os.path.normpath(base_output_folder)
            current_output_path = os.path.join(base_output_folder, processed_subfolder) if processed_subfolder else base_output_folder
            current_output_path = os.path.normpath(current_output_path)

        if not os.path.exists(current_output_path):
            try:
                os.makedirs(current_output_path, exist_ok=True)
            except Exception as e:
                print(f"[SaveImageSeb] Error creating directory {current_output_path}: {e}")
                return {"ui": {"text": [f"Error creating directory: {e}"]}}
        LAST_SAVED_TO_FOLDER_SEB = current_output_path

        results_for_ui = []
        batch = len(images)
        for i, image_tensor in enumerate(images):
            img_np = image_tensor.cpu().numpy()
            img_pil = Image.fromarray(np.clip(img_np * 255., 0, 255).astype(np.uint8))
            metadata = PngInfo()

            if extra_pnginfo is not None:
                for key, value in extra_pnginfo.items():
                    if key == "workflow" and not save_workflow_data:
                        continue
                    if value is None: continue
                    try:
                        if isinstance(value, (dict, list)):
                            metadata.add_text(key, json.dumps(value))
                        elif isinstance(value, str):
                            metadata.add_text(key, value)
                        else:
                            metadata.add_text(key, str(value))
                    except Exception as e: print(f"[SaveImageSeb] Warning: Could not add metadata for key '{key}'. Error: {e}")

            # ---- replace the source file itself (first image of a batch) ----------
            if use_source and source_mode == SOURCE_REPLACE and i == 0:
                ext = os.path.splitext(src)[1]
                fmt, kwargs = _LOSSY.get(ext.lower(), (None, {}))
                tmp = src + ".seb_tmp" + ext          # same folder -> os.replace is atomic
                try:
                    if ext.lower() == ".png":
                        img_pil.save(tmp, pnginfo=metadata, compress_level=4)
                    elif fmt:
                        img_pil.save(tmp, fmt, **kwargs)
                    else:
                        img_pil.save(tmp)
                    os.replace(tmp, src)
                    full_file_path = src
                    print(f"[SaveImageSeb] Replaced source: {full_file_path}")
                except Exception as e:
                    print(f"[SaveImageSeb] Error replacing {src}: {e}")
                    try: os.remove(tmp)
                    except OSError: pass
                    continue
            else:
                if use_source:
                    # named after the source, never over it
                    stem = os.path.splitext(os.path.basename(src))[0]
                    parts = [stem + process_text_pattern(source_suffix.strip())]
                    avoid = src
                else:
                    processed_filename_core = process_text_pattern(filename_core.strip())
                    parts = [processed_filename_core] if processed_filename_core else []
                    avoid = None
                if include_timestamp_in_filename:
                    parts.append(datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                filename_base = filename_separator.join(filter(None, parts)) or "image_seb"

                full_file_path = _unique_target(current_output_path, filename_base, filename_separator,
                                                counter_digits, overwrite_existing, batch, i, avoid,
                                                prefer_plain=use_source)
                if full_file_path is None:
                    print(f"[SaveImageSeb] Could not find unique filename for: {filename_base}"); continue
                try:
                    img_pil.save(full_file_path, pnginfo=metadata, compress_level=4)
                    print(f"[SaveImageSeb] Saved: {full_file_path}")
                except Exception as e: print(f"[SaveImageSeb] Error saving {full_file_path}: {e}"); continue

            comfy_output_dir_root = folder_paths.get_output_directory()
            if os.path.normpath(current_output_path).startswith(os.path.normpath(comfy_output_dir_root)):
                subfolder_for_ui = os.path.relpath(current_output_path, comfy_output_dir_root)
                if subfolder_for_ui == ".": subfolder_for_ui = ""
                results_for_ui.append({"filename": os.path.basename(full_file_path), "subfolder": subfolder_for_ui, "type": "output"})

        if results_for_ui: return {"ui": {"images": results_for_ui}}
        return {"ui": {"text": [f"Saved {len(images)} to: {current_output_path}. No previews if outside ComfyUI output." ]}}

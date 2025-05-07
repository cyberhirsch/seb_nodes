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
import torch
import json
import re
import traceback

LAST_SAVED_TO_FOLDER_ADVANCED = None

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

class SaveImageAdvanced:
    _routes_initialized = False
    def __init__(self):
        if not SaveImageAdvanced._routes_initialized:
            SaveImageAdvanced._setup_routes()
            SaveImageAdvanced._routes_initialized = True

    @staticmethod
    @server.PromptServer.instance.routes.get("/comfy_save_advanced/open_folder")
    async def route_open_folder(request):
        global LAST_SAVED_TO_FOLDER_ADVANCED
        path_to_open = LAST_SAVED_TO_FOLDER_ADVANCED
        if not path_to_open or not os.path.isdir(path_to_open):
            return server.PromptServer.instance.json_response(
                {"status": "error", "message": f"Folder path not set or invalid: {path_to_open}"}, status=404)
        try:
            if sys.platform == "win32": os.startfile(path_to_open)
            elif sys.platform == "darwin": subprocess.Popen(["open", path_to_open])
            else: subprocess.Popen(["xdg-open", path_to_open])
            return server.PromptServer.instance.json_response({"status": "opened", "path": path_to_open})
        except Exception as e:
            print(f"[SaveImageAdvanced] Error opening folder: {e}\n{traceback.format_exc()}")
            return server.PromptServer.instance.json_response({"status": "error", "message": str(e)}, status=500)

    @classmethod
    def _setup_routes(cls): pass

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
                    "default": "ComfyUI/%date:yyyy-MM-dd%",
                    "multiline": False,
                    "placeholder": "e.g., MyProject/%date:yyyy-MM-dd% or leave empty"
                }),
                "filename_core": ("STRING", {"default": "ComfyUI"}),
                "filename_separator": ("STRING", {"default": "_"}),
                "include_timestamp_in_filename": ("BOOLEAN", {"default": False}),
                "counter_digits": ("INT", {"default": 5, "min": 1, "max": 10}),
                # "save_prompt_data": ("BOOLEAN", {"default": True}), # Removed
                "save_workflow_data": ("BOOLEAN", {"default": True}),
                "overwrite_existing": ("BOOLEAN", {"default": False}),
            },
            # "optional": { # Removed custom_metadata_json
            #      "custom_metadata_json": ("STRING", {"default": "{}", "multiline": True, "placeholder": '{\n  "my_key": "my_value"\n}'})
            # },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION = "execute_save_refined"
    OUTPUT_NODE = True
    CATEGORY = "image/save"

    def execute_save_refined(self, images, base_output_folder, 
                             subfolder_pattern,
                             filename_core, filename_separator, 
                             include_timestamp_in_filename,
                             counter_digits, 
                             # save_prompt_data, # Removed
                             save_workflow_data,
                             overwrite_existing,
                             prompt=None, extra_pnginfo=None): # Removed custom_metadata_json from params
        global LAST_SAVED_TO_FOLDER_ADVANCED

        processed_subfolder = process_text_pattern(subfolder_pattern.strip()) if subfolder_pattern.strip() else ""
        
        if not os.path.isabs(base_output_folder):
             base_output_folder = os.path.join(folder_paths.get_output_directory(), base_output_folder)
        base_output_folder = os.path.normpath(base_output_folder)

        if processed_subfolder:
            current_output_path = os.path.join(base_output_folder, processed_subfolder)
        else:
            current_output_path = base_output_folder
        current_output_path = os.path.normpath(current_output_path)

        if not os.path.exists(current_output_path):
            try:
                os.makedirs(current_output_path, exist_ok=True)
            except Exception as e:
                print(f"[SaveImageAdvanced] Error creating directory {current_output_path}: {e}")
                return {"ui": {"text": [f"Error creating directory: {e}"]}}
        LAST_SAVED_TO_FOLDER_ADVANCED = current_output_path

        results_for_ui = []
        for i, image_tensor in enumerate(images):
            img_np = image_tensor.cpu().numpy()
            img_pil = Image.fromarray(np.clip(img_np * 255., 0, 255).astype(np.uint8))
            metadata = PngInfo()
            
            # --- Metadata Handling ---
            # Prompt data is no longer explicitly saved via a button
            # It will be saved if it's part of extra_pnginfo and save_workflow_data is true (as ComfyUI includes prompt in workflow)
            # Or if a user *manually* ensures 'prompt' is in extra_pnginfo.
            # For now, we only explicitly handle 'workflow' from extra_pnginfo.

            if extra_pnginfo is not None:
                for key, value in extra_pnginfo.items():
                    if key == "workflow" and not save_workflow_data:
                        continue
                    
                    # If the 'prompt' key exists in extra_pnginfo (e.g. from 'API Save' node),
                    # and save_workflow_data is true (which usually includes prompt), it will be saved.
                    # We are not double-adding it here.
                    
                    if value is None: continue
                    try:
                        if isinstance(value, (dict, list)):
                            metadata.add_text(key, json.dumps(value))
                        elif isinstance(value, str):
                            metadata.add_text(key, value)
                        else:
                            metadata.add_text(key, str(value))
                    except Exception as e: print(f"[SaveImageAdvanced] Warning: Could not add metadata for key '{key}'. Error: {e}")
            
            # Custom metadata JSON parsing removed

            # --- Filename Construction ---
            processed_filename_core = process_text_pattern(filename_core.strip())
            filename_parts = [processed_filename_core] if processed_filename_core else []
            if include_timestamp_in_filename:
                filename_parts.append(datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
            filename_base = filename_separator.join(filter(None, filename_parts)) or "image"
            
            full_file_path = ""
            if overwrite_existing:
                current_file_name_no_ext = filename_base
                if len(images) > 1 and i > 0: current_file_name_no_ext += f"{filename_separator}{i:0{counter_digits}}" # Still use counter_digits for batch index padding
                full_file_path = os.path.join(current_output_path, f"{current_file_name_no_ext}.png")
            else:
                scan_prefix = filename_base + filename_separator if filename_base else ""
                
                # Corrected Counter Logic:
                current_max_counter = 0 # Default for first file if no matches
                try:
                    if os.path.exists(current_output_path): # Only scan if directory exists
                        for f_name in os.listdir(current_output_path):
                            if f_name.startswith(scan_prefix) and f_name.lower().endswith(".png"):
                                # Extract potential counter: scan_prefix_NUMBER...
                                # Remove scan_prefix
                                name_part = f_name[len(scan_prefix):]
                                # Remove .png suffix
                                name_part_no_ext = name_part.lower()[:-4] # remove .png
                                
                                # The part right after scan_prefix and before the next separator (if any) should be the counter
                                potential_num_str = name_part_no_ext.split(filename_separator)[0] if filename_separator else name_part_no_ext
                                
                                if potential_num_str.isdigit():
                                    current_max_counter = max(current_max_counter, int(potential_num_str))
                except FileNotFoundError: # Should not happen if we created the dir
                    pass
                except Exception as e_scan: # Catch other potential errors during scan
                    print(f"[SaveImageAdvanced] Error scanning directory for counter: {e_scan}")

                file_counter = current_max_counter + 1 # Ensures first file is 1 if dir is empty or no matches

                current_file_name_no_ext = f"{filename_base}{filename_separator}{file_counter:0{counter_digits}}"
                if len(images) > 1: current_file_name_no_ext += f"{filename_separator}b{i:02}" # Batch index
                full_file_path = os.path.join(current_output_path, f"{current_file_name_no_ext}.png")
                
                # This loop for ensuring uniqueness is generally good if multiple processes might write,
                # but with single-threaded execution and the above scan, it might be redundant.
                # Keeping it for safety, but the primary counter should be correct.
                loop_breaker = 0
                temp_file_counter = file_counter # Use a temp counter for this uniqueness check loop
                while os.path.exists(full_file_path) and loop_breaker < 1000:
                    temp_file_counter += 1 
                    current_file_name_no_ext = f"{filename_base}{filename_separator}{temp_file_counter:0{counter_digits}}"
                    if len(images) > 1: current_file_name_no_ext += f"{filename_separator}b{i:02}"
                    full_file_path = os.path.join(current_output_path, f"{current_file_name_no_ext}.png")
                    loop_breaker += 1
                if loop_breaker >= 1000:
                    print(f"[SaveImageAdvanced] Could not find unique filename for: {filename_base}"); continue
            try:
                img_pil.save(full_file_path, pnginfo=metadata, compress_level=4)
                print(f"[SaveImageAdvanced] Saved: {full_file_path}")
            except Exception as e: print(f"[SaveImageAdvanced] Error saving {full_file_path}: {e}"); continue

            comfy_output_dir_root = folder_paths.get_output_directory()
            if os.path.normpath(current_output_path).startswith(os.path.normpath(comfy_output_dir_root)):
                subfolder_for_ui = os.path.relpath(current_output_path, comfy_output_dir_root)
                if subfolder_for_ui == ".": subfolder_for_ui = ""
                results_for_ui.append({"filename": os.path.basename(full_file_path), "subfolder": subfolder_for_ui, "type": "output"})
        
        if results_for_ui: return {"ui": {"images": results_for_ui}}
        return {"ui": {"text": [f"Saved {len(images)} to: {current_output_path}. No previews if outside ComfyUI output." ]}}
# G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/save_image_seb.py
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
                             prompt=None, extra_pnginfo=None):
        global LAST_SAVED_TO_FOLDER_SEB 

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
                print(f"[SaveImageSeb] Error creating directory {current_output_path}: {e}")
                return {"ui": {"text": [f"Error creating directory: {e}"]}}
        LAST_SAVED_TO_FOLDER_SEB = current_output_path

        results_for_ui = []
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
            
            processed_filename_core = process_text_pattern(filename_core.strip())
            filename_parts = [processed_filename_core] if processed_filename_core else []
            if include_timestamp_in_filename:
                filename_parts.append(datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
            filename_base = filename_separator.join(filter(None, filename_parts)) or "image_seb" 
            
            full_file_path = ""
            if overwrite_existing:
                current_file_name_no_ext = filename_base
                if len(images) > 1 and i > 0: current_file_name_no_ext += f"{filename_separator}{i:0{counter_digits}}"
                full_file_path = os.path.join(current_output_path, f"{current_file_name_no_ext}.png")
            else:
                scan_prefix = filename_base + filename_separator if filename_base else ""
                current_max_counter = 0
                try:
                    if os.path.exists(current_output_path):
                        for f_name in os.listdir(current_output_path):
                            if f_name.startswith(scan_prefix) and f_name.lower().endswith(".png"):
                                name_part = f_name[len(scan_prefix):]
                                name_part_no_ext = name_part.lower()[:-4]
                                potential_num_str = name_part_no_ext.split(filename_separator)[0] if filename_separator else name_part_no_ext
                                if potential_num_str.isdigit():
                                    current_max_counter = max(current_max_counter, int(potential_num_str))
                except FileNotFoundError: pass
                except Exception as e_scan: print(f"[SaveImageSeb] Error scanning directory for counter: {e_scan}")

                file_counter = current_max_counter + 1
                current_file_name_no_ext = f"{filename_base}{filename_separator}{file_counter:0{counter_digits}}"
                if len(images) > 1: current_file_name_no_ext += f"{filename_separator}b{i:02}"
                full_file_path = os.path.join(current_output_path, f"{current_file_name_no_ext}.png")
                
                loop_breaker = 0
                temp_file_counter = file_counter
                while os.path.exists(full_file_path) and loop_breaker < 1000:
                    temp_file_counter += 1 
                    current_file_name_no_ext = f"{filename_base}{filename_separator}{temp_file_counter:0{counter_digits}}"
                    if len(images) > 1: current_file_name_no_ext += f"{filename_separator}b{i:02}"
                    full_file_path = os.path.join(current_output_path, f"{current_file_name_no_ext}.png")
                    loop_breaker += 1
                if loop_breaker >= 1000:
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
        
        # --- THIS IS THE CORRECTED LINE ---
        return {"ui": {"text": [f"Saved {len(images)} to: {current_output_path}. No previews if outside ComfyUI output." ]}}
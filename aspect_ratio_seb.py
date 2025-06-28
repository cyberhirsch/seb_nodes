# File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/aspect_ratio_seb.py

import math

class AspectRatioSeb:
    """
    A node to calculate width and height based on aspect ratio presets,
    custom values, and a target size controlled by megapixels or a fixed side.
    """
    
    ASPECT_RATIOS = [
        "1:1 (Square)", 
        "4:3 (Classic TV)", 
        "3:2 (Photography)", 
        "16:9 (Widescreen)", 
        "1.85:1 (Cinema)",
        "21:9 (Anamorphic)", 
        "2.39:1 (Cinemascope)",
        "Custom"
    ]
    
    CONTROL_MODES = ["Megapixels", "Fixed Side"]
    FIXED_AXIS = ["Width", "Height"]

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "preset": (s.ASPECT_RATIOS, {"default": "16:9 (Widescreen)"}),
                "custom_aspect_width": ("INT", {"default": 16, "min": 1}),
                "custom_aspect_height": ("INT", {"default": 9, "min": 1}),
                "control_mode": (s.CONTROL_MODES, {"default": "Megapixels"}),
                "target_megapixels": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 64.0, "step": 0.1}),
                "fixed_side_value": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "fixed_side_axis": (s.FIXED_AXIS, {"default": "Width"}),
                "swap_dimensions": ("BOOLEAN", {"default": False}),
                "multiple_of": ("INT", {"default": 8, "min": 1}),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "calculate_aspect_ratio"
    CATEGORY = "utils/aspect_ratio"

    def calculate_aspect_ratio(self, preset, custom_aspect_width, custom_aspect_height, 
                               control_mode, target_megapixels, fixed_side_value, 
                               fixed_side_axis, swap_dimensions, multiple_of):
        
        # 1. Determine the aspect ratio (AR)
        ar_w, ar_h = 1.0, 1.0
        if preset == "Custom":
            ar_w = float(custom_aspect_width)
            ar_h = float(custom_aspect_height)
        else:
            # Extract numbers from the preset string
            parts = preset.split(' ')[0].split(':')
            ar_w = float(parts[0])
            ar_h = float(parts[1])
        
        if ar_h == 0: ar_h = 1.0 # Prevent division by zero

        width = 1024
        height = 1024

        # 2. Calculate initial dimensions based on control mode
        if control_mode == "Megapixels":
            total_pixels = target_megapixels * 1_000_000
            # w * h = total_pixels
            # w / h = ar_w / ar_h  => w = h * (ar_w / ar_h)
            # h^2 * (ar_w / ar_h) = total_pixels
            height = math.sqrt(total_pixels / (ar_w / ar_h))
            width = height * (ar_w / ar_h)
        
        elif control_mode == "Fixed Side":
            if fixed_side_axis == "Width":
                width = float(fixed_side_value)
                height = width * (ar_h / ar_w)
            else: # Height
                height = float(fixed_side_value)
                width = height * (ar_w / ar_h)

        # 3. Round to the nearest multiple (e.g., multiple of 8)
        width = round(width / multiple_of) * multiple_of
        height = round(height / multiple_of) * multiple_of
        
        # 4. Swap if requested
        if swap_dimensions:
            width, height = height, width

        return (int(width), int(height))# File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/aspect_ratio_seb.py

import math

class AspectRatioSeb:
    """
    A node to calculate width and height based on aspect ratio presets,
    custom values, and a target size controlled by megapixels or a fixed side.
    """
    
    # --- UPDATED: Ratios sorted from tallest portrait to widest landscape ---
    ASPECT_RATIOS = [
        # --- Portrait (Tall to Wide) ---
        "9:19.5 (Mobile Portrait)",
        "9:16 (Tall Portrait)",
        "2:3 (Portrait)",
        "3:4 (Portrait)",
        "4:5 (Social Media Portrait)",
        
        # --- Square (Middle) ---
        "1:1 (Square)", 

        # --- Landscape (Narrow to Wide) ---
        "4:3 (Landscape)",
        "3:2 (Landscape)", 
        "16:9 (Widescreen)",
        "19.5:9 (Mobile Landscape)",
        "21:9 (Anamorphic)",
        
        # --- Other ---
        "Custom"
    ]
    
    CONTROL_MODES = ["Megapixels", "Fixed Side"]
    FIXED_AXIS = ["Width", "Height"]

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "preset": (s.ASPECT_RATIOS, {"default": "1:1 (Square)"}), # Default changed to the middle value
                "custom_aspect_width": ("INT", {"default": 16, "min": 1}),
                "custom_aspect_height": ("INT", {"default": 9, "min": 1}),
                "control_mode": (s.CONTROL_MODES, {"default": "Megapixels"}),
                "target_megapixels": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 64.0, "step": 0.1}),
                "fixed_side_value": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "fixed_side_axis": (s.FIXED_AXIS, {"default": "Width"}),
                "multiple_of": ("INT", {"default": 8, "min": 1}),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "calculate_aspect_ratio"
    CATEGORY = "utils/aspect_ratio"

    def calculate_aspect_ratio(self, preset, custom_aspect_width, custom_aspect_height, 
                               control_mode, target_megapixels, fixed_side_value, 
                               fixed_side_axis, multiple_of):
        
        ar_w, ar_h = 1.0, 1.0
        if preset == "Custom":
            ar_w = float(custom_aspect_width)
            ar_h = float(custom_aspect_height)
        else:
            parts = preset.split(' ')[0].split(':')
            ar_w = float(parts[0])
            ar_h = float(parts[1])
        
        if ar_h == 0: ar_h = 1.0

        width, height = 1024, 1024

        if control_mode == "Megapixels":
            total_pixels = target_megapixels * (1024 * 1024)
            height = math.sqrt(total_pixels / (ar_w / ar_h))
            width = height * (ar_w / ar_h)
        
        elif control_mode == "Fixed Side":
            if fixed_side_axis == "Width":
                width = float(fixed_side_value)
                height = width * (ar_h / ar_w)
            else:
                height = float(fixed_side_value)
                width = height * (ar_w / ar_h)

        width = round(width / multiple_of) * multiple_of
        height = round(height / multiple_of) * multiple_of
        
        return (int(width), int(height))
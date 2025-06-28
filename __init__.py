# File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/__init__.py

# Import all your node classes
from .switch_masks_seb import SwitchMasksSeb 
from .save_image_seb import SaveImageSeb
from .aspect_ratio_seb import AspectRatioSeb
from .unified_prompter_seb import UnifiedPrompterSeb # <-- ADD THIS

# Map the internal class names to the classes themselves
NODE_CLASS_MAPPINGS = {
    "SwitchMasksSeb": SwitchMasksSeb,   
    "SaveImageSeb": SaveImageSeb,
    "AspectRatioSeb": AspectRatioSeb,
    "UnifiedPrompterSeb": UnifiedPrompterSeb      # <-- ADD THIS
}

# Map the internal class names to the names you want to see in the UI
NODE_DISPLAY_NAME_MAPPINGS = {
    "SwitchMasksSeb": "Switch Mask (Seb)", 
    "SaveImageSeb": "Save Image (Seb)",
    "AspectRatioSeb": "Aspect Ratio (Seb)",
    "UnifiedPrompterSeb": "Unified Prompter (Seb)" # <-- ADD THIS
}

# This tells ComfyUI to look for JS files in a 'js' sub-folder
WEB_DIRECTORY = "./js" 

# Standard boilerplate
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

# Update the confirmation message
print(">> Seb's Custom Nodes (seb_nodes): Loaded SwitchMasks, SaveImage, AspectRatio & UnifiedPrompter <<")
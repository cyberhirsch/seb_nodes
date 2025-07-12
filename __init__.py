# File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/__init__.py

# Import all node classes
from .switch_masks_seb import SwitchMasksSeb 
from .save_image_seb import SaveImageSeb
from .aspect_ratio_seb import AspectRatioSeb
from .unified_prompter_seb import UnifiedPrompterSeb
from .switch_seb import SwitchSeb
from .depth_inpaint_seb import DepthInpaintSeb

# Map the internal class names to the classes themselves
NODE_CLASS_MAPPINGS = {
    "SwitchMasksSeb": SwitchMasksSeb,   
    "SaveImageSeb": SaveImageSeb,
    "AspectRatioSeb": AspectRatioSeb,
    "UnifiedPrompterSeb": UnifiedPrompterSeb,
    "SwitchSeb": SwitchSeb,
    "DepthInpaintSeb": DepthInpaintSeb
}

# Map the internal class names to the names in the UI
NODE_DISPLAY_NAME_MAPPINGS = {
    "SwitchMasksSeb": "Switch Mask (Seb)", 
    "SaveImageSeb": "Save Image (Seb)",
    "AspectRatioSeb": "Aspect Ratio (Seb)",
    "UnifiedPrompterSeb": "Unified Prompter (Seb)",
    "SwitchSeb": "Switch (Seb)",
    "DepthInpaintSeb": "Depth Inpaint (Seb)" 
}

# This tells ComfyUI to look for JS files in a 'js' sub-folder
WEB_DIRECTORY = "./js" 

# Standard boilerplate
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

# Update the confirmation message
print(">> Seb's Custom Nodes (seb_nodes): Loaded SwitchMasks, SaveImage, AspectRatio, UnifiedPrompter, Switch & DepthInpaint <<")
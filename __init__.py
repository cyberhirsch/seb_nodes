# File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/__init__.py
from .switch_masks_seb import SwitchMasksSeb 
from .save_image_seb import SaveImageSeb

NODE_CLASS_MAPPINGS = {
    "SwitchMasksSeb": SwitchMasksSeb,   
    "SaveImageSeb": SaveImageSeb
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SwitchMasksSeb": "Switch Mask (Seb)", 
    "SaveImageSeb": "Save Image (Seb)"
}

WEB_DIRECTORY = "./js" # This path is relative to the __init__.py file

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

print(">> Seb's Custom Nodes (seb_nodes): Loaded SwitchMasksSeb & SaveImageSeb <<") # Updated print message
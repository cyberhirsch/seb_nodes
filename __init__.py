from .save_advanced_node import SaveImageAdvanced

# Mapping node class names to their Python classes
NODE_CLASS_MAPPINGS = {
    "SaveImageAdvanced": SaveImageAdvanced
}

# Mapping node class names to their display names in the UI
NODE_DISPLAY_NAME_MAPPINGS = {
    "SaveImageAdvanced": "Save Image w/ Path ( Seb )"
}

# Specify the web directory for JavaScript files
WEB_DIRECTORY = "./js"

# For auto-exporting by ComfyUI
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

print("ಝ𝓒 Custom Node: Save Image Advanced loaded (with Open Folder button)")
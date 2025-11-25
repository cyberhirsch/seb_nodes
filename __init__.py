import importlib.util
import sys
import subprocess
import os

# --- Auto-Installation Logic ---
def install_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name
    
    if importlib.util.find_spec(import_name) is None:
        print(f">> Seb Nodes: Installing missing requirement '{package_name}'...")
        try:
            # sys.executable finds the hidden Python automatically
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package_name])
            print(f">> Seb Nodes: '{package_name}' installed successfully.")
        except Exception as e:
            print(f">> Seb Nodes: Failed to install '{package_name}'. Error: {e}")

# List of requirements to check
requirements = [
    ("matplotlib", "matplotlib"),
    ("opencv-python", "cv2"),
    ("transforms3d", "transforms3d"),
    ("networkx", "networkx"),
    ("scikit-image", "skimage")
]

for package, import_name in requirements:
    install_package(package, import_name)
# -------------------------------

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

WEB_DIRECTORY = "./js" 

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

print(">> Seb's Custom Nodes (seb_nodes): Loaded SwitchMasks, SaveImage, AspectRatio, UnifiedPrompter, Switch & DepthInpaint <<")

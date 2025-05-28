# File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/switch_masks_seb.py
import torch

class SwitchMasksSeb:
    """
    A ComfyUI node that selects one of several input masks based on which
    predefined common aspect ratio is closest to the input image's aspect ratio.
    The predefined aspect ratios are: 21:9, 16:9, 3:2, 4:3, 1:1, 3:4, 2:3, 9:16.
    """

    AR_SPECS = [
        {"key_suffix": "21_9", "label": "21:9", "value": 21/9},
        {"key_suffix": "16_9", "label": "16:9", "value": 16/9},
        {"key_suffix": "3_2",  "label": "3:2",  "value": 3/2},
        {"key_suffix": "4_3",  "label": "4:3",  "value": 4/3},
        {"key_suffix": "1_1",  "label": "1:1",  "value": 1.0},
        {"key_suffix": "3_4",  "label": "3:4",  "value": 3/4},
        {"key_suffix": "2_3",  "label": "2:3",  "value": 2/3},
        {"key_suffix": "9_16", "label": "9:16", "value": 9/16},
    ]

    @classmethod
    def INPUT_TYPES(cls):
        required_inputs = {"image": ("IMAGE",)}
        for spec in cls.AR_SPECS:
            input_key = f"mask_{spec['key_suffix']}"
            required_inputs[input_key] = ("MASK",)
        
        return {"required": required_inputs}

    RETURN_TYPES = ("MASK", "STRING")
    RETURN_NAMES = ("selected_mask", "detected_ar_label")
    FUNCTION = "select_mask_by_ar"
    CATEGORY = "mask/util/Seb" 

    def select_mask_by_ar(self, image, **kwargs):
        default_mask_key = None
        default_label = "1:1"
        for spec in self.AR_SPECS:
            if spec["label"] == "1:1":
                default_mask_key = f"mask_{spec['key_suffix']}"
                default_label = spec["label"]
                break
        if not default_mask_key and self.AR_SPECS:
             default_mask_key = f"mask_{self.AR_SPECS[0]['key_suffix']}"
             default_label = self.AR_SPECS[0]['label']
        default_mask_tensor = kwargs.get(default_mask_key) if default_mask_key else None

        class_name_for_log = self.__class__.__name__ 

        if image is None or image.ndim < 3:
            error_msg = f"[{class_name_for_log}]: Invalid image input. Defaulting to mask for {default_label}."
            print(error_msg)
            if default_mask_tensor is None and self.AR_SPECS:
                first_mask_key = f"mask_{self.AR_SPECS[0]['key_suffix']}"
                default_mask_tensor = kwargs.get(first_mask_key)
            return (default_mask_tensor, f"Error: Invalid Image (using {default_label} mask)")

        _batch_size, height, width, _channels = image.shape

        if width == 0 or height == 0:
            error_msg = f"[{class_name_for_log}]: Image has zero dimension ({width}x{height}). Defaulting to mask for {default_label}."
            print(error_msg)
            return (default_mask_tensor, f"Error: Zero Dim Image (using {default_label} mask)")
        
        image_ar = width / float(height)
        closest_ar_spec = None
        min_diff = float('inf')

        for spec in self.AR_SPECS:
            diff = abs(image_ar - spec["value"])
            if diff < min_diff:
                min_diff = diff
                closest_ar_spec = spec

        if closest_ar_spec is None:
            error_msg = f"[{class_name_for_log}]: Could not determine closest AR. Defaulting to mask for {default_label}."
            print(error_msg)
            return (default_mask_tensor, f"Error: AR Undetermined (using {default_label} mask)")

        selected_mask_input_key = f"mask_{closest_ar_spec['key_suffix']}"
        selected_mask = kwargs[selected_mask_input_key]
        selected_label = closest_ar_spec["label"]

        print(f"[{class_name_for_log}]: Image {width}x{height} (AR: {image_ar:.3f}). Closest to {selected_label} (AR: {closest_ar_spec['value']:.3f}, diff: {min_diff:.3f}). Selected mask for {selected_label}.")
        return (selected_mask, selected_label)
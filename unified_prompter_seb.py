# =================================================================================
# File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/unified_prompter_seb.py
# Description: Final, complete code for the Unified Prompter node.
# Features:
# - Dynamically loads styles from unified_prompter_styles.json.
# - Provides dropdowns for multiple positive prompt categories.
# - Integrates a "Random" option directly into each positive dropdown.
# - Allows combining up to 3 negative prompt presets.
# - Outputs final conditioning and the generated text prompts for preview.
# - Is compatible with SD1.5, SDXL, and multi-encoder (FLUX) models.
# - Is free of Unicode characters for maximum compatibility.
# =================================================================================

import os
import json
import torch
import random
from collections import OrderedDict

# --- Constants ---
NODE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(NODE_DIR, "unified_prompter_styles.json")

# --- Helper Function ---
def load_and_prepare_styles():
    """Loads styles from JSON and prepares them for ComfyUI dropdowns."""
    try:
        with open(JSON_PATH, 'r', encoding='utf-8-sig') as f:
            data = json.load(f, object_pairs_hook=OrderedDict)
        
        dropdowns = {}
        for category, items in data.items():
            if category.startswith("_"): continue
            # Create the base list of options for each category, e.g., ["None", "Photorealistic", "Cinematic", ...]
            options = ["None"] + [name for name, value in items.items() if value != "category"]
            dropdowns[category] = options
        return data, dropdowns
    except Exception as e:
        print(f"[UnifiedPrompter] CRITICAL ERROR: Could not load or parse styles.json. Please check its format. Error: {e}")
        return {}, {}

# --- Load Data on Startup ---
STYLE_DATA, DROPDOWNS = load_and_prepare_styles()

class UnifiedPrompterSeb:
    """A Prompt Construction Kit node with a 'Random' option in each dropdown."""

    @classmethod
    def INPUT_TYPES(s):
        required_inputs = {
            "clip": ("CLIP", ),
            "main_prompt": ("STRING", {"multiline": True, "default": "a beautiful landscape"}),
        }
        
        # Dynamically create the UI inputs
        for category, options in DROPDOWNS.items():
            if category != "negative_prompts":
                # For each positive category, create a new list with "Random" inserted after "None"
                options_with_random = options[:1] + ["Random"] + options[1:]
                required_inputs[category] = (options_with_random, )

        # Negative prompt section
        required_inputs["base_negative_prompt"] = ("STRING", {"multiline": True, "default": ""})
        if "negative_prompts" in DROPDOWNS:
             required_inputs["negative_preset_1"] = (DROPDOWNS["negative_prompts"], )
             required_inputs["negative_preset_2"] = (DROPDOWNS["negative_prompts"], )
             required_inputs["negative_preset_3"] = (DROPDOWNS["negative_prompts"], )

        required_inputs["log_prompts"] = ("BOOLEAN", {"default": False})
        
        return {"required": required_inputs}

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "negative", "positive_text", "negative_text")
    FUNCTION = "generate_conditioning"
    CATEGORY = "utils/prompting"

    def generate_conditioning(self, clip, main_prompt, base_negative_prompt, log_prompts, **kwargs):
        
        # --- 1. Assemble Positive Prompt ---
        positive_parts = [main_prompt]
        
        if log_prompts:
            print("--- Unified Prompter Selections ---")
        
        # Iterate through all known positive style categories from the JSON file
        for category in STYLE_DATA:
            if category.startswith("_") or category == "negative_prompts":
                continue

            # This is the user's literal choice from the dropdown menu
            user_selection = kwargs.get(category, "None")
            final_selection = user_selection

            # If the user chose "Random", we override their selection
            if user_selection == "Random":
                # Get the original list of options for this category (which doesn't include "Random")
                valid_choices = DROPDOWNS[category]
                # Filter out "None" so it isn't picked randomly
                valid_choices = [item for item in valid_choices if item != "None"]
                
                if valid_choices:
                    # Pick a random item from the filtered list
                    final_selection = random.choice(valid_choices)
                    if log_prompts:
                        print(f"Randomized '{category}': {final_selection}")
            
            # Add the text for the final selection (either user's choice or random choice)
            if final_selection and final_selection != "None":
                prompt_text = STYLE_DATA[category].get(final_selection, "")
                if prompt_text:
                    positive_parts.append(prompt_text)

        final_pos = ", ".join(filter(None, positive_parts))

        # --- 2. Assemble Negative Prompt ---
        negative_parts = [base_negative_prompt]
        for i in range(1, 4):
            preset_key = f"negative_preset_{i}"
            selected_negative = kwargs.get(preset_key, "None")
            if selected_negative != "None" and "negative_prompts" in STYLE_DATA:
                prompt_text = STYLE_DATA["negative_prompts"].get(selected_negative, "")
                if prompt_text:
                    negative_parts.append(prompt_text)
        final_neg = ", ".join(filter(None, negative_parts))

        # --- 3. Log Final Prompts if Requested ---
        if log_prompts:
            print("--- Final Assembled Prompts ---")
            print(f"Positive: {final_pos}")
            print(f"Negative: {final_neg}")
            print("-------------------------------")

        # --- 4. Encode Prompts (Universal Method) ---
        positive_cond = clip.encode_from_tokens_scheduled(clip.tokenize(final_pos))
        negative_cond = clip.encode_from_tokens_scheduled(clip.tokenize(final_neg))

        # --- 5. Return All Outputs ---
        return (positive_cond, negative_cond, final_pos, final_neg)
# G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/switch_seb.py
# Python backend for a switch with 5 static inputs.

class AnyType(str):
  def __ne__(self, __value: object) -> bool: return False

any_type = AnyType("*")

class SwitchSeb:
  NAME = "Switch (Seb)"
  CATEGORY = "seb_nodes"

  @classmethod
  def INPUT_TYPES(cls):
    return {
      "required": {
        "select": ("INT", {"default": 1, "min": 1, "max": 5, "step": 1}),
      },
      "optional": {
        "any_input_1": (any_type,), "any_input_2": (any_type,),
        "any_input_3": (any_type,), "any_input_4": (any_type,),
        "any_input_5": (any_type,),
      }
    }

  RETURN_TYPES = (any_type,); RETURN_NAMES = ('output',); FUNCTION = "switch"
  def switch(self, select, **kwargs):
    return (kwargs.get(f"any_input_{select}"),)
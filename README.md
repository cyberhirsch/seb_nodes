# Seb Nodes for ComfyUI

A collection of custom nodes for ComfyUI by Seb (cyberhirsch), enhancing image saving and mask manipulation workflows.

**Current Nodes:**
1.  **Save Image (Seb)**: Advanced image saving with dynamic paths and an "Open Folder" button.
2.  **Switch Mask (Seb)**: Selects a mask based on image aspect ratio from multiple inputs.

---

## 1. Save Image (Seb)

Provides more control over image saving, including dynamic subfolder creation and a convenient button to open the last used output folder directly from the UI.

### Features (Save Image (Seb))

*   **Custom Base Output Folder**: Specify any root directory for your saves (defaults to ComfyUI's output).
*   **Dynamic Subfolder Creation**: Use patterns like `%date:yyyy-MM-dd%` in the `subfolder_pattern` input to automatically organize saves (e.g., into daily folders). Leave blank to save directly to the base folder.
*   **Flexible Filename Generation**:
    *   Set a core filename component (`filename_core`).
    *   Choose a separator (`filename_separator`).
    *   Optionally include a high-resolution timestamp (`include_timestamp_in_filename`).
    *   Configurable counter padding (`counter_digits`).
    *   Batch index automatically added for batches (`_b00`, `_b01`, etc.).
*   **Save Workflow Data**: Option to embed the full workflow JSON into the saved PNG metadata.
*   **Overwrite Option**: Choose whether to overwrite existing files or always generate a unique filename using the counter.
*   **✨ Open Last Seb Output Folder Button ✨**: Quickly navigate to the folder where this node last saved images directly from the ComfyUI interface (opens on the server machine).

### Usage / Node Inputs (Save Image (Seb))

*   **`images`**: Connect the image output from another node here.
*   **`base_output_folder`**: The root directory for saving. Can be absolute (e.g., `D:\ComfyOutput`) or relative (e.g., `MySaves`, which will be inside `ComfyUI/output/MySaves`).
*   **`subfolder_pattern`**: Defines the subfolder structure within the base folder.
    *   Use patterns like `%date:yyyy-MM-dd%`, `%date:yyyyMM%`, etc.
    *   Example: `ProjectX/%date:yyyy-MM-dd%` creates `D:\ComfyOutput\ProjectX\2025-05-06\`.
    *   Leave blank to save directly into `base_output_folder`.
    *   Default: `ComfyUI_Seb/%date:yyyy-MM-dd%`
*   **`filename_core`**: The main text part of the filename (e.g., "CharacterPortrait"). Default: `Image_Seb`.
*   **`filename_separator`**: Character used to join filename parts (e.g., `_` or `-`).
*   **`include_timestamp_in_filename`**: (Toggle) If enabled, adds a detailed timestamp (YYYYMMDDHHMMSSms) to the filename for uniqueness.
*   **`counter_digits`**: Number of digits for the counter (e.g., 5 results in `00001`, `00002`).
*   **`save_workflow_data`**: (Toggle) If enabled, embeds the workflow JSON into the PNG metadata.
*   **`overwrite_existing`**: (Toggle) If enabled, may overwrite files if the generated name exists (primarily affects the first image in a potential batch). If disabled (default), it guarantees a unique filename by incrementing the counter.
*   **`Open Last Seb Output Folder` (Button)**: Click this after a successful save to open the directory where the files were saved. **Note:** This opens the folder on the computer running the ComfyUI server backend.

---

## 2. Switch Mask (Seb)

Selects a mask from a set of provided mask inputs based on which predefined common aspect ratio is closest to the input image's aspect ratio. If no mask is provided for the closest AR, no mask is output.

![Placeholder - Add Screenshot of Switch Mask (Seb) Node Here](placeholder_switch_mask_seb.png)
*(Replace `placeholder_switch_mask_seb.png` with an actual screenshot)*

### Features (Switch Mask (Seb))

*   **Aspect Ratio Detection**: Calculates the aspect ratio of the input `image`.
*   **Nearest Match**: Compares the image's AR to a predefined list of common aspect ratios:
    *   21:9, 16:9, 3:2, 4:3, 1:1, 3:4, 2:3, 9:16
*   **Conditional Mask Output**:
    *   Outputs the mask connected to the input slot corresponding to the closest detected AR.
    *   If the specific mask input for the matched AR is not connected, it outputs `None` (no mask).
*   **Label Output**: Outputs a string indicating the `detected_ar_label` (e.g., "16:9", "1:1").

### Usage / Node Inputs & Outputs (Switch Mask (Seb))

**Inputs:**
*   **`image`**: (Required) The IMAGE tensor to analyze for aspect ratio.
*   **`mask_21_9`**: (Optional) MASK input for 21:9 aspect ratio.
*   **`mask_16_9`**: (Optional) MASK input for 16:9 aspect ratio.
*   **`mask_3_2`**: (Optional) MASK input for 3:2 aspect ratio.
*   **`mask_4_3`**: (Optional) MASK input for 4:3 aspect ratio.
*   **`mask_1_1`**: (Optional) MASK input for 1:1 aspect ratio.
*   **`mask_3_4`**: (Optional) MASK input for 3:4 aspect ratio.
*   **`mask_2_3`**: (Optional) MASK input for 2:3 aspect ratio.
*   **`mask_9_16`**: (Optional) MASK input for 9:16 aspect ratio.

**Outputs:**
*   **`selected_mask`**: The MASK tensor corresponding to the detected aspect ratio, or `None` if no matching mask input was provided.
*   **`detected_ar_label`**: A STRING indicating the label of the closest aspect ratio (e.g., "16:9", "Error: Invalid Image").

---

## Installation (for Seb Nodes package)

**Recommended: Using ComfyUI-Manager**

1.  Install [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager).
2.  Open ComfyUI and click the "Manager" button.
3.  Click "Install Custom Nodes".
4.  Search for "**Seb Nodes**" (or "cyberhirsch" if that's how it's listed due to your GitHub username).
5.  Click "Install" on the "Seb Nodes" package.
6.  **Restart ComfyUI** completely.

**Manual Installation**

1.  Navigate to your ComfyUI installation directory (e.g., `G:\AI\ComfyUI_windows_portable\ComfyUI\`).
2.  Go into the `custom_nodes` subfolder.
3.  Open a terminal/command prompt in this directory.
4.  Clone your repository:
    ```bash
    git clone https://github.com/cyberhirsch/seb_nodes.git seb_nodes
    ```
    *(Assuming your GitHub username is `cyberhirsch` and repository is `seb_nodes`. Adjust if different. Cloning into a folder named `seb_nodes` ensures it matches the package name.)*
5.  **Restart ComfyUI** completely. The nodes should appear under their respective categories ("image/save" and "mask/util/Seb").

## General Notes & Limitations

*   The **"Open Last Seb Output Folder"** button on the `Save Image (Seb)` node executes the command on the **server machine** where the Python backend is running. If you are accessing ComfyUI remotely via a web browser, it will open the folder on the server, not your local client machine.
*   If you update the node's Python code (especially changing `INPUT_TYPES`), you may encounter UI display glitches in existing workflows using these nodes. The best fix is usually to delete the old node instance and add a new one to your workflow.

## Dependencies

*   Requires a standard ComfyUI installation.
*   No additional external Python packages are needed for these nodes.

## License

*   MIT License 
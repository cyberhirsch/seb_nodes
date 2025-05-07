# ComfyUI Save Image Advanced (with Open Folder Button)

A custom node for ComfyUI providing more control over image saving, including dynamic subfolder creation and a convenient button to open the last used output folder directly from the UI.

![Placeholder - Add Screenshot of Node Here](placeholder_screenshot.png)
*(Replace `placeholder_screenshot.png` with a link to or path of an actual screenshot of your node's UI)*

## Features

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
*   **✨ Open Last Output Folder Button ✨**: Quickly navigate to the folder where the node last saved images directly from the ComfyUI interface (opens on the server machine).

## Installation

**Recommended: Using ComfyUI-Manager**

1.  Install [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager).
2.  Open ComfyUI and click the "Manager" button.
3.  Click "Install Custom Nodes".
4.  Search for "Save Image Advanced" (or your node's name once listed).
5.  Click "Install" on the desired node.
6.  **Restart ComfyUI** completely.

**Manual Installation**

1.  Navigate to your ComfyUI installation directory.
2.  Go into the `custom_nodes` subfolder.
3.  Open a terminal/command prompt in this directory.
4.  Run the following command:
    ```bash
    git clone https://github.com/YourUsername/YourRepoName.git 
    ```
    *(Replace `YourUsername/YourRepoName.git` with the actual URL of your GitHub repository)*
5.  **Restart ComfyUI** completely.

## Usage / Node Inputs

*   **`images`**: Connect the image output from another node here.
*   **`base_output_folder`**: The root directory for saving. Can be absolute (e.g., `D:\ComfyOutput`) or relative (e.g., `MySaves`, which will be inside `ComfyUI/output/MySaves`).
*   **`subfolder_pattern`**: Defines the subfolder structure within the base folder.
    *   Use patterns like `%date:yyyy-MM-dd%`, `%date:yyyyMM%`, etc.
    *   Example: `ProjectX/%date:yyyy-MM-dd%` creates `D:\ComfyOutput\ProjectX\2025-05-06\`.
    *   Leave blank to save directly into `base_output_folder`.
    *   Default: `ComfyUI/%date:yyyy-MM-dd%`
*   **`filename_core`**: The main text part of the filename (e.g., "CharacterPortrait").
*   **`filename_separator`**: Character used to join filename parts (e.g., `_` or `-`).
*   **`include_timestamp_in_filename`**: (Toggle) If enabled, adds a detailed timestamp (YYYYMMDDHHMMSSms) to the filename for uniqueness.
*   **`counter_digits`**: Number of digits for the counter (e.g., 5 results in `00001`, `00002`).
*   **`save_workflow_data`**: (Toggle) If enabled, embeds the workflow JSON into the PNG metadata.
*   **`overwrite_existing`**: (Toggle) If enabled, may overwrite files if the generated name exists (primarily affects the first image in a potential batch). If disabled (default), it guarantees a unique filename by incrementing the counter.
*   **`Open Last Output Folder` (Button)**: Click this after a successful save to open the directory where the files were saved. **Note:** This opens the folder on the computer running the ComfyUI server backend.

## Notes & Limitations

*   The **"Open Last Output Folder"** button executes the command on the **server machine** where the Python backend is running. If you are accessing ComfyUI remotely via a web browser, it will open the folder on the server, not your local machine.
*   If you update the node's Python code (especially changing `INPUT_TYPES`), you may encounter UI display glitches in existing workflows. The best fix is usually to delete the old node instance and add a new one to your workflow.

## Dependencies

*   Requires a standard ComfyUI installation.
*   No additional external Python packages are needed.

## License

*   MIT License

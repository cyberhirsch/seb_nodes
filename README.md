# Seb Nodes for ComfyUI

A suite of essential utilities for ComfyUI by Seb (cyberhirsch), designed to streamline your creative process from initial setup to final output.

---

## 📋 Table of Contents

- [🚀 Installation](#-installation)
- [📦 The Nodes: A Workflow Approach](#-the-nodes-a-workflow-approach)
  - [1. Aspect Ratio (Seb)](#1-aspect-ratio-seb)
   Nodes for ComfyUI

A suite of essential utilities for ComfyUI by Seb (cyberhirsch), designed to streamline your creative process from initial setup to final output.

---

## 📋 Table of Contents

- [🚀 Installation](#-installation)
- [📦 The Nodes: A Workflow Approach](#-the-nodes-a-workflow-approach)
  - [1. Aspect Ratio (Seb)](#1-aspect-ratio-seb)
  - [2. Unified Prompter (Seb)](#2-unified-prompter-seb)
  - [3. Switch Mask (Seb)](#3-switch-mask-seb)
  - [4. Save Image (Seb)](#4-save-image-seb)
- [📄 License](#-license)

---

## 🚀 Installation

### Recommended: Using ComfyUI-Manager

1.  If you haven't already, install the [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager).
2.  In your ComfyUI interface, click the **Manager** button.
3.  Click **Install Custom Nodes**.
4.  Search for `Seb Nodes` or `cyberhirsch`.
5.  Click the **Install** button next to the package.
6.  **Restart ComfyUI** completely.

### Manual Installation

1.  Navigate to your ComfyUI installation directory.
2.  Enter the `custom_nodes` subfolder (e.g., `ComfyUI/custom_nodes/`).
3.  Open a terminal or command prompt in this directory.
4.  Clone the repository:
    ```bash
    git clone https://github.com/cyberhirsch/seb_nodes.git
    ```
5.  **Restart ComfyUI** completely.

---

## 📦 The Nodes: A Workflow Approach

This collection is designed to work together to solve common workflow challenges.

### 1. Aspect Ratio (Seb)

**(Category: `utils/aspect_ratio`)**

Stop guessing your dimensions. This node intelligently calculates `width` and `height` for you, ensuring your images are perfectly sized and compatible with your models.

![Screenshot of the Aspect Ratio (Seb) node](screenshots/Aspect%20Ratio.png)

#### Key Features

*   **Preset Library**: A logically sorted list of common aspect ratios, from tall portrait (`9:16`) to cinematic widescreen (`21:9`).
*   **Intelligent Sizing Modes**:
    *   **Megapixels**: Set a target image complexity (e.g., `1.0` for a ~1MP image) and let the node handle the math across different shapes.
    *   **Fixed Side**: Lock in a specific width or height, and the node calculates the other dimension to match your chosen ratio.
*   **Dynamic UI**: The interface smartly hides irrelevant options to reduce clutter.
*   **Model-Safe Output**: A `multiple_of` setting ensures your final dimensions are divisible by a required number (like 8), preventing model errors.

> **Pro-Tip:** Use **Megapixels** mode when experimenting with different aspect ratios. It keeps your VRAM usage and generation time consistent, allowing for fairer comparisons between compositions.

### 2. Unified Prompter (Seb)

**(Category: `utils/prompting`)**

Build complex, high-quality prompts with an organized, modular system. This node replaces dozens of text boxes with a clean, dropdown-based interface powered by a simple, external JSON file.

![Screenshot of the Unified Prompter (Seb) node](screenshots/Unified%20Prompter.png)

#### Key Features

*   **External JSON Stylesheet**: All dropdown options are loaded from `unified_prompter_styles.json`. Add, edit, and share entire prompt libraries without ever touching the code.
*   **Categorized Modifiers**: Organize your prompt fragments into logical groups like `technique`, `composition`, `lighting`, and `artist`.
*   **Creative Roulette**: Every positive prompt category includes a **"Random"** option. Let the node surprise you with new style combinations to break creative blocks.
*   **Multi-Layered Negatives**: Stack up to three negative prompt presets (e.g., a base negative, a model-specific one, and an aesthetic filter) for fine-tuned control.
*   **Transparent Output**: Outputs the final text prompts as strings, so you can preview exactly what's being sent to the sampler.

> **Pro-Tip:** Create different style files for different themes (e.g., `scifi_styles.json`, `fantasy_styles.json`). Before starting ComfyUI, just rename the one you want to use to `unified_prompter_styles.json`.

### 3. Switch Mask (Seb)

**(Category: `mask/util/Seb`)**

Automate your masking process for any image shape. This node receives an image and selects the most appropriate mask from a set of eight aspect-ratio-specific inputs.

![Screenshot of the Switch Mask (Seb) node](screenshots/Switch%20Mask.png)

#### Key Features

*   **Dynamic Mask Selection**: Automatically detects the incoming image's aspect ratio and outputs the mask from the corresponding input slot.
*   **Failsafe Design**: If no mask is connected to the input that best matches the image, the node outputs nothing, preventing errors in your workflow.
*   **Clear Feedback**: Outputs a text label of the detected aspect ratio (e.g., "16:9") for verification.

> **Example Workflow:** Combine this with a 'Vignette' or 'Blur' node. Create masks for 16:9, 1:1, and 9:16, and connect them to the respective inputs. This node will now automatically apply the correct vignette to any image, making your post-processing workflow universal.

### 4. Save Image (Seb)

**(Category: `image/save`)**

Take full control of your file organization and naming. This node is a super-powered replacement for the default save functionality.

![Screenshot of the Save Image (Seb) node](screenshots/Save%20Image.png)

#### Key Features

*   **Granular File Naming**: Construct filenames with a core component, a separator, an optional timestamp, and an automatic batch counter.
*   **Dynamic Folder Sorting**: Use date and time patterns (e.g., `%date:yyyy-MM-dd%`) to automatically sort your images into a clean folder structure.
*   **Instant Access Button**: Includes an **"Open Last Output Folder"** button directly on the node to immediately navigate to where your files were saved.
*   **Metadata Control**: Choose whether to embed the full ComfyUI workflow into the saved PNG file.

> **Pro-Tip:** The `filename_core` input can be connected to the output of other nodes. For example,- [2. Unified Prompter (Seb)](#2-unified-prompter-seb)
  - [3. Switch Mask (Seb)](#3-switch-mask-seb)
  - [4. Save Image (Seb)](#4-save-image-seb)
- [📄 License](#-license)

---

## 🚀 Installation

### Recommended: Using ComfyUI-Manager

1.  If you haven't already, install the [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager).
2.  In your ComfyUI interface, click the **Manager** button.
3.  Click **Install Custom Nodes**.
4.  Search for `Seb Nodes` or `cyberhirsch`.
5.  Click the **Install** button next to the package.
6.  **Restart ComfyUI** completely.

### Manual Installation

1.  Navigate to your ComfyUI installation directory.
2.  Enter the `custom_nodes` subfolder (e.g., `ComfyUI/custom_nodes/`).
3.  Open a terminal or command prompt in this directory.
4.  Clone the repository:
    ```bash
    git clone https://github.com/cyberhirsch/seb_nodes.git
    ```
5.  **Restart ComfyUI** completely.

---

## 📦 The Nodes: A Workflow Approach

This collection is designed to work together to solve common workflow challenges.

### 1. Aspect Ratio (Seb)

**(Category: `utils/aspect_ratio`)**

Stop guessing your dimensions. This node intelligently calculates `width` and `height` for you, ensuring your images are perfectly sized and compatible with your models.

![Screenshot of the Aspect Ratio node](screenshots/Aspect%20Ratio.png)

#### Key Features

*   **Preset Library**: A logically sorted list of common aspect ratios, from tall portrait (`9:16`) to cinematic widescreen (`21:9`).
*   **Intelligent Sizing Modes**:
    *   **Megapixels**: Set a target image complexity (e.g., `1.0` for a ~1MP image) and let the node handle the math across different shapes.
    *   **Fixed Side**: Lock in a specific width or height, and the node calculates the other dimension to match your chosen ratio.
*   **Dynamic UI**: The interface smartly hides irrelevant options to reduce clutter.
*   **Model-Safe Output**: A `multiple_of` setting ensures your final dimensions are divisible by a required number (like 8), preventing model errors.

> **Pro-Tip:** Use **Megapixels** mode when experimenting with different aspect ratios. It keeps your VRAM usage and generation time consistent, allowing for fairer comparisons between compositions.

### 2. Unified Prompter (Seb)

**(Category: `utils/prompting`)**

Build complex, high-quality prompts with an organized, modular system. This node replaces dozens of text boxes with a clean, dropdown-based interface powered by a simple, external JSON file.

![Screenshot of the Unified Prompter node](screenshots/Unified%20Prompter.png)

#### Key Features

*   **External JSON Stylesheet**: All dropdown options are loaded from `unified_prompter_styles.json`. Add, edit, and share entire prompt libraries without ever touching the code.
*   **Categorized Modifiers**: Organize your prompt fragments into logical groups like `technique`, `composition`, `lighting`, and `artist`.
*   **Creative Roulette**: Every positive prompt category includes a **"Random"** option. Let the node surprise you with new style combinations to break creative blocks.
*   **Multi-Layered Negatives**: Stack up to three negative prompt presets (e.g., a base negative, a model-specific one, and an aesthetic filter) for fine-tuned control.
*   **Transparent Output**: Outputs the final text prompts as strings, so you can preview exactly what's being sent to the sampler.

> **Pro-Tip:** Create different style files for different themes (e.g., `scifi_styles.json`, `fantasy_styles.json`). Before starting ComfyUI, just rename the one you want to use to `unified_prompter_styles.json`.

### 3. Switch Mask (Seb)

**(Category: `mask/util/Seb`)**

Automate your masking process for any image shape. This node receives an image and selects the most appropriate mask from a set of eight aspect-ratio-specific inputs.

![Screenshot of the Switch Mask node](screenshots/Switch%20Mask.png)

#### Key Features

*   **Dynamic Mask Selection**: Automatically detects the incoming image's aspect ratio and outputs the mask from the corresponding input slot.
*   **Failsafe Design**: If no mask is connected to the input that best matches the image, the node outputs nothing, preventing errors in your workflow.
*   **Clear Feedback**: Outputs a text label of the detected aspect ratio (e.g., "16:9") for verification.

> **Example Workflow:** Combine this with a 'Vignette' or 'Blur' node. Create masks for 16:9, 1:1, and 9:16, and connect them to the respective inputs. This node will now automatically apply the correct vignette to any image, making your post-processing workflow universal.

### 4. Save Image (Seb)

**(Category: `image/save`)**

Take full control of your file organization and naming. This node is a super-powered replacement for the default save functionality.

![Screenshot of the Save Image node](screenshots/Save%20Image.png)

#### Key Features

*   **Granular File Naming**: Construct filenames with a core component, a separator, an optional timestamp, and an automatic batch counter.
*   **Dynamic Folder Sorting**: Use date and time patterns (e.g., `%date:yyyy-MM-dd%`) to automatically sort your images into a clean folder structure.
*   **Instant Access Button**: Includes an **"Open Last Output Folder"** button directly on the node to immediately navigate to where your files were saved.
*   **Metadata Control**: Choose whether to embed the full ComfyUI workflow into the saved PNG file.

> **Pro-Tip:** The `filename_core` input can be connected to the output of other nodes. For example, connect the `seed` number from a "Primitive" node to include the seed directly in every filename.

---

## 📄 License

This project is licensed under the **MIT License**.

``` connect the `seed` number from a "Primitive" node to include the seed directly in every filename.

---

## 📄 License

This project is licensed under the **MIT License**.

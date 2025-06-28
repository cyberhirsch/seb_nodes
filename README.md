# Seb Nodes for ComfyUI

A suite of essential utilities for ComfyUI by Seb (cyberhirsch), designed to streamline your creative process from initial setup to final output.

---

## 📋 Table of Contents

- [🚀 Installation](#-installation)
- [📦 The Nodes](#-the-nodes)
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
4.  Search for `Seb`.
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

## 📦 The Nodes

This collection is designed to work together to solve common workflow challenges.

### 1. Aspect Ratio (Seb)

**(Category: `utils/aspect_ratio`)**

Stop guessing your dimensions. This node intelligently calculates `width` and `height` for you, ensuring your images are perfectly sized and compatible with your models.

<img src="screenshots/Aspect%20Ratio.png" alt="Screenshot of the Aspect Ratio (Seb) node" width="427">

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

<img src="screenshots/Unified%20Prompter.png" alt="Screenshot of the Unified Prompter (Seb) node" width="591">

#### Key Features

*   **External JSON Stylesheet**: All dropdown options are loaded from `unified_prompter_styles.json`. Add, edit, and share entire prompt libraries without ever touching the code.
*   **Categorized Modifiers**: Organize your prompt fragments into logical groups like `technique`, `composition`, `lighting`, and `artist`.
*   **Creative Roulette**: Every positive prompt category includes a **"Random"** option. Let the node surprise you with new style combinations to break creative blocks.
*   **Multi-Layered Negatives**: Stack up to three negative prompt presetsTip:** The `filename_core` input can be connected to the output of other nodes. For example, connect the `seed` number from a "Primitive" node to include the seed directly in every filename.

---

## 📄 License

This project is licensed under the **MIT License**.

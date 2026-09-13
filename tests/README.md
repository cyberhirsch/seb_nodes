# 360 tests

Every test here drives a **real headless Chromium** (Playwright) against a
**running ComfyUI**. The embedded browser pane in the desktop app does not
composite -- `requestAnimationFrame` never fires -- so nothing WebGL-based can
be checked through it. Headless Chromium composites, so the editor and the
node-face preview actually paint and can be measured by pixel.

## One-time setup

    pip install playwright pillow numpy opencv-python
    python -m playwright install chromium

## Start a scratch ComfyUI

Never test against the instance you are working in; the tests clear the graph
and commit into the panorama store. For the desktop install:

    G:\AI\ComfyUI\.venv\Scripts\python.exe G:\AI\ComfyUI\Install\resources\ComfyUI\main.py ^
        --port 8189 --base-directory G:\AI\ComfyUI ^
        --front-end-root G:\AI\ComfyUI\Install\resources\ComfyUI\web_custom_versions\desktop_app ^
        --cpu --disable-auto-launch

`--front-end-root` matters: the desktop app ships the frontend in its Electron
bundle, not as the pip package `main.py` looks for. `--cpu` is fine -- nothing
here samples.

## Run

    python tests/run_all.py            # everything
    python tests/run_all.py mask yaw   # by name

`run_all.py` writes the marker panoramas into the instance's input folder on
first use (`make_testpano.py`), runs each `test_*.py` as its own process, and
prints `PASS` / `FAIL` / `SKIP` per file with the failing VERDICT block. Exit
code = number of failures.

Environment (all optional): `SEB_PORT` (8189), `SEB_INPUT_DIR` (the scratch
instance's `input/`, default derived from where this pack is installed),
`SEB_WORKFLOW_DIR` (`G:\AI\_Workflows\Utility`).

## What each test proves

| test | proves |
|---|---|
| `test_yaw_truth` | Python's yaw/pitch point where the panorama says: +90 is longitude +90, +pitch is up |
| `test_write_roundtrip` | Write 360 puts a view back exactly where Read 360 took it; the mirror longitude is untouched |
| `test_core_mask` | `core` mask keeps the margin as context; Write feathers the commit edge instead of stopping dead |
| `test_store_migration` | changing `canvas_width` resamples committed work instead of discarding it |
| `test_face_layout` | one preview on the node face, box follows the framing aspect, editor button visible, edits and editor sync both re-fit |
| `test_save_reframes` | editor Save re-frames the node preview, and onto the same marker Python extracts |
| `test_editor_fresh_graph` | the editor shows the panorama before any run, and follows an image swap |
| `test_camera_edit_persists` | a camera typed on the node survives the editor rewriting `state_json` |
| `test_editor_mask_path` | a mask painted in the editor reaches Python's MASK output (`editor` mode); `core` ignores it |
| `test_workflows_load` | every `seb_360_*.json` loads with no unknown seb node types; missing third-party packs are listed, not failed |
| `test_folder_loader` | Load Images From Folder (Seb). *one per run*: a single queued prompt processes the whole folder one image per run, sequentially, saving as it goes, stops after the last, and a failed run does not continue the chain; past-the-end is a clear error. *all in one run*: every image in one run, source names kept via Save Image (Seb), alpha → mask, non-images ignored, chunking, unchanged folder cached |
| `test_save_source_modes` | Save Image (Seb) `source_mode`: *same folder as source* lands next to the original, named after it + suffix, never over it; *replace source file* overwrites in place keeping the format (JPEG/PNG/WebP), atomically, no temp files left; *ignore source* unchanged |
| `test_pano_render` | (older) the editor paints the panorama after a run |
| `test_pano_roundtrip` | (older) editor camera -> node widgets, `view_height` follows the framed aspect |

Screenshots the tests take land next to them as `_*.png` and are ignored by git.

## Reading a failure

Each test prints one JSON object. `VERDICT` is the list of named checks; the
keys above it are the measurements those checks were made from, so a `false`
can be traced to a number without re-running.

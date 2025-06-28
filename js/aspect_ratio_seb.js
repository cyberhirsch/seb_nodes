// File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/js/aspect_ratio_seb.js
import { app } from "/scripts/app.js";

app.registerExtension({
	name: "Comfy.AspectRatioSeb.UI",
	async beforeRegisterNodeDef(nodeType, nodeData, app) {
		if (nodeData.name === "AspectRatioSeb") {
			const onNodeCreated = nodeType.prototype.onNodeCreated;
			nodeType.prototype.onNodeCreated = function () {
				onNodeCreated?.apply(this, arguments);

				// Get widget references
				const presetWidget = this.widgets.find((w) => w.name === "preset");
				const customWidthWidget = this.widgets.find((w) => w.name === "custom_aspect_width");
				const customHeightWidget = this.widgets.find((w) => w.name === "custom_aspect_height");
				const controlModeWidget = this.widgets.find((w) => w.name === "control_mode");
				const megapixelsWidget = this.widgets.find((w) => w.name === "target_megapixels");
				const fixedSideValueWidget = this.widgets.find((w) => w.name === "fixed_side_value");
				const fixedSideAxisWidget = this.widgets.find((w) => w.name === "fixed_side_axis");

				const toggleVisibility = () => {
					// Toggle custom aspect ratio fields
					const showCustom = presetWidget.value === "Custom";
					customWidthWidget.hidden = !showCustom;
					customHeightWidget.hidden = !showCustom;

					// Toggle control mode fields
					const showMegapixels = controlModeWidget.value === "Megapixels";
					megapixelsWidget.hidden = !showMegapixels;
					fixedSideValueWidget.hidden = showMegapixels;
					fixedSideAxisWidget.hidden = showMegapixels;

					// Request a redraw of the node
					this.setDirtyCanvas(true, true);
				};

				// Add callbacks to controlling widgets to run our function on change
				const originalPresetCallback = presetWidget.callback;
				presetWidget.callback = (value) => {
					originalPresetCallback?.(value);
					toggleVisibility();
				};

				const originalControlModeCallback = controlModeWidget.callback;
				controlModeWidget.callback = (value) => {
					originalControlModeCallback?.(value);
					toggleVisibility();
				};

				// Set initial visibility when the node is first created
				setTimeout(toggleVisibility, 0);
			};
		}
	},
});
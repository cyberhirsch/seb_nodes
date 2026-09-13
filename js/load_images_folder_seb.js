import { app } from "../../scripts/app.js";

// A progress line on the node face: "3 / 12  holiday 07" while a folder loop
// runs, "all 12 in this run" in list mode. Python sends it as ui.progress.
app.registerExtension({
    name: "Seb.LoadImagesFromFolder",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "LoadImagesFromFolderSeb") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            this.sebProgress = this.addWidget("text", "progress", "run to start", () => { },
                { serialize: false });
            return r;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const r = onExecuted ? onExecuted.apply(this, arguments) : undefined;
            if (message && message.progress && this.sebProgress) {
                this.sebProgress.value = String(message.progress[0]);
                this.setDirtyCanvas(true, true);
            }
            return r;
        };
    },
});

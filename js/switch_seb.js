import { app } from "../../../scripts/app.js";

// Define the mode constants for LiteGraph nodes for clarity and correctness
const NODE_MODE_NORMAL = 0; // The node is active and will be executed
const NODE_MODE_MUTED = 2;  // The node is muted and will be skipped

// This extension adds advanced UI features to the "Switch (Seb)" node.
app.registerExtension({
    name: "seb.SwitchSeb.Final",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        // Only apply these changes to our specific node
        if (nodeData.name === "Switch (Seb)") {

            // Get a reference to the original onNodeCreated function
            const onNodeCreated = nodeType.prototype.onNodeCreated;

            // Override the function that runs when a new node is created
            nodeType.prototype.onNodeCreated = function () {
                // Run the original function first to ensure the node is set up
                onNodeCreated?.apply(this, arguments);

                // ======================================================================
                // THIS IS THE MASTER FUNCTION THAT CONTAINS THE LOGIC YOU WERE MISSING
                // ======================================================================
                this.updateNodeState = () => {
                    const selectWidget = this.widgets.find((w) => w.name === "select");
                    const muteToggleWidget = this.widgets.find((w) => w.name === "Mute Inactive");

                    if (!selectWidget || !muteToggleWidget) return;

                    const selectedIndex = selectWidget.value;
                    const shouldMuteInactive = muteToggleWidget.value;

                    // Loop through all inputs to update muting state
                    for (let i = 0; i < this.inputs.length; i++) {
                        const input = this.inputs[i];
                        if (input.link) {
                            const linkInfo = app.graph.links[input.link];
                            const upstreamNode = app.graph.getNodeById(linkInfo.origin_id);

                            if (upstreamNode) {
                                const isSelectedInput = (i + 1) === selectedIndex;

                                if (isSelectedInput) {
                                    // THIS IS THE ACTIVE PATH: Ensure the node is ON
                                    upstreamNode.mode = NODE_MODE_NORMAL;
                                } else {
                                    // THIS IS AN INACTIVE PATH: Mute it if the toggle is on
                                    upstreamNode.mode = shouldMuteInactive ? NODE_MODE_MUTED : NODE_MODE_NORMAL;
                                }
                            }
                        }
                    }
                    // Force the UI to redraw to show the muted state
                    app.graph.setDirtyCanvas(true, true);
                };

                // --- Add Widgets and Triggers ---

                // 1. Add our custom "Mute Inactive" toggle widget
                this.addWidget("toggle", "Mute Inactive", false, () => this.updateNodeState(), { "on": "Yes", "off": "No" });

                // 2. Find the "select" widget from Python and modify its callback
                const selectWidget = this.widgets.find((w) => w.name === "select");
                if (selectWidget) {
                    const originalCallback = selectWidget.callback;
                    selectWidget.callback = (value) => {
                        originalCallback?.(value);
                        this.updateNodeState();
                    };
                }

                // Run the function once on creation to set the initial state
                setTimeout(() => this.updateNodeState(), 10);
            };

            // 3. Also update whenever connections are made or broken
            const onConnectionsChange = nodeType.prototype.onConnectionsChange;
            nodeType.prototype.onConnectionsChange = function () {
                onConnectionsChange?.apply(this, arguments);
                if (this.updateNodeState) {
                    setTimeout(() => this.updateNodeState(), 10);
                }
            };
        }
    },
});
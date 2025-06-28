// save_image_seb_ui.js
import { app } from "/scripts/app.js";

app.registerExtension({
    name: "Comfy.SaveImageSeb.UI", // <-- CHANGED for consistency
    async beforeRegisterNodeDef(nodeType, nodeData, appInstance) {
        // Check if this is our target node type
        if (nodeData.name === "SaveImageSeb") { // <-- CHANGED to match Python class name

            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;

            nodeType.prototype.onNodeCreated = function () {
                originalOnNodeCreated?.apply(this, arguments);

                const openFolderButton = this.addWidget(
                    "button",
                    "Open Last Output Folder",
                    null,
                    () => {
                        // <-- CHANGED to match Python API route
                        fetch("/comfy_save_seb/open_folder")
                            .then(response => {
                                if (!response.ok) {
                                    // Try to get error message from server if available
                                    return response.json().then(errData => {
                                        // Use a more specific error message if available from server
                                        throw new Error(errData.message || `Server error: ${response.status}`);
                                    }).catch(() => { // Fallback if error response isn't JSON
                                        throw new Error(`Server error: ${response.status}`);
                                    });
                                }
                                return response.json(); // Expecting JSON for successful responses
                            })
                            .then(data => {
                                if (data.status === "opened") {
                                    console.log("SaveImageSeb: Folder open command sent successfully for path -", data.path); // <-- CHANGED
                                } else if (data.message) {
                                    // If the server responded with ok status but indicated an issue in the JSON payload
                                    console.error("SaveImageSeb: Could not open folder -", data.message); // <-- CHANGED
                                } else {
                                    // Unexpected response structure
                                    console.error("SaveImageSeb: Unknown issue opening folder. Response data:", data); // <-- CHANGED
                                }
                            })
                            .catch(error => {
                                console.error("SaveImageSeb: Failed to call open folder API or API error -", error.message); // <-- CHANGED
                                // You might want to add an alert back here for user feedback on failure
                            });
                    },
                    {} // options (can be empty)
                );
                openFolderButton.serialize = false;
            };
        }
    },
});
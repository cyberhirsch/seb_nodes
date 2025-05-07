import { app } from "/scripts/app.js";

app.registerExtension({
    name: "Comfy.SaveImageAdvanced.UI", // Give it a unique name
    async beforeRegisterNodeDef(nodeType, nodeData, appInstance) {
        // Check if this is our target node type
        if (nodeData.name === "SaveImageAdvanced") { // This must match the Python class name
            
            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;

            nodeType.prototype.onNodeCreated = function () {
                originalOnNodeCreated?.apply(this, arguments);

                const openFolderButton = this.addWidget(
                    "button",
                    "Open Last Output Folder",
                    null,
                    () => {
                        fetch("/comfy_save_advanced/open_folder")
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
                                    console.log("SaveImageAdvanced: Folder open command sent successfully for path -", data.path);
                                } else if (data.message) {
                                    // If the server responded with ok status but indicated an issue in the JSON payload
                                    console.error("SaveImageAdvanced: Could not open folder -", data.message);
                                    // Decide if you want an alert for this specific case
                                    // alert("Could not open folder: " + data.message); 
                                } else {
                                    // Unexpected response structure
                                    console.error("SaveImageAdvanced: Unknown issue opening folder. Response data:", data);
                                }
                            })
                            .catch(error => {
                                console.error("SaveImageAdvanced: Failed to call open folder API or API error -", error.message);
                                // We removed the alert(error.message) here.
                                // If the folder opens, this console error is for debugging.
                                // If the folder *doesn't* open, this console error will be the primary indicator of a problem.
                            });
                    },
                    {} // options (can be empty)
                );
                openFolderButton.serialize = false; 
            };
        }
    },
});
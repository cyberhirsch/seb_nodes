import { app } from "../../scripts/app.js";
import { api } from "/scripts/api.js";

app.registerExtension({
    name: "Seb.360.Preview",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "Read360Seb") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                // The vendored Pano Editor (pano_editor.js) is bound to this node and
                // brings its own preview widgets. Ours is the framing preview; theirs
                // would stack on top of it, so they are stripped below.
                // ComfyUI core mounts a $$canvas-image-preview widget from node.imgs
                // whenever a node has an image-upload widget. On this node that draws
                // the whole source ERP a second time, under our framing preview, and
                // roughly doubles the node height. Our WebGL preview already shows the
                // framing, and the editor reads its panorama from the execution output
                // (pano_input_images), so nothing here wants node.imgs. Swallow it --
                // undefined is what a node without images has anyway.
                try {
                    Object.defineProperty(this, "imgs", {
                        configurable: true,
                        get() { return undefined; },
                        set() { /* ignored on purpose */ },
                    });
                } catch (e) {
                    console.warn("[Seb 360] could not suppress core image preview", e);
                }

                const panoEditor = (app.extensions || []).some(
                    e => /Seb\.PanoEditor\.Vendored/.test(String(e && e.name || "")));
                if (panoEditor) {
                    // Their editor is for assembly (stickers / paint / mask), opened on
                    // demand. The node face keeps OUR framing preview, which shows the
                    // actual extracted view at view_width:view_height. Their DOM preview
                    // shows the raw source image and collides with our canvas, so drop it.
                    // Their preview remounts itself, and under more than one name
                    // ($$comfy_animation_preview, then $$canvas-image-preview), so a
                    // one-shot filter does not hold. Strip it on every draw instead.
                    const stripTheirPreview = () => {
                        if (!this.widgets) return;
                        const keep = this.widgets.filter(
                            w => !(w && /^\$\$(canvas-image-preview|comfy_animation_preview)/
                                .test(String(w.name || ""))));
                        if (keep.length !== this.widgets.length) {
                            this.widgets = keep;
                            this.imgs = null;
                        }
                    };
                    this.__sebStripPanoPreview = stripTheirPreview;
                    stripTheirPreview();

                }

                // The editor writes its camera into state_json, but nothing pushes it
                // into the widgets -- so the node face (and our framing preview, which
                // reads the widgets) would show a different camera than Python extracts.
                // Mirror it back on every change.
                this.__sebSyncCam = () => {
                    const sw = (this.widgets || []).find(w => w.name === "state_json");
                    if (!sw || !sw.value || sw.value === this.__sebLastState) return;
                    // A node-side edit is still queued: it is newer than this state,
                    // so write it out rather than overwrite it.
                    if (this.__sebPushTimer) { pushCamToState(this); return; }
                    this.__sebLastState = sw.value;
                    let st;
                    try { st = JSON.parse(sw.value); } catch (e) { return; }
                    let pose = st && st.pose;
                    if (!pose) {
                        const shots = (st && st.shots) || [];
                        if (!shots.length) return;
                        const sel = st.active && st.active.selected_shot_id;
                        pose = shots.find(x => x && x.id === sel) || shots[0];
                    }
                    if (!pose) return;
                    const put = (name, val) => {
                        const w = (this.widgets || []).find(x => x.name === name);
                        if (w && typeof val === "number" && isFinite(val)) w.value = val;
                    };
                    let yaw = Number(pose.yaw_deg) || 0;
                    yaw = ((yaw + 180) % 360 + 360) % 360 - 180;
                    put("yaw", yaw);
                    put("pitch", Math.max(-90, Math.min(90, Number(pose.pitch_deg) || 0)));
                    put("fov", Number(pose.hFOV_deg) || 90);
                    // keep the framed aspect: vFOV = 2*atan(tan(hFOV/2)/aspect)
                    const h = Number(pose.hFOV_deg), v = Number(pose.vFOV_deg);
                    if (h > 0 && v > 0) {
                        const aspect = Math.tan(h * Math.PI / 360) / Math.tan(v * Math.PI / 360);
                        const wW = (this.widgets || []).find(x => x.name === "view_width");
                        if (wW && wW.value) {
                            put("view_height", Math.max(64, Math.round(wW.value / aspect / 8) * 8));
                        }
                    }
                    fitPreview(this);
                    this.setDirtyCanvas(true, true);
                    if (this.gl) requestAnimationFrame(() => drawScene(this));
                };
                // Their Hu() can re-assign the button's callback, so re-wrap if needed
                // rather than wrapping once and hoping it survives.
                this.__sebWrapEditorButton = () => {
                    const btn = (this.widgets || []).find(
                        w => /Open Pano Editor/.test(String(w.name || "")));
                    if (!btn || typeof btn.callback !== "function") return;
                    if (btn.callback.__sebPrimes) return;
                    const inner = btn.callback;
                    const wrapped = (...a) => {
                        primeEditorSource(this);
                        return inner.apply(this, a);
                    };
                    wrapped.__sebPrimes = true;
                    btn.callback = wrapped;
                };

                this.__sebTimer = setInterval(() => {
                    if (this.__sebSyncCam) this.__sebSyncCam();
                    if (this.__sebWrapEditorButton) this.__sebWrapEditorButton();
                }, 500);

                // Create Canvas for WebGL
                this.previewCanvas = document.createElement("canvas");
                this.previewCanvas.width = 512;
                this.previewCanvas.height = 512;
                this.previewCanvas.style.width = "100%";
                this.previewCanvas.style.objectFit = "contain";
                this.previewCanvas.style.backgroundColor = "black";

                this.previewWidget = this.addDOMWidget("360_preview", "canvas",
                    this.previewCanvas, { serialize: false, hideOnZoom: false });
                // The preview box itself takes the framing aspect, so the view fills
                // it edge to edge instead of sitting in black bars.
                fitPreview(this);

                this.densityWidget = this.addWidget("text", "density", "run to measure",
                    () => { }, { serialize: false });

                // Init WebGL 2
                this.gl = this.previewCanvas.getContext("webgl2");
                if (!this.gl) {
                    console.warn("[Seb 360] WebGL 2 not supported, falling back to WebGL 1");
                    this.gl = this.previewCanvas.getContext("webgl");
                }

                this.panoTexture = null;
                this.shaderProgram = null;

                if (this.gl) {
                    initWebGL(this);
                }

                // Event Listeners for Interaction
                let isDragging = false;
                let lastX = 0;
                let lastY = 0;

                this.previewCanvas.addEventListener("mousedown", (e) => {
                    isDragging = true;
                    lastX = e.clientX;
                    lastY = e.clientY;
                });

                this.__sebOnMouseUp = () => {
                    if (isDragging) schedulePush(this);
                    isDragging = false;
                };
                window.addEventListener("mouseup", this.__sebOnMouseUp);

                this.__sebOnMouseMove = (e) => {
                    if (!isDragging) return;

                    const dx = e.clientX - lastX;
                    const dy = e.clientY - lastY;
                    lastX = e.clientX;
                    lastY = e.clientY;

                    // Update Yaw/Pitch
                    // Sensitivity
                    const sensitivity = 0.5;

                    const yawWidget = this.widgets.find(w => w.name === "yaw");
                    const pitchWidget = this.widgets.find(w => w.name === "pitch");

                    if (yawWidget && pitchWidget) {
                        let newYaw = yawWidget.value - (dx * sensitivity);
                        let newPitch = pitchWidget.value + (dy * sensitivity);

                        // Clamp/Wrap
                        // Yaw: -180 to 180
                        if (newYaw > 180) newYaw -= 360;
                        if (newYaw < -180) newYaw += 360;

                        // Pitch: -90 to 90
                        newPitch = Math.max(-90, Math.min(90, newPitch));

                        yawWidget.value = newYaw;
                        pitchWidget.value = newPitch;

                        // Trigger redraw
                        this.setDirtyCanvas(true, true); // Redraw node
                        requestAnimationFrame(() => drawScene(this));
                    }
                };
                window.addEventListener("mousemove", this.__sebOnMouseMove);

                // Also listen to widget changes (if user types manually)
                setTimeout(() => {
                    const update = () => {
                        fitPreview(this);
                        schedulePush(this);
                        requestAnimationFrame(() => drawScene(this));
                    };
                    // view_width/view_height included: they set the preview's aspect,
                    // so the framing is wrong until it redraws.
                    for (const name of ["yaw", "pitch", "fov", "projection",
                                        "view_width", "view_height"]) {
                        const w = this.widgets.find(w => w.name === name);
                        if (!w) continue;
                        const cb = w.callback;
                        w.callback = (...args) => { update(); if (cb) cb(...args); };
                    }
                }, 100);

                // Listen to image upload
                setTimeout(() => {
                    const imageWidget = this.widgets.find(w => w.name === "image");
                    if (imageWidget) {
                        const cb = imageWidget.callback;
                        imageWidget.callback = (...args) => {
                            // Load image from ComfyUI View API
                            const filename = imageWidget.value;
                            if (filename) {
                                clearEditorSource(this);
                                loadPanoImage(this, null, filename);
                            }
                            if (cb) cb(...args);
                        };
                        // Initial load if value exists
                        if (imageWidget.value) {
                            loadPanoImage(this, null, imageWidget.value);
                        }
                    }
                }, 500);

                return r;
            };
            // Backstop for frontend versions that mount the preview widget without
            // going through node.imgs.
            const onDrawForeground = nodeType.prototype.onDrawForeground;
            nodeType.prototype.onDrawForeground = function () {
                if (this.__sebStripPanoPreview) this.__sebStripPanoPreview();
                return onDrawForeground ? onDrawForeground.apply(this, arguments) : undefined;
            };

            // Without this every deleted Read node keeps its 500ms poll and its
            // window listeners alive for the life of the tab.
            const onRemoved = nodeType.prototype.onRemoved;
            nodeType.prototype.onRemoved = function () {
                if (this.__sebTimer) { clearInterval(this.__sebTimer); this.__sebTimer = null; }
                if (this.__sebPushTimer) { clearTimeout(this.__sebPushTimer); this.__sebPushTimer = null; }
                if (this.__sebOnMouseUp) window.removeEventListener("mouseup", this.__sebOnMouseUp);
                if (this.__sebOnMouseMove) window.removeEventListener("mousemove", this.__sebOnMouseMove);
                return onRemoved ? onRemoved.apply(this, arguments) : undefined;
            };

            const onResize = nodeType.prototype.onResize;
            nodeType.prototype.onResize = function () {
                const r = onResize ? onResize.apply(this, arguments) : undefined;
                fitPreview(this);
                return r;
            };

            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                const r = onConfigure ? onConfigure.apply(this, arguments) : undefined;
                setTimeout(() => fitPreview(this), 50);
                return r;
            };

            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                const r = onExecuted ? onExecuted.apply(this, arguments) : undefined;

                if (message && message.pano_id && message.pano_id[0]) {
                    const panoId = message.pano_id[0];
                    loadPanoImage(this, panoId);
                }

                if (message && message.density && this.densityWidget) {
                    this.densityWidget.value = message.density[0];
                    this.setDirtyCanvas(true, true);
                }

                return r;
            };
        }

        if (nodeData.name === "Write360Seb") {
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                const r = onExecuted ? onExecuted.apply(this, arguments) : undefined;
                if (message && message.pano_id && message.pano_id[0]) {
                    this.panoId = message.pano_id[0];
                }
                if (message && message.pending) {
                    this.pendingCount = message.pending[0] | 0;
                    const cw = this.widgets.find(w => w.name === "candidate");
                    if (cw) cw.value = 0;
                    showCandidate(this, 0);

                    if (this.pendingCount && wantsFollow(this)) {
                        refreshReaders(this.panoId, 0);
                    }
                }
                return r;
            };

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                this.pendingCount = 0;

                this.candidateImg = document.createElement("img");
                this.candidateImg.style.width = "100%";
                this.candidateImg.style.height = "160px";
                this.candidateImg.style.objectFit = "contain";
                this.candidateImg.style.backgroundColor = "black";
                this.addDOMWidget("candidate_preview", "img", this.candidateImg, {
                    serialize: false,
                    hideOnZoom: false
                });

                this.statusWidget = this.addWidget("text", "staged", "none", () => { }, {
                    serialize: false
                });

                this.addWidget("toggle", "follow_candidate", true, () => { }, {
                    serialize: false
                });

                this.addWidget("number", "candidate", 0, (v) => {
                    const i = Math.round(v);
                    showCandidate(this, i);
                    if (this.pendingCount && wantsFollow(this)) {
                        refreshReaders(this.panoId, i);
                    }
                }, { min: 0, max: 7, step: 10, precision: 0, serialize: false });

                this.addWidget("button", "Commit Candidate", null, () => {
                    if (!this.panoId) { alert("Run the node first."); return; }
                    if (!this.pendingCount) { alert("Nothing staged to commit."); return; }
                    const idx = Math.round(this.widgets.find(w => w.name === "candidate")?.value || 0);
                    api.fetchApi("/seb/360/commit", {
                        method: "POST",
                        body: JSON.stringify({ id: this.panoId, index: idx }),
                    }).then(async (res) => {
                        if (res.ok) {
                            this.pendingCount = 0;
                            if (this.statusWidget) this.statusWidget.value = "committed";
                            showCandidate(this, -1);
                            refreshReaders(this.panoId);
                        } else {
                            const e = await res.json().catch(() => ({}));
                            alert("Commit failed: " + (e.error || res.status));
                        }
                    }).catch(err => alert("Error: " + err));
                });

                this.addWidget("button", "Discard Staged", null, () => {
                    if (!this.panoId) return;
                    api.fetchApi("/seb/360/discard", {
                        method: "POST",
                        body: JSON.stringify({ id: this.panoId }),
                    }).then(() => {
                        this.pendingCount = 0;
                        if (this.statusWidget) this.statusWidget.value = "discarded";
                        showCandidate(this, -1);
                        refreshReaders(this.panoId);
                    }).catch(err => alert("Error: " + err));
                });

                this.addWidget("button", "Export to Disk", null, () => {
                    if (!this.panoId) {
                        alert("Please run the node first to generate the panorama.");
                        return;
                    }

                    api.fetchApi("/seb/360/save", {
                        method: "POST",
                        body: JSON.stringify({ id: this.panoId }),
                    }).then(async (response) => {
                        if (response.ok) {
                            const data = await response.json();
                            alert("Saved to: " + data.filename);
                        } else {
                            alert("Error saving panorama.");
                        }
                    }).catch((err) => {
                        alert("Error: " + err);
                    });
                });

                return r;
            }
        }
    },
});

function initWebGL(node) {
    const gl = node.gl;

    // Shaders
    const vsSource = `
        attribute vec4 aVertexPosition;
        attribute vec2 aTextureCoord;
        varying highp vec2 vTextureCoord;
        void main(void) {
            gl_Position = aVertexPosition;
            vTextureCoord = aTextureCoord;
        }
    `;

    const fsSource = `
        precision mediump float;
        varying highp vec2 vTextureCoord;
        uniform sampler2D uSampler;
        uniform float uYaw;
        uniform float uPitch;
        uniform float uFov;
        uniform float uAspect;
        uniform int uProjection; // 0 = Perspective, 1 = Equirectangular
        
        #define PI 3.14159265359
        
        void main(void) {
            vec2 uv = vTextureCoord * 2.0 - 1.0;
            
            vec3 dir;
            
            if (uProjection == 1) {
                // Equirectangular (Rotated)
                // UV is just lat/lon directly
                // We want to map UV (-1..1) to Lat/Lon
                // But we want to apply rotation.
                // So we convert UV -> Spherical -> Cartesian -> Rotate -> Spherical -> UV
                
                float lon = uv.x * PI;
                float lat = uv.y * (PI * 0.5);
                
                float x = cos(lat) * sin(lon);
                float y = sin(lat);
                float z = cos(lat) * cos(lon);
                
                dir = vec3(x, y, z);
                
            } else {
                // Perspective. fov is HORIZONTAL, matching equirect_to_perspective
                // in the Python: uv.x hits +-1 at the horizontal edge, so dividing
                // y by the aspect yields vertical fov = 2*atan(tan(fov/2)/aspect).
                float f = 1.0 / tan(radians(uFov) * 0.5);
                dir = normalize(vec3(uv.x, uv.y / uAspect, f));
            }
            
            // Rotate (Yaw/Pitch)
            float yaw = radians(uYaw);   // sign matches get_rotation_matrix()
            float pitch = radians(uPitch);
            
            // Pitch
            float y = dir.y * cos(pitch) - dir.z * sin(pitch);
            float z = dir.y * sin(pitch) + dir.z * cos(pitch);
            dir.y = y;
            dir.z = z;
            
            // Yaw
            float x = dir.x * cos(yaw) + dir.z * sin(yaw);
            z = -dir.x * sin(yaw) + dir.z * cos(yaw);
            dir.x = x;
            dir.z = z;
            
            float lon = atan(dir.x, dir.z);
            float lat = asin(dir.y);
            
            vec2 sphereUV = vec2(
                lon / (2.0 * PI) + 0.5,
                lat / PI + 0.5
            );
            
            gl_FragColor = texture2D(uSampler, sphereUV);
        }
    `;

    const shaderProgram = initShaderProgram(gl, vsSource, fsSource);
    node.shaderProgram = shaderProgram;

    node.programInfo = {
        program: shaderProgram,
        attribLocations: {
            vertexPosition: gl.getAttribLocation(shaderProgram, 'aVertexPosition'),
            textureCoord: gl.getAttribLocation(shaderProgram, 'aTextureCoord'),
        },
        uniformLocations: {
            uSampler: gl.getUniformLocation(shaderProgram, 'uSampler'),
            uYaw: gl.getUniformLocation(shaderProgram, 'uYaw'),
            uPitch: gl.getUniformLocation(shaderProgram, 'uPitch'),
            uFov: gl.getUniformLocation(shaderProgram, 'uFov'),
            uAspect: gl.getUniformLocation(shaderProgram, 'uAspect'),
            uProjection: gl.getUniformLocation(shaderProgram, 'uProjection'),
        },
    };

    // Buffers
    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    const positions = [
        -1.0, 1.0,
        1.0, 1.0,
        -1.0, -1.0,
        1.0, -1.0,
    ];
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(positions), gl.STATIC_DRAW);
    node.positionBuffer = positionBuffer;

    const textureCoordBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, textureCoordBuffer);
    const textureCoordinates = [
        0.0, 0.0,
        1.0, 0.0,
        0.0, 1.0,
        1.0, 1.0,
    ];
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(textureCoordinates), gl.STATIC_DRAW);
    node.textureCoordBuffer = textureCoordBuffer;
}

function initShaderProgram(gl, vsSource, fsSource) {
    const vertexShader = loadShader(gl, gl.VERTEX_SHADER, vsSource);
    const fragmentShader = loadShader(gl, gl.FRAGMENT_SHADER, fsSource);
    const shaderProgram = gl.createProgram();
    gl.attachShader(shaderProgram, vertexShader);
    gl.attachShader(shaderProgram, fragmentShader);
    gl.linkProgram(shaderProgram);
    return shaderProgram;
}

function loadShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('An error occurred compiling the shaders: ' + gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        return null;
    }
    return shader;
}

function loadPanoImage(node, id, filename, candidate) {
    const img = new Image();
    img.onload = function () {
        const gl = node.gl;
        const texture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);

        // Wrapping and Filtering
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT); // Important for 360
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

        node.panoTexture = texture;
        console.log("[Seb 360] Texture loaded successfully");
        drawScene(node);
    };

    img.onerror = function (e) {
        console.error("[Seb 360] Failed to load image:", e);
    };

    let src = "";
    if (filename) {
        // Standard ComfyUI View URL for Input folder
        src = api.apiURL(`/view?filename=${encodeURIComponent(filename)}&type=input`);
    } else if (id) {
        // Our Custom API. A candidate index renders the staged result on top of
        // the committed layer, so the 3D viewer shows what commit would produce.
        const c = (candidate !== undefined && candidate !== null && candidate >= 0)
            ? `&candidate=${candidate}` : "";
        src = `/seb/360/view?id=${encodeURIComponent(id)}${c}&t=${Date.now()}`;
    }
    console.log("[Seb 360] Loading image from:", src);
    img.src = src;
}

function showCandidate(node, index) {
    if (!node.candidateImg) return;

    if (!node.panoId || index < 0 || !node.pendingCount) {
        node.candidateImg.removeAttribute("src");
        if (node.statusWidget && !node.pendingCount) {
            node.statusWidget.value = "none";
        }
        node.setDirtyCanvas(true, true);
        return;
    }

    const i = Math.max(0, Math.min(index, node.pendingCount - 1));
    if (node.statusWidget) {
        node.statusWidget.value = `${i + 1} of ${node.pendingCount}`;
    }
    node.candidateImg.src =
        `/seb/360/view?id=${encodeURIComponent(node.panoId)}&candidate=${i}&t=${Date.now()}`;
    node.setDirtyCanvas(true, true);
}

// After a commit the layer changed, so any Read 360 viewing the same panorama
// is showing stale pixels until its texture is reloaded. Passing a candidate
// index instead previews the staged result in the same 3D viewer.
function refreshReaders(panoId, candidate) {
    if (!app.graph || !panoId) return;
    for (const n of app.graph._nodes || []) {
        if (n.type === "Read360Seb" && n.gl) {
            loadPanoImage(n, panoId, null, candidate);
        }
    }
}

// Whether the 3D viewer should jump to the selected candidate. Purely a viewing
// preference -- unrelated to update_reference, which folds a commit into the base.
function wantsFollow(node) {
    const w = node.widgets?.find(w => w.name === "follow_candidate");
    return w ? !!w.value : true;
}

// Their editor binds its panorama from this node's execution output, under the
// key pano_input_images. On a graph that has not been run yet that key does not
// exist, so the editor used to open with an empty Panorama layer. Point it at the
// source image instead; the next run replaces this with the real base+layer
// composite, which is what we actually want it to edit against.
function primeEditorSource(node) {
    if (!node) return;
    const outs = app.nodeOutputs || (app.nodeOutputs = {});
    const cur = outs[node.id] || outs[String(node.id)] || null;
    if (cur && Array.isArray(cur.pano_input_images) && cur.pano_input_images.length) return;
    const w = (node.widgets || []).find(x => x.name === "image");
    const file = w && String(w.value || "");
    if (!file || file.includes("/")) return;
    outs[node.id] = Object.assign({}, cur, {
        pano_input_images: [{ filename: file, subfolder: "", type: "input" }],
    });
}

// Picking a different panorama invalidates whatever the editor was bound to.
function clearEditorSource(node) {
    if (!node) return;
    const outs = app.nodeOutputs || {};
    const cur = outs[node.id] || outs[String(node.id)];
    if (cur) delete cur.pano_input_images;
}

// Widgets -> state_json. The pull direction alone is not enough: the editor seeds
// state_json with a default frame, and every later write to it (even an unrelated
// setting) re-stamped that frame over whatever was typed on the node or set by
// drag-to-look. Pushing back keeps one camera, wherever it was set.
function reduceRatio(w, h) {
    const gcd = (a, b) => b ? gcd(b, a % b) : a;
    const a = Math.max(1, Math.round(w)), b = Math.max(1, Math.round(h));
    const d = gcd(a, b) || 1;
    return `${Math.round(a / d)}:${Math.round(b / d)}`;
}

function pushCamToState(node) {
    if (!node) return;
    if (node.__sebPushTimer) { clearTimeout(node.__sebPushTimer); node.__sebPushTimer = null; }
    const sw = (node.widgets || []).find(w => w.name === "state_json");
    if (!sw || !sw.value) return;
    let st;
    try { st = JSON.parse(sw.value); } catch (e) { return; }
    const shots = (st && st.shots) || [];
    if (!shots.length) return;
    const sel = st.active && st.active.selected_shot_id;
    const shot = shots.find(x => x && x.id === sel) || shots[0];
    if (!shot || shot.locked === true) return;

    const g = n => (node.widgets || []).find(w => w.name === n);
    const num = (n, d) => {
        const w = g(n);
        const v = w ? Number(w.value) : NaN;
        return isFinite(v) ? v : d;
    };
    const yaw = num("yaw", 0);
    const pitch = Math.max(-89.9, Math.min(89.9, num("pitch", 0)));
    const hfov = Math.max(1, Math.min(179, num("fov", 90)));
    const vw = num("view_width", 0), vh = num("view_height", 0);
    const aspect = (vw > 0 && vh > 0) ? (vw / vh) : 1;
    const vfov = Math.max(1, Math.min(179,
        2 * Math.atan(Math.tan(hfov * Math.PI / 360) / aspect) * 180 / Math.PI));

    const near = (a, b, eps) => Math.abs((Number(a) || 0) - b) < eps;
    if (near(shot.yaw_deg, yaw, 1e-6) && near(shot.pitch_deg, pitch, 1e-6)
        && near(shot.hFOV_deg, hfov, 1e-6) && near(shot.vFOV_deg, vfov, 1e-3)) return;

    shot.yaw_deg = yaw;
    shot.pitch_deg = pitch;
    shot.hFOV_deg = hfov;
    shot.vFOV_deg = vfov;
    // The editor re-derives vFOV from aspect_id, so keep it consistent.
    if (vw > 0 && vh > 0) shot.aspect_id = reduceRatio(vw, vh);

    const next = JSON.stringify(st);
    sw.value = next;
    node.__sebLastState = next;   // ours -- do not pull it straight back
}

function schedulePush(node) {
    if (!node) return;
    if (node.__sebPushTimer) clearTimeout(node.__sebPushTimer);
    node.__sebPushTimer = setTimeout(() => {
        node.__sebPushTimer = null;
        pushCamToState(node);
    }, 200);
}

// Size the preview box to view_width:view_height so the framing fills it. Without
// this the box is a fixed 256px and anything but that aspect renders inside black
// bars, which wastes most of the node face and reads as a bug.
const PREVIEW_MIN_H = 96;
const PREVIEW_MAX_H = 480;

function previewAspect(node) {
    const get = n => (node.widgets || []).find(w => w.name === n);
    const vw = Number(get("view_width")?.value) || 0;
    const vh = Number(get("view_height")?.value) || 0;
    return (vw > 0 && vh > 0) ? (vw / vh) : 1.0;
}

function fitPreview(node) {
    if (!node || !node.previewCanvas) return;
    const aspect = previewAspect(node);
    const boxW = node.previewCanvas.clientWidth
        || Math.max(64, (node.size && node.size[0] ? node.size[0] : 320) - 20);
    const h = Math.max(PREVIEW_MIN_H,
        Math.min(PREVIEW_MAX_H, Math.round(boxW / aspect)));

    if (node.previewWidget) {
        node.previewWidget.computeSize = (width) => {
            const w = width || boxW;
            return [w, Math.max(PREVIEW_MIN_H,
                Math.min(PREVIEW_MAX_H, Math.round(w / previewAspect(node))))];
        };
    }
    if (node.__sebPreviewH === h) return;
    node.__sebPreviewH = h;
    node.previewCanvas.style.height = h + "px";

    // Height is fully determined by the widgets plus this box, so fit the node to
    // its content instead of leaving dead space where the removed preview used to
    // sit. Width stays the user's -- dragging it wider grows the preview with it.
    if (!node.__sebFitting && typeof node.computeSize === "function") {
        node.__sebFitting = true;
        try {
            const want = node.computeSize();
            if (want && want[1] && Math.abs(node.size[1] - want[1]) > 2) {
                node.setSize([node.size[0], want[1]]);
            }
        } finally {
            node.__sebFitting = false;
        }
    }

    node.setDirtyCanvas(true, true);
    if (node.gl) requestAnimationFrame(() => drawScene(node));
}

function drawScene(node) {
    if (!node.gl || !node.panoTexture) return;

    const gl = node.gl;
    const programInfo = node.programInfo;

    // Resize canvas to match display size
    const canvas = gl.canvas;
    const displayWidth = canvas.clientWidth;
    const displayHeight = canvas.clientHeight;

    if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
        canvas.width = displayWidth;
        canvas.height = displayHeight;
    }

    // Render into a letterboxed rect matching view_width/view_height, so the
    // preview frames exactly what the node will extract instead of being
    // stretched to whatever shape the node box happens to be.
    const vw = node.widgets.find(w => w.name === "view_width")?.value || 1024;
    const vh = node.widgets.find(w => w.name === "view_height")?.value || 1024;
    const viewAspect = (vw > 0 && vh > 0) ? (vw / vh) : 1.0;

    let vpW = canvas.width;
    let vpH = Math.round(vpW / viewAspect);
    if (vpH > canvas.height) {
        vpH = canvas.height;
        vpW = Math.round(vpH * viewAspect);
    }
    const vpX = Math.round((canvas.width - vpW) / 2);
    const vpY = Math.round((canvas.height - vpH) / 2);

    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.0, 0.0, 0.0, 1.0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.viewport(vpX, vpY, vpW, vpH);

    gl.useProgram(programInfo.program);

    // Attributes
    {
        const numComponents = 2;
        const type = gl.FLOAT;
        const normalize = false;
        const stride = 0;
        const offset = 0;
        gl.bindBuffer(gl.ARRAY_BUFFER, node.positionBuffer);
        gl.vertexAttribPointer(
            programInfo.attribLocations.vertexPosition,
            numComponents,
            type,
            normalize,
            stride,
            offset);
        gl.enableVertexAttribArray(programInfo.attribLocations.vertexPosition);
    }
    {
        const numComponents = 2;
        const type = gl.FLOAT;
        const normalize = false;
        const stride = 0;
        const offset = 0;
        gl.bindBuffer(gl.ARRAY_BUFFER, node.textureCoordBuffer);
        gl.vertexAttribPointer(
            programInfo.attribLocations.textureCoord,
            numComponents,
            type,
            normalize,
            stride,
            offset);
        gl.enableVertexAttribArray(programInfo.attribLocations.textureCoord);
    }

    // Uniforms
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, node.panoTexture);
    gl.uniform1i(programInfo.uniformLocations.uSampler, 0);

    const yaw = node.widgets.find(w => w.name === "yaw")?.value || 0;
    const pitch = node.widgets.find(w => w.name === "pitch")?.value || 0;
    const fov = node.widgets.find(w => w.name === "fov")?.value || 90;
    const projection = node.widgets.find(w => w.name === "projection")?.value;
    const aspect = viewAspect;

    const projMode = (projection === "equirectangular") ? 1 : 0;

    gl.uniform1f(programInfo.uniformLocations.uYaw, yaw);
    gl.uniform1f(programInfo.uniformLocations.uPitch, pitch);
    gl.uniform1f(programInfo.uniformLocations.uFov, fov);
    gl.uniform1f(programInfo.uniformLocations.uAspect, aspect);
    gl.uniform1i(programInfo.uniformLocations.uProjection, projMode);

    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
}

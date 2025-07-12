# File: G:/AI/ComfyUI_windows_portable/ComfyUI/custom_nodes/seb_nodes/depth_inpaint_seb.py

import torch
import numpy as np
from collections import namedtuple
import os
import cv2

# --- Custom Output Type ---
Mesh = namedtuple("Mesh", ["vertices", "colors", "faces"])

# --- Dependency Imports ---
# This correctly imports from the 'depth_inpaint_seb' sub-folder
from .depth_inpaint_seb.networks import Inpaint_Color_Net, Inpaint_Depth_Net, Inpaint_Edge_Net
from .depth_inpaint_seb.mesh import create_mesh, tear_edges, generate_init_node, group_edges, reassign_floating_island, update_status, remove_dangling, fill_missing_node, enlarge_border, fill_dummy_bord, context_and_holes, DL_inpaint_edge, generate_face, reproject_3d_int_detail
from .depth_inpaint_seb.bilateral_filtering import sparse_bilateral_filtering

# --- Helper Functions ---
def tensor_to_np(tensor):
    """Converts a ComfyUI tensor to a NumPy array (H, W, C) in BGR format."""
    img_np = tensor.cpu().numpy().squeeze()
    img_np = (img_np * 255).astype(np.uint8)
    return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR) if img_np.ndim == 3 else img_np

# --- Core Logic ---
def generate_mesh_data_seb(image_bgr, depth, int_mtx, config, rgb_model, depth_edge_model, depth_feat_model):
    """
    Performs the 3D photo generation pipeline and returns mesh data.
    """
    depth = depth.astype(np.float64)
    
    input_mesh, _, image_bgr, depth = create_mesh(depth, image_bgr, int_mtx, config)
    input_mesh = tear_edges(input_mesh, config['depth_threshold'], None)
    input_mesh, info_on_pix = generate_init_node(input_mesh, config, min_node_in_cc=200)

    edge_ccs, input_mesh, edge_mesh = group_edges(input_mesh, config, image_bgr, remove_conflict_ordinal=False)
    input_mesh, info_on_pix, depth = reassign_floating_island(input_mesh, info_on_pix, image_bgr, depth)
    input_mesh = update_status(input_mesh, info_on_pix)
    edge_ccs, input_mesh, edge_mesh = group_edges(input_mesh, config, image_bgr, remove_conflict_ordinal=True)
    input_mesh, info_on_pix, edge_mesh, depth, _ = remove_dangling(input_mesh, edge_ccs, edge_mesh, info_on_pix, image_bgr, depth, config)
    input_mesh, depth, info_on_pix = update_status(input_mesh, info_on_pix, depth)
    edge_ccs, input_mesh, edge_mesh = group_edges(input_mesh, config, image_bgr, remove_conflict_ordinal=True)
    
    mesh, info_on_pix, depth = fill_missing_node(input_mesh, info_on_pix, image_bgr, depth)
    if config['extrapolate_border']:
        input_mesh, info_on_pix, depth, image_bgr = enlarge_border(input_mesh, info_on_pix, depth, image_bgr, config)
        input_mesh, info_on_pix = fill_dummy_bord(input_mesh, info_on_pix, image_bgr, depth, config)
        edge_ccs, input_mesh, edge_mesh = group_edges(input_mesh, config, image_bgr, remove_conflict_ordinal=True)

    context_ccs, mask_ccs, _, edge_ccs, erode_context_ccs, _, edge_maps, extend_context_ccs, extend_edge_ccs, extend_erode_context_ccs = \
        context_and_holes(input_mesh, edge_ccs, config, [], None, depth_feat_model, inpaint_iter=0)

    input_mesh, info_on_pix, _, _, _, image_bgr = DL_inpaint_edge(input_mesh, info_on_pix, config, image_bgr, depth,
                                                                 context_ccs, erode_context_ccs, extend_context_ccs,
                                                                 extend_erode_context_ccs, mask_ccs, [],
                                                                 edge_ccs, extend_edge_ccs, None, edge_maps,
                                                                 rgb_model, depth_edge_model, None,
                                                                 depth_feat_model, inpaint_iter=0)
    
    vertex_id, verts_list, colors_list = 0, [], []
    k_00, k_02, k_11, k_12 = input_mesh.graph['cam_param_pix_inv'][0, 0], input_mesh.graph['cam_param_pix_inv'][0, 2], input_mesh.graph['cam_param_pix_inv'][1, 1], input_mesh.graph['cam_param_pix_inv'][1, 2]
    w_offset, h_offset = input_mesh.graph['woffset'], input_mesh.graph['hoffset']

    for pix_xy, pix_list in info_on_pix.items():
        for pix_info in pix_list:
            if not input_mesh.has_node((pix_xy[0], pix_xy[1], pix_info['depth'])): continue
            
            pix_depth = pix_info.get('real_depth', pix_info['depth'])
            pt_3d = reproject_3d_int_detail(pix_xy[0], pix_xy[1], pix_depth, k_00, k_02, k_11, k_12, w_offset, h_offset)
            color_val = (pix_info['color'] / pix_info.get('overlap_number', 1.0)).astype(np.uint8)
            
            verts_list.append(pt_3d)
            colors_list.append(cv2.cvtColor(color_val, cv2.COLOR_BGR2RGB))
            
            input_mesh.nodes[(pix_xy[0], pix_xy[1], pix_info['depth'])]['cur_id'] = vertex_id
            vertex_id += 1
            
    config['save_ply'] = False
    faces_list = generate_face(input_mesh, info_on_pix, config)
    
    return Mesh(vertices=np.array(verts_list, dtype=np.float32), 
                colors=np.array(colors_list, dtype=np.uint8), 
                faces=np.array(faces_list, dtype=np.int32))

# --- ComfyUI Node Class ---
class DepthInpaintSeb:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
                "image": ("IMAGE",), "depth_image": ("IMAGE",),
                "depth_threshold": ("FLOAT", {"default": 0.04, "min": 0.0, "max": 0.2, "step": 0.001}),
                "extrapolate_border": ("BOOLEAN", {"default": True}),
                "extrapolation_thickness": ("INT", {"default": 60, "min": 0, "max": 200, "step": 1}),
                "background_thickness": ("INT", {"default": 70, "min": 10, "max": 200, "step": 1}),
                "redundant_number": ("INT", {"default": 12, "min": 0, "max": 100, "step": 1}),
            }}

    RETURN_TYPES = ("MESH",)
    FUNCTION = "generate"
    CATEGORY = "Seb/3D"

    def generate(self, image, depth_image, depth_threshold, extrapolate_border, extrapolation_thickness, background_thickness, redundant_number):
        image_np_bgr = tensor_to_np(image)
        depth_np_gray = tensor_to_np(depth_image)
        
        depth_np = 1.0 / (depth_np_gray / 255.0 * 10.0 + 0.05)
        depth_np = cv2.resize(depth_np, (image_np_bgr.shape[1], image_np_bgr.shape[0]), interpolation=cv2.INTER_AREA)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        config = {
            'depth_threshold': depth_threshold, 'extrapolate_border': extrapolate_border, 'extrapolation_thickness': extrapolation_thickness, 
            'background_thickness': background_thickness, 'redundant_number': redundant_number, 'context_thickness': 140, 
            'sparse_iter': 5, 'filter_size': [7, 7, 5, 5, 5], 'sigma_s': 4.0, 'sigma_r': 0.5, 'log_depth': True,
            'depth_edge_dilate': 10, 'repeat_inpaint_edge': True, 'background_thickness_2': 70, 'context_thickness_2': 70, 
            'depth_edge_dilate_2': 5, 'ext_edge_threshold': 0.002, 'largest_size': 512, 'crop_border': [0.0, 0.0, 0.0, 0.0], 
            'save_ply': False, 'gpu_ids': 0 if device == 'cuda' else -1, 'gray_image': False
        }
        
        node_dir = os.path.dirname(os.path.abspath(__file__))
        ckpt_dir = os.path.join(node_dir, 'checkpoints')
        
        depth_edge_model = Inpaint_Edge_Net(init_weights=True).to(device)
        depth_edge_model.load_state_dict(torch.load(os.path.join(ckpt_dir, 'edge-model.pth'), map_location=device))
        depth_edge_model.eval()

        depth_feat_model = Inpaint_Depth_Net().to(device)
        depth_feat_model.load_state_dict(torch.load(os.path.join(ckpt_dir, 'depth-model.pth'), map_location=device), strict=True)
        depth_feat_model.eval()

        rgb_model = Inpaint_Color_Net().to(device)
        rgb_model.load_state_dict(torch.load(os.path.join(ckpt_dir, 'color-model.pth'), map_location=device))
        rgb_model.eval()

        _, vis_depths = sparse_bilateral_filtering(depth_np.copy(), image_np_bgr.copy(), config, num_iter=config['sparse_iter'])
        filtered_depth = vis_depths[-1]

        H, W, _ = image_np_bgr.shape
        int_mtx = np.array([[max(H, W), 0, W//2], [0, max(H, W), H//2], [0, 0, 1]]).astype(np.float32)

        mesh_data = generate_mesh_data_seb(image_np_bgr, filtered_depth, int_mtx, config, rgb_model, depth_edge_model, depth_feat_model)
        
        return (mesh_data,)
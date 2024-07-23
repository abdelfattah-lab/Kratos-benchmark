"""
Requirements that are shared across multiple implementations.
"""

# --- Start: Experiment

# General
REQUIRED_KEYS_EXP = ['root_dir', 'verilog_search_dir']

# --- End: Experiment

# --- Start: Design

# General
REQUIRED_KEYS_DESIGN = ['module_dir', 'wrapper_module_name', 'impl', 'sparsity', 'data_width']

# Convolution
REQUIRED_KEYS_CONV1D = [*REQUIRED_KEYS_DESIGN, 'img_w', 'img_d', 'fil_w', 'res_d']
REQUIRED_KEYS_CONV2D = [*REQUIRED_KEYS_CONV1D, 'img_h', 'fil_h']
REQUIRED_KEYS_CONV1D_STRIDE = [*REQUIRED_KEYS_CONV2D, 'stride_w']
REQUIRED_KEYS_CONV2D_STRIDE = [*REQUIRED_KEYS_CONV2D, 'stride_w', 'stride_h']

# GEMM
REQUIRED_KEYS_GEMM = [*REQUIRED_KEYS_DESIGN, 'row_num', 'col_num', 'length']

# --- End: Design
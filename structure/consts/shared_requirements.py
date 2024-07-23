"""
Requirements that are shared across multiple implementations.
"""

# --- Start: Experiment

# General
REQUIRED_KEYS_EXP = ['root_dir', 'verilog_search_dir']

# --- End: Experiment

# --- Start: Design

# General
REQUIRED_KEYS_DESIGN = ['module_dir', 'wrapper_module_name', 'impl', 'sparsity']

# Convolution
REQUIRED_KEYS_CONV2D = [*REQUIRED_KEYS_DESIGN, 'data_width', 'img_w', 'img_h', 'img_d', 'fil_w', 'fil_h', 'res_d']
REQUIRED_KEYS_CONV2D_STRIDE = [*REQUIRED_KEYS_CONV2D, 'stride_w', 'stride_h']

# --- End: Design
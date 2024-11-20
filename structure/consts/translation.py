"""
Provides key translations, i.e., parameter names to human-readable labels.
"""

TRANSLATIONS_EXP = {
    'root_dir': 'Experiment root directory',
    'verilog_search_dir': 'SystemVerilog search directory',
    'stdout_file': 'stdout file',
    'stderr_file': 'stderr file'
}

TRANSLATIONS_ARCH = {
    'ble_count': 'BLE count',
    'CLB_pins_per_group': 'No. of CLB pins per group',
    'num_feedback_ble': 'No. of feedback BLEs per CLB',
    'frac_feedback_ble': 'Fraction of feedback BLEs per CLB',
    'lut_size': 'LUT size'
}

TRANSLATIONS_DESIGN = {
    # General
    'data_width': 'Data width',
    'sparsity': 'Sparsity',
    'clock': 'Clock',
    'constant_weight': 'Constant input',

    # Convolution
    'img_w': 'Image width',
    'img_h': 'Image height',
    'img_d': 'Image depth',
    'fil_w': 'Filter width',
    'fil_h': 'Filter height',
    'res_d': 'Result depth',
    'stride_w': 'Stride width',
    'stride_h': 'Stride height',
    'separate_filters': 'Separate filters',
    'buffer_stages': 'Buffer stages',
    
    #GEMM
    'row_num': 'No. of result rows',
    'col_num': 'No. of result columns',
    'length': 'Length of input matrix',
}

# Common graph headers.
TRANSLATIONS_GRAPH = {
    'fmax': 'Maximum Frequency',
    'cpd': 'Critical Path Delay',
    'twl': 'Total Wire Length',
    'area_total_used': 'Total Area Used',
    'area_fle': 'Total ALM Area Used',
    'adp_used': 'Area-Delay Product',
    'adp_fle': 'Area-Delay Product',
    'clb': 'LAB Count',
    'fle': 'ALM Count',
    'lut': 'LUTs Used',
    'adder': 'Adders',
    'adder_avg_util': 'Average Adder Utilisation',
    'lut5/adder': '5-LUT to Adder Ratio',
    'lut5_concurrency': '5-LUT Concurrency Percentage',
}
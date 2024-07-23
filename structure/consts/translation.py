"""
Provides key translations, i.e., parameter names to human-readable labels.
"""

TRANSLATIONS_EXP = {

}

TRANSLATIONS_ARCH = {
    'CLB_pins_per_group': 'No. of CLB pins per group',
    'num_feedback_ble': 'No. of feedback pins per BLE',
    'lut_size': 'LUT size'
}

TRANSLATIONS_DESIGN = {
    # General
    'impl': 'Implementation',
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
    'buffer_stages': 'Buffer stages',
    
    #GEMM
    'row_num': 'No. of rows',
    'col_num': 'No. of columns',
    'length': 'Length',
}
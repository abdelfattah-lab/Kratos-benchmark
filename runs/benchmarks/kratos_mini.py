"""
Scaled-down experiments for architecture testing.
"""
from runs.benchmarks import get_params

def get_conv_1d_fu_params(base_params: dict[str, any], exp_root_dir: str = 'mini/conv_1d/fu') -> dict[str, any]:
    """
    Add Conv-1D Fully-Unrolled parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 8,
        'img_d': 8,
        'fil_w': 3,
        'res_d': 8,
        'stride_w': 1
    })

def get_conv_1d_pw_params(base_params: dict[str, any], exp_root_dir: str = 'mini/conv_1d/pw') -> dict[str, any]:
    """
    Add Conv-1D Pixel-Wise parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 16,
        'img_d': 16,
        'fil_w': 3,
        'res_d': 16,
        'stride_w': 1
    })

def get_conv_2d_fu_params(base_params: dict[str, any], exp_root_dir: str = 'mini/conv_2d/fu') -> dict[str, any]:
    """
    Add Conv-2D Fully-Unrolled parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 4,
        'img_h': 4,
        'img_d': 4,
        'fil_w': 2,
        'fil_h': 2,
        'res_d': 4,
        'stride_w': 1,
        'stride_h': 1
    })

def get_conv_2d_rp_params(base_params: dict[str, any], exp_root_dir: str = 'mini/conv_2d/rp') -> dict[str, any]:
    """
    Add Conv-2D Row-Parallel parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 8,
        'img_h': 8,
        'img_d': 8,
        'fil_w': 3,
        'fil_h': 3,
        'res_d': 8,
        'stride_w': 1,
        'stride_h': 1
    })

def get_conv_2d_pw_params(base_params: dict[str, any], exp_root_dir: str = 'mini/conv_2d/pw') -> dict[str, any]:
    """
    Add Conv-2D Pixel-Wise parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 16,
        'img_h': 16,
        'img_d': 16,
        'fil_w': 3,
        'fil_h': 3,
        'res_d': 16,
        'stride_w': 1,
        'stride_h': 1
    })

def get_gemmt_fu_params(base_params: dict[str, any], exp_root_dir: str = 'mini/gemmt/fu') -> dict[str, any]:
    """
    Add GEMM-T Fully-Unrolled parameters.
    """
    size = 6
    return get_params(base_params, exp_root_dir, {
        'row_num': 7,
        'col_num': 7,
        'length': 8
    })

def get_gemmt_rp_params(base_params: dict[str, any], exp_root_dir: str = 'mini/gemmt/rp') -> dict[str, any]:
    """
    Add GEMM-T Fully-Unrolled parameters.
    """
    size = 16
    return get_params(base_params, exp_root_dir, {
        'row_num': size,
        'col_num': size,
        'length': size
    })

def get_gemms_params(base_params: dict[str, any], exp_root_dir: str = 'mini/gemms') -> dict[str, any]:
    """
    Add GEMM-S parameters.
    """
    size = 16
    return get_params(base_params, exp_root_dir, {
        'row_num': size,
        'col_num': size,
        'length': size
    })
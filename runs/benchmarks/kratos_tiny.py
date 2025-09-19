"""
Extremely small experiment parameters for testing circuit synthesizability.
"""
from runs.benchmarks import get_params

def get_conv_1d_fu_params(base_params: dict[str, any], exp_root_dir: str = 'tiny/conv_1d/fu') -> dict[str, any]:
    """
    Add Conv-1D Fully-Unrolled parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 4,
        'img_d': 4,
        'fil_w': 2,
        'res_d': 4,
        'stride_w': 1
    })

def get_conv_1d_pw_params(base_params: dict[str, any], exp_root_dir: str = 'tiny/conv_1d/pw') -> dict[str, any]:
    """
    Add Conv-1D Pixel-Wise parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 8,
        'img_d': 8,
        'fil_w': 3,
        'res_d': 8,
        'stride_w': 1
    })

def get_conv_2d_fu_params(base_params: dict[str, any], exp_root_dir: str = 'tiny/conv_2d/fu') -> dict[str, any]:
    """
    Add Conv-2D Fully-Unrolled parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 3,
        'img_h': 3,
        'img_d': 3,
        'fil_w': 2,
        'fil_h': 2,
        'res_d': 3,
        'stride_w': 1,
        'stride_h': 1
    })

def get_conv_2d_rp_params(base_params: dict[str, any], exp_root_dir: str = 'tiny/conv_2d/rp') -> dict[str, any]:
    """
    Add Conv-2D Row-Parallel parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 3,
        'img_h': 3,
        'img_d': 3,
        'fil_w': 2,
        'fil_h': 2,
        'res_d': 3,
        'stride_w': 1,
        'stride_h': 1
    })

def get_conv_2d_pw_params(base_params: dict[str, any], exp_root_dir: str = 'tiny/conv_2d/pw') -> dict[str, any]:
    """
    Add Conv-2D Pixel-Wise parameters.
    """
    return get_params(base_params, exp_root_dir, {
        'img_w': 3,
        'img_h': 3,
        'img_d': 3,
        'fil_w': 2,
        'fil_h': 2,
        'res_d': 3,
        'stride_w': 1,
        'stride_h': 1
    })

def get_gemmt_fu_params(base_params: dict[str, any], exp_root_dir: str = 'tiny/gemmt/fu') -> dict[str, any]:
    """
    Add GEMM-T Fully-Unrolled parameters.
    """
    size = 4
    return get_params(base_params, exp_root_dir, {
        'row_num': size,
        'col_num': size,
        'length': size
    })

def get_gemmt_rp_params(base_params: dict[str, any], exp_root_dir: str = 'tiny/gemmt/rp') -> dict[str, any]:
    """
    Add GEMM-T Fully-Unrolled parameters.
    """
    size = 8
    return get_params(base_params, exp_root_dir, {
        'row_num': size,
        'col_num': size,
        'length': size
    })

def get_gemms_params(base_params: dict[str, any], exp_root_dir: str = 'tiny/gemms') -> dict[str, any]:
    """
    Add GEMM-S parameters.
    """
    size = 8
    return get_params(base_params, exp_root_dir, {
        'row_num': size,
        'col_num': size,
        'length': size
    })
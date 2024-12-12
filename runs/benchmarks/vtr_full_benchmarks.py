"""
Experiments to simulate VTR benchmarks.
"""

from runs.benchmarks import get_params
import os

def get_vtr_verilog_dir() -> str:
    """
    Looks for the Verilog benchmarks within VTR.
    Requires VTR_ROOT to be set.
    """
    vtr_root_dir = os.environ.get('VTR_ROOT')
    if vtr_root_dir is None:
        raise ValueError("VTR_ROOT not set!")
    
    return os.path.join(vtr_root_dir, 'vtr_flow', 'benchmarks', 'verilog')


def get_all_vtr_bm_params(base_params: dict[str, any], exp_root_dir: str = 'vtr_full_bm'):
    """
    Load ALL VTR benchmark implementations as a list.
    """
    return get_params(base_params, exp_root_dir, {
        'verilog_dir': get_vtr_verilog_dir(),
        'subset': 'vtr-bm',
        'impl': [
            # 'bgm', # has falling-edge latches
            'blob_merge', 
            # 'boundtop', # has falling-edge latches
            # 'ch_intrinsics', # has falling-edge latches
            'diffeq1', 
            'diffeq2', 
            'LU8PEEng', 
            'LU32PEEng', 
            'mcml', 
            'mkDelayWorker32B', 
            'mkPktMerge',
            'mkSMAdapter4B',
            # 'or1200', # has falling-edge latches
            # 'raygentop', # has falling-edge latches
            'sha',
            'stereovision0',
            'stereovision1',
            'stereovision2',
            # 'stereovision3', # has falling-edge latches
        ],
    })

def get_all_koios_params(base_params: dict[str, any], exp_root_dir: str = 'vtr_full_bm'):
    """
    Load ALL Koios benchmark implementations as a list.
    """
    return get_params(base_params, exp_root_dir, {
        'verilog_dir': os.path.join(get_vtr_verilog_dir(), 'koios'),
        'subset': 'koios',
        'impl': [
            'dla_like.large',
            'clstm_like.large',
            # 'deepfreeze', # in another directory
            'tdarknet_like.large',
            'bwave_like.fixed.large',
            # 'bwave_like.float.large', # too big
            'bwave_like.float.small',
            'lstm',
            'bnn',
            'lenet',
            # 'dnnweaver', # broken
            'tpu_like.large.os',
            'tpu_like.large.ws',
            'gemm_layer',
            # 'attention_layer', # broken
            'conv_layer',
            'conv_layer_hls',
            'robot_rl',
            'reduction_layer',
            'spmv',
            'eltwise_layer',
            'softmax',
            # 'proxy', # in another directory
        ],
    })
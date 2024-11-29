"""
Experiments to simulate VTR benchmarks.
"""

from runs.benchmarks import get_params

def get_all_vtr_bm_params(base_params: dict[str, any], exp_root_dir: str = 'vtr_full_bm'):
    """
    Load ALL VTR benchmark implementations as a list.
    """
    return get_params(base_params, exp_root_dir, {
        'verilog_dir': 'verilog/vtr_full_benchmarks',
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
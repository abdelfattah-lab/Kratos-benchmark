import structure.consts.keys as keys

from runs.vtr_denoised_v1 import run_vtr_denoised_v1

import runs.benchmarks as general_bm
import runs.benchmarks.kratos as kratos
import runs.benchmarks.kratos_mini as mini

import util.derived_metrics as derived_metrics

# Stratix-IV, v1.2
from impl.arch.stratix_IV.gen_exp_fpop import GenExpFpopArchFactory

# Stratix 10
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory

# Conv-1D
from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_1d.pw import Conv1dPwDesign

# Conv-2D
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.conv_2d.rp import Conv2dRpDesign
from impl.design.conv_2d.pw import Conv2dPwDesign

# GEMM-T
from impl.design.gemmt.fu import GemmTFuDesign
from impl.design.gemmt.rp import GemmTRpDesign

# GEMM-S
from impl.design.gemms import GemmSDesign

# Verification
from impl.design.simple_unrolled import SimpleUnrolledDesign

import numpy as np
import os.path as path
from pandas import DataFrame

BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        # 'allow_skipping': True,
        'adder_cin_global': False,
        'soft_multiplier_adders': True,
        'route_chan_width': 400,
        'force_denser_packing': True,
        # ... additional Experiment.run() parameters
    },
    keys.KEY_ARCH: {
        # fixed architecture parameters for both baseline and explored
        'cin_mux_stride': 0,
        'direct_ff_mux_with': 'adder',
    },
    keys.KEY_DESIGN: {
        'sparsity': [0, 0.5, 0.9],
        'data_width': list(range(3, 9)), # 3-8
    }
}

VARIABLE_ARCH_PARAMS = dict(
    ble_count=10
)

DESIGN_LIST = [
    # Mini benchmarks
    # (Conv1dFuDesign(), mini.get_conv_1d_fu_params(BASE_PARAMS)),
    # (Conv1dPwDesign(), mini.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign(), mini.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign(), mini.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), mini.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign(), mini.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign(), mini.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), mini.get_gemms_params(BASE_PARAMS)),

    # Kratos benchmarks
    # (Conv1dFuDesign(), kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), kratos.get_conv_1d_pw_params(BASE_PARAMS)),
    (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign(), kratos.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    (GemmTRpDesign(), kratos.get_gemmt_rp_params(BASE_PARAMS)),
    (GemmSDesign(), kratos.get_gemms_params(BASE_PARAMS)),

    # Benchmarks for verification
    # (SimpleUnrolledDesign(), general_bm.get_params(BASE_PARAMS, 'simple_unrolled', {}))
]

# add derived metrics:
# - ADP used
# - CLB average utilization
def add_derived_metrics(df: DataFrame) -> tuple[DataFrame, list[str]]:
    df = derived_metrics.apply_adp_used(df)
    df = derived_metrics.apply_clb_avg_util(df, 10)
    df = derived_metrics.apply_lut5_to_adder_ratio(df)
    return df, ['adp_used', 'clb_avg_util', 'lut5/adder']

run_vtr_denoised_v1(
    new_arch=LUTSkipArchFactory,
    base_arch=BaseArchFactory,
    design_list=DESIGN_LIST,
    variable_arch_params=VARIABLE_ARCH_PARAMS,
    x_axis=['data_width'],
    filter_params_baseline=['data_width', 'sparsity'],
    group_cols=['sparsity'],
    group_cols_short_labels=dict(sparsity='s'),
    filter_results=['fmax', 'cpd', 'twl', 'area_total_used'],
    filter_blocks=['clb', 'fle',
                    'lut5',
                    'arithmetic_skip.lut5', 
                    'arithmetic_skip.lut5_ff', 
                    'arithmetic_skip.adder',
                    'arithmetic.adder',
                   ],
    avoid_norm=['clb_avg_util', 
                'lut5',
                'arithmetic_skip.lut5', 'arithmetic_skip.lut5_ff', 
                'arithmetic_skip.adder', 'arithmetic.adder',
                ],
    translations={
        'ble_count': 'N',
        'fmax': 'Maximum Frequency',
        'cpd': 'Critical Path Delay',
        'twl': 'Total Wirelength',
        'clb': 'LAB Count',
        'fle': 'ALM Count',
        'area_total_used': 'Total area (used logic area + routing)',
        'adp_used': 'Area-Delay Product (used logic area + routing)',
        'clb_avg_util': '% of CLB used, average',
        # 'flutS.ff': 'Non-arithmetic Register Count',
        # 'arithmetic.ff': 'Arithmetic Register Count',
        # 'ff': 'Total Register Count',
        'lut5': '(Global) 5-LUTs (absolute count)',
        'arithmetic_skip.lut5': '(Skip) 5-LUTs (absolute count)',
        'arithmetic_skip.adder': '(Skip) Adders (absolute count)',
        'arithmetic.adder': '(Normal) Adders (absolute count)',
    },
    df_processing_fn=add_derived_metrics,
    merge_designs=True,
    num_parallel_tasks=4,
    verbose=True,
)
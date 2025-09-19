import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH
from runs.vtr_denoised_v1 import run_vtr_denoised_v1

import runs.benchmarks as general_bm
import runs.benchmarks.kratos as kratos
import runs.benchmarks.kratos_mini as mini
import runs.benchmarks.kratos_tiny as tiny

import util.derived_metrics as derived_metrics

# Stratix-IV, v1.2
from impl.arch.stratix_IV.gen_exp_fpop import GenExpFpopArchFactory

# Stratix 10
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.lut_skip_1d import LUTSkip1dArchFactory
from impl.arch.stratix_10.lut_skip_6 import LUTSkip6ArchFactory

# Conv-1D
from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_1d.pw import Conv1dPwDesign

# Conv-2D
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.conv_2d.rp import Conv2dRpDesign
from impl.design.conv_2d.pw import Conv2dPwDesign
from impl.design.conv_2d.stress_test.fu_and_shaxN import Conv2dFuAndShaxNDesign

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
        # 'force_denser_packing': True,
        # ... additional Experiment.run() parameters
    },
    keys.KEY_ARCH: {
        # fixed architecture parameters for both baseline and explored
        'cin_mux_stride': 0,
        # 'enable_lut6': False,
        # 'direct_ff_mux_with': 'adder',
    },
    keys.KEY_DESIGN: {
        'sparsity': [0, 0.5, 0.9],
        # 'sparsity': 0,
        # 'data_width': 6,
        # 'sha_num': list(range(2, 31, 2)),
        'data_width': list(range(3, 9)), # 3-8
        # 'sha_num': list(range(2, 11, 2)),
    }
}

VARIABLE_ARCH_PARAMS = dict(
    ble_count=10
)

DESIGN_LIST = [
    # Tiny benchmarks
    # (Conv1dFuDesign(), tiny.get_conv_1d_fu_params(BASE_PARAMS)),
    # (Conv1dPwDesign(), tiny.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign(), tiny.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign(), tiny.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), tiny.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign(), tiny.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign(), tiny.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), tiny.get_gemms_params(BASE_PARAMS)),

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
    (Conv1dFuDesign(), kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), kratos.get_conv_1d_pw_params(BASE_PARAMS)),
    (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign(), kratos.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign(), kratos.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), kratos.get_gemms_params(BASE_PARAMS)),

    # Stress tests
    # (Conv2dFuAndShaxNDesign(), kratos.get_conv_2d_fu_and_shaxN_params(BASE_PARAMS, exp_root_dir='conv_2d/fu_and_shaxN'))
    # Benchmarks for verification
    # (SimpleUnrolledDesign(), general_bm.get_params(BASE_PARAMS, 'simple_unrolled', {}))
]

# add derived metrics:
# - ADP used
# - CLB average utilization
def add_derived_metrics(df: DataFrame) -> tuple[DataFrame, list[str]]:
    # df = derived_metrics.apply_clb_avg_util(df, 10)
    df = derived_metrics.apply_adder_avg_util(df)
    
    # 5-LUT measurements
    df = derived_metrics.apply_lut5_to_adder_ratio(df)
    df = derived_metrics.apply_lut5_concurrency(df)

    # 5-LUT measurements
    df = derived_metrics.apply_lut6_to_adder_ratio(df)
    df = derived_metrics.apply_lut6_concurrency(df)

    # 5/6-LUT measurements
    df = derived_metrics.apply_lut56_to_adder_ratio(df)
    df = derived_metrics.apply_lut56_concurrency(df)
    
    # Area calculations
    df = derived_metrics.apply_area_fle(df)

    # ADP
    # df = derived_metrics.apply_adp_used(df)
    df = derived_metrics.apply_adp_fle(df)

    return df, [
        # 'clb_avg_util', 
        'adder_avg_util',
        'lut5/adder',
        'lut5_concurrency',
        'lut6/adder',
        'lut6_concurrency',
        'lut56/adder',
        'lut56_concurrency',
        'area_fle',
        # 'adp_used',
        'adp_fle', 
    ]

run_vtr_denoised_v1(
    # new_arch=LUTSkipArchFactory,
    # new_arch=LUTSkip1dArchFactory,
    new_arch=LUTSkip6ArchFactory,
    base_arch=BaseArchFactory,
    design_list=DESIGN_LIST,
    variable_arch_params=VARIABLE_ARCH_PARAMS,
    # x_axis=['sha_num'],
    x_axis=['data_width'],
    filter_params_baseline=[
        # 'sha_num', 
        'data_width', 'sparsity'],
    filter_params_add=['per_fle_area'],
    # group_cols=['data_width'],
    group_cols=['sparsity'],
    group_cols_short_labels=dict(sparsity='s', data_width='dw'),
    filter_results=['fmax', 'cpd', 'twl', 
                    'concurrent_lut5s', 'concurrent_lut6s',
                    ],
    filter_blocks=['clb', 'fle',
                    'lut5', 'lut6',
                    'adder',
                   ],
    avoid_norm=[
                'lut5/adder',
                'lut5_concurrency',
                'lut6/adder',
                'lut6_concurrency',
                'lut56/adder',
                'lut56_concurrency',
                ],
    avoid_plot=[
                'per_fle_area',
                'concurrent_lut5s', 'concurrent_lut6s',
                'lut5', 'lut6',
                'adder',
                ],
    translations=TRANSLATIONS_GRAPH,
    df_processing_fn=add_derived_metrics,
    merge_designs=True,
    num_parallel_tasks=4,
    verbose=True,
    desc='Base vs. LUT Skip[6], conv1d-FU/PW, conv2d-FU',
    notify_batch=25,
    notify='telegram',
)
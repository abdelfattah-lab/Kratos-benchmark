import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH
from runs.vtr_denoised_v1 import run_vtr_denoised_v1, run_vtr_denoised_6arch

import util.derived_metrics as derived_metrics

# Stratix 10
from impl.arch.stratix_10.fair.base import BaseArchFactory
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.lut_skip_scratch3 import LUTSkip3ArchFactory
from impl.arch.stratix_10.lut_skip_1d import LUTSkip1dArchFactory
from impl.arch.stratix_10.lut_skip_6 import LUTSkip6ArchFactory
from impl.arch.stratix_10.sharing_1 import LUTSkipArchShare1
from impl.arch.stratix_10.sharing_2 import LUTSkipArchShare2
from impl.arch.stratix_10.sharing_3 import LUTSkipArchShare3
from impl.arch.stratix_10.sharing_4 import LUTSkipArchShare4

# VTR Standard Benchmark Loader parameters
import runs.benchmarks.vtr_full_benchmarks as vtr_bm

# Designs (Kratos)
from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_1d.pw import Conv1dPwDesign
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.conv_2d.pw import Conv2dPwDesign
from impl.design.gemmt.fu import GemmTFuDesign
from impl.design.gemmt.rp import GemmTRpDesign
from impl.design.gemms import GemmSDesign

import runs.benchmarks.kratos as kratos
import runs.benchmarks.kratos_tiny as tiny

# VTR Standard Benchmark Loader
from impl.design.vtr_full_benchmarks.loader import VtrBenchmarkLoaderDesign

import numpy as np
import os.path as path
from pandas import DataFrame

BASE_ARCH = BaseArchFactory
EXP_ARCH = LUTSkipArchFactory

BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': True,
        'adder_cin_global': False,
        'soft_multiplier_adders': True,
        'route_chan_width': 400,
        'compressor_tree_type': 'wallace',
        'target_ext_pin_util' : '0.9,0.9',
    },
    keys.KEY_ARCH: {
        # fixed architecture parameters for both baseline and explored
        'cin_mux_stride': 0,
    },
    keys.KEY_DESIGN: {
        'sparsity': 0.5,
        'data_width': 6,
    }
}

VARIABLE_ARCH_PARAMS = None

VARIABLE_ARCH_PARAMS = dict(
    ble_count=10
)

DESIGN_LIST = [
    # VTR Standard benchmarks
    (Conv1dFuDesign(), kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), kratos.get_conv_1d_pw_params(BASE_PARAMS)),
    (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    (Conv2dPwDesign(), kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    (GemmTRpDesign(), kratos.get_gemmt_rp_params(BASE_PARAMS)),
    (GemmSDesign(), kratos.get_gemms_params(BASE_PARAMS)),

    # Tiny benchmarks
    #(Conv1dFuDesign(), tiny.get_conv_1d_fu_params(BASE_PARAMS)),
    #(Conv1dPwDesign(), tiny.get_conv_1d_pw_params(BASE_PARAMS)),
    #(Conv2dFuDesign(), tiny.get_conv_2d_fu_params(BASE_PARAMS)),
    #(Conv2dPwDesign(), tiny.get_conv_2d_pw_params(BASE_PARAMS)),
    #(GemmTFuDesign(), tiny.get_gemmt_fu_params(BASE_PARAMS)),
    #(GemmTRpDesign(), tiny.get_gemmt_rp_params(BASE_PARAMS)),
    #(GemmSDesign(), tiny.get_gemms_params(BASE_PARAMS)),
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

print("BASE", BASE_ARCH)
print("EXP", EXP_ARCH, "\n")

run_vtr_denoised_v1(
    new_arch=EXP_ARCH,
    base_arch=BASE_ARCH,
    design_list=DESIGN_LIST,
    variable_arch_params=VARIABLE_ARCH_PARAMS,
    x_axis=['ble_count'],
    filter_params_baseline=['sparsity','data_width'],
    filter_params_add=['per_fle_area'],
    group_cols=['per_fle_area'],
    group_cols_short_labels=dict(),
    filter_results=['fmax', 'cpd', 'twl', 
                    'concurrent_lut5s', 'concurrent_lut6s',
                    ],
    filter_blocks=['clb', 'fle', 'lut4',
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
    rotate_x_axis_labels=True,
    merge_designs=False,
    num_parallel_tasks=1,
    #stagger_launch_sec=120,
    # verbose=True,
    desc='Base vs. Exp'
)
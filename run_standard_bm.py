import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH
from runs.vtr_denoised_v1 import run_vtr_denoised_v1

import util.derived_metrics as derived_metrics

# Stratix 10
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.fair.base import BaseArchFactory
from impl.arch.stratix_10.fair.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.lut_skip_1d import LUTSkip1dArchFactory
from impl.arch.stratix_10.lut_skip_6 import LUTSkip6ArchFactory

# VTR Standard Benchmark Loader parameters
import runs.benchmarks.vtr_full_benchmarks as vtr_bm

# VTR Standard Benchmark Loader
from impl.design.vtr_full_benchmarks.loader import VtrBenchmarkLoaderDesign

import numpy as np
import os.path as path
from pandas import DataFrame

BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': True,
        'avoid_mult': False,
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
        # none required
    }
}

VARIABLE_ARCH_PARAMS = dict(
    ble_count=10
)

DESIGN_LIST = [
    # VTR Standard benchmarks
    # (VtrBenchmarkLoaderDesign(), vtr_bm.get_all_vtr_bm_params(BASE_PARAMS)),
    # Koios benchmarks
    (VtrBenchmarkLoaderDesign(), vtr_bm.get_all_koios_params(BASE_PARAMS)),
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
    new_arch=LUTSkipArchFactory,
    # new_arch=LUTSkip1dArchFactory,
    # new_arch=LUTSkip6ArchFactory,
    base_arch=BaseArchFactory,
    # base_arch=LUTSkipArchFactory,
    design_list=DESIGN_LIST,
    variable_arch_params=VARIABLE_ARCH_PARAMS,
    x_axis=['impl'],
    filter_params_baseline=['impl'],
    filter_params_add=['per_fle_area'],
    group_cols=['per_fle_area'],
    group_cols_short_labels=dict(),
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
    rotate_x_axis_labels=True,
    merge_designs=False,
    num_parallel_tasks=1,
    # verbose=True,
    desc='(Narwhal) Base vs. LUT Skip, all Koios benchmarks',
    notify_batch=25,
    notify='telegram',
)
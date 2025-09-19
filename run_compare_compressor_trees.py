import structure.consts.keys as keys

import runs.benchmarks.kratos as kratos
import runs.benchmarks.kratos_mini as mini

from structure.run import Runner
from util.results import save_and_plot
from util.plot import plot_xy
from util.calc import merge_op

# VTR experiment
from impl.exp.vtr import VtrExperiment

# Stratix IV Architectures
# from impl.arch.stratix_IV.base import BaseArchFactory
# from impl.arch.stratix_IV.gen_exp_parallel_carry import GenExpParallelCCArchFactory

# Stratix 10 Architectures
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.parallel_carry import ParallelCarryArchFactory

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

from copy import deepcopy
import time
import pandas as pd
import numpy as np
import os
import os.path as path

BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': True,
        'adder_cin_global': False,
        'compressor_tree_type': ['wallace', 'dadda', 'cascade', 'old'],
        # ... additional Experiment.run() parameters
    },
    keys.KEY_ARCH: {
        'lut_size': 6,
        # 'cin_mux_stride': 1,
        # 'cin_mux_stride': list(range(1, 4)),
    },
    keys.KEY_DESIGN: {
        'sparsity': 0.5,
        'data_width': list(range(3, 9)),
        # 'data_width': 8
    }
}

DESIGN_LIST = [
    # Mini benchmarks
    # (Conv1dFuDesign(), mini.get_conv_1d_fu_params(BASE_PARAMS)),
    # (Conv1dPwDesign(), mini.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign(), mini.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign(), mini.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), mini.get_conv_2d_pw_params(BASE_PARAMS)),
    (GemmTFuDesign(), mini.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign(), mini.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), mini.get_gemms_params(BASE_PARAMS)),

    # Kratos benchmarks
    # (Conv1dFuDesign(), kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    # (Conv1dPwDesign(), kratos.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign(), kratos.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign(), kratos.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), kratos.get_gemms_params(BASE_PARAMS)),
]

def run_experiments(
        runner: Runner, 
        num_parallel_tasks: int = 8,
        filter_params: list[str] = None,
        filter_results: list[str] = None,
        extract_blocks_list: list[str] = ['clb', 'fle', 'adder']
    ) -> dict[str, pd.DataFrame]:
    """
    Run the Runner on a provided VTR_ROOT.
    """
    os.environ["VTR_ROOT"] = "/media/samsdrive/vtr-exploration/vtr-updated/"
    return runner.run_all_threaded(
        verbose=True,
        num_parallel_tasks=num_parallel_tasks,
        filter_params=filter_params,
        filter_results=filter_results,
        result_kwargs=dict(
            extract_blocks_list=extract_blocks_list
        )
    )

# Construct Runner with experiments.
RUNNER = Runner()
ARCH = BaseArchFactory()
# ARCH = GenExpParallelCCArchFactory()
for (design, params) in DESIGN_LIST:
    RUNNER.add_experiments(VtrExperiment, ARCH, design, params)

# Define parameters.

# set this to True if you want the geometric mean of all included designs.
MERGE_DESIGNS = True

NUM_PARALLEL_TASKS = 8
FILTER_PARAMS = ['data_width', 'compressor_tree_type']
FILTER_BLOCKS = ['clb', 'fle', 'adder', 'lut']
FILTER_RESULTS = [#'fmax', 'area_le', 'area_le_used', 'area_r', 'area_total', 'area_total_used', 
                  'twl', *FILTER_BLOCKS]
TRANSLATIONS = {
    'data_width': 'Data Width',
    'fmax': 'Fmax (MHz)',
    'area_le': 'LE Area (MWTAs)',
    'area_le_used': 'Used Logic Area (MWTAs)',
    'area_r': 'Routing Area (MWTAs)',
    'area_total': 'Total Area of LEs and Routing (MWTAs)',
    'area_total_used': 'Total Area of Used Logic and Routing (MWTAs)',
    'twl': 'Total Wirelength',
    'clb': 'CLB Count',
    'fle': 'FLE Count',
    'adder': 'Adder Count',
    'lut': 'LUT Count',
}

results = run_experiments(
    runner=RUNNER,
    num_parallel_tasks=NUM_PARALLEL_TASKS,
    filter_params=FILTER_PARAMS,
    filter_results=FILTER_RESULTS,
    extract_blocks_list=FILTER_BLOCKS,
)

if MERGE_DESIGNS:
    # take geometric mean.
    merged = None
    for k, v in results.items():
        if merged is None:
            merged = v.copy(deep=True)
        else:
            merged = merge_op(merged, v, lambda a, b: a * b, FILTER_RESULTS)
    
    merged_count = len(results)
    for col in FILTER_RESULTS:
        merged[col] **= 1/merged_count
    
    results['merged'] = merged

# define plot function.
def plot_fn(save_dir: str, filesafe_name: str, df: pd.DataFrame) -> None:
    plot_xy(df, ['compressor_tree_type'], ['data_width'], FILTER_RESULTS,
            x_axis_label=['Data Width'],
            y_axis_label=[TRANSLATIONS.get(c, c) for c in FILTER_RESULTS],
            save_path=path.join(save_dir, f"{filesafe_name}_graphs.png"),
            short_labels=dict(compressor_tree_type='ct'))

# save for each result.
save_and_plot(results, plot_fn=plot_fn)
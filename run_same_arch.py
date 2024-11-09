import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH

from runs.vtr_denoised_same_arch import run_vtr_denoised_same_arch

import runs.benchmarks as general_bm
import runs.benchmarks.kratos as kratos
import runs.benchmarks.kratos_mini as mini
import runs.benchmarks.kratos_tiny as tiny

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

BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        # 'allow_skipping': True,
        'adder_cin_global': False,
        # 'soft_multiplier_adders': True,
        'compressor_tree_type': ['old', 'cascade', 'wallace', 'dadda'],
        'route_chan_width': 400,
        'force_denser_packing': True,
        # ... additional Experiment.run() parameters
    },
    keys.KEY_ARCH: {
        # fixed architecture parameters for both baseline and explored
        # 'lut_size': 5,
        'cin_mux_stride': 0,
        'direct_ff_mux_with': 'adder',
        # 'direct_ff_mux_with': 'lut',
    },
    keys.KEY_DESIGN: {
        # 'sparsity': [0, 0.5, 0.9],
        'data_width': list(range(3, 9)), # 3-8
        'sparsity': 0,
        # 'data_width': 4,
        # 'const_weight': [i for i in range(1, 2 ** 4)]
        # 'tree_base': [2, 3, 4],
        # 'tree_base': 4,
    }
}

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

run_vtr_denoised_same_arch(
    arch=BaseArchFactory,
    design_list=DESIGN_LIST,
    compare_param_key='compressor_tree_type',
    base_param_value='old',
    compare_param_order=['old', 'cascade', 'wallace', 'dadda'],
    short_label='type',
    x_axis=['data_width'],
    filter_params=['data_width'],
    filter_results=['fmax', 'cpd', 'twl', 'area_total_used'],
    filter_blocks=['clb', 'fle',
                    'lut',
                    'arithmetic.adder',
                   ],
    avoid_norm=['lut'],
    translations=TRANSLATIONS_GRAPH,
    merge_designs=True,
    num_parallel_tasks=4,
    verbose=True,
)
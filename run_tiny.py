"""
Runs all benchmarks at extremely small sizes. Use to verify if circuit is synthesizable.
"""

import structure.consts.keys as keys

from runs.vtr_all_designs import run_vtr_all_designs
import runs.benchmarks.kratos_tiny as tiny

# Stratix-10 Architectures
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.parallel_carry import ParallelCarryArchFactory
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.four_bit_adder import FourBitSingleChainArchFactory, FourBitDoubleChainArchFactory

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

import numpy as np
import os.path as path

# ARCH = BaseArchFactory()
# ARCH = ParallelCarryArchFactory()
ARCH_DOUBLE_DUTY = LUTSkipArchFactory()
ARCH_4BIT_DOUBLE_ADDER = FourBitDoubleChainArchFactory()
ARCH_4BIT_SINGLE_ADDER = FourBitSingleChainArchFactory()

ARCH = ARCH_4BIT_SINGLE_ADDER

BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        # 'allow_skipping': True,
        'adder_cin_global': True,
        'soft_multiplier_adders': True,
        # ... additional Experiment.run() parameters
    },
    keys.KEY_ARCH: {
        'lut_size': 6,
        'direct_ff_mux_with': ['lut', 'adder'],
    },
    keys.KEY_DESIGN: {
        'sparsity': [0, 0.5, 0.9],
        # 'sparsity': 0.5,
        'data_width': list(range(3, 9)),
    }
}

DESIGN_LIST = [
    # Tiny benchmarks
    # (Conv1dFuDesign(), tiny.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), tiny.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign(), tiny.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign(), tiny.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), tiny.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign(), tiny.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign(), tiny.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), tiny.get_gemms_params(BASE_PARAMS)),
]



run_vtr_all_designs(
    arch=ARCH,
    design_list=DESIGN_LIST,
    filter_params=['data_width', 'sparsity', 'direct_ff_mux_with'],
    x_axis=['data_width'],
    group_col=['sparsity', 'direct_ff_mux_with'],
    group_cols_short_labels=dict(sparsity='s', direct_ff_mux_with='ff'),
    filter_results=['fmax', 'cpd', 'rcw', 'area_total', 'area_total_used', 'lero', 'lelr_frac', 'lelo_frac', 'lero_frac', 'nets_absorbed_frac'],
    filter_blocks=['io.inpad', 'io.outpad', 'clb', 'fle', 'ff', 'lut'],
    translations={
        'data_width': 'Data Width',
        'fmax': 'Fmax',
        'cpd': 'CPD',
        'rcw': 'Route Channel Width',
        'area_total': 'Total area (logic tiles + routing)',
        'area_total_used': 'Total area (used logic area + routing)',
        'lero': 'LEs as Register only',
        'lelr_frac': '% of LEs as Logic and Register',
        'lelo_frac': '% of LEs as Logic only',
        'lero_frac': '% of LEs as Register only',
        'nets_absorbed_frac': '% of Logical Nets absorbed',
        'io.inpad': 'Input Pins',
        'io.outpad': 'Output Pins',
        'clb': 'CLB Count',
        'fle': 'FLE Count',
        'ff': 'Total Register Count',
        'lut': 'LUT Count',
    },
    num_parallel_tasks=8,
    verbose=True,
    desc='tiny_run',
    notify_batch=5,
)
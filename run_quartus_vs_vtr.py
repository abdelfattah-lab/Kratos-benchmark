import structure.consts.keys as keys
from impl.arch.stratix_10.fair.base import BaseArchFactory

from runs.benchmarks import get_params 
import runs.benchmarks.kratos as kratos
import runs.benchmarks.kratos_mini as mini

from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_1d.pw import Conv1dPwDesign
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.conv_2d.rp import Conv2dRpDesign
from impl.design.conv_2d.pw import Conv2dPwDesign
from impl.design.gemmt.fu import GemmTFuDesign
from impl.design.gemmt.rp import GemmTRpDesign
from impl.design.gemms import GemmSDesign
from impl.design.simple_unrolled import SimpleUnrolledDesign

from impl.exp.quartus import QuartusExperiment
from impl.exp.vtr import VtrExperiment
from structure.run import Runner

import os.path as path

DATA_WIDTH = list(range(3, 9))
BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': True,
        # 'adder_cin_global': True,
        'execute_flow_type': 'compile',
        # ... additional Experiment.run() parameters
    },
    keys.KEY_ARCH: {
        'lut_size': 6, # fix LUT at standard size
    },
    keys.KEY_DESIGN: {
        'data_width': DATA_WIDTH,
        'sparsity': 0,
    }
}

BASE_ARCH = BaseArchFactory()

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

    # ============================================================
    # # Kratos benchmarks
    (Conv1dFuDesign(), kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), kratos.get_conv_1d_pw_params(BASE_PARAMS)),
    (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign(), kratos.get_conv_2d_rp_params(BASE_PARAMS)),
    (Conv2dPwDesign(), kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    (GemmTRpDesign(), kratos.get_gemmt_rp_params(BASE_PARAMS)),
    (GemmSDesign(), kratos.get_gemms_params(BASE_PARAMS)),  
    # ============================================================
    
    
    # Verification
    # (SimpleUnrolledDesign(), get_params(BASE_PARAMS, 'simple_unrolled', {
    #     'const_weight': list(range(1, 2**DATA_WIDTH - 1))
    # }))
]

RUNNER = Runner()
for design, params in DESIGN_LIST:
    RUNNER.add_experiments(
        QuartusExperiment, # Quartus
        # VtrExperiment, # VTR
        BASE_ARCH, design, params
    )

for dir, df in RUNNER.run_all_threaded(
    verbose=True,
    desc='Quartus vs. VTR',
    num_parallel_tasks=1,
    filter_params=['data_width'],
    # Quartus
    filter_results=['alm', 'lut_total'],
    # # VTR
    # filter_results=['fle', 'lut'],
    # result_kwargs=dict(extract_blocks_list=['lut']),
).items():
    df.to_csv(f"{dir.replace('/', '_')}_results.csv")
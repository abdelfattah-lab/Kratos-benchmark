import os
os.chdir(os.path.dirname(os.path.realpath(__file__))) # change working directory to this file's directory (for background scripts)

from structure.run import Runner
from impl.exp.vtr import VtrExperiment
from impl.arch.base import BaseArchFactory
from impl.design.conv_2d.pw import Conv2dPwDesign
import structure.consts.keys as keys

params = {
    keys.KEY_EXP: {
        'root_dir': 'experiments/conv_2d_pw',
        'verilog_search_dir': os.path.join(os.path.dirname(os.path.realpath(__file__)), 'verilog')
    },
    keys.KEY_ARCH: {
        'lut_size': [3, 4, 5, 6]
    },
    keys.KEY_DESIGN: {
        'impl': 'conv_bram_sr_fast',
        'module_dir': 'conv_2d',
        'wrapper_module_name': 'conv_bram_sr_fast_wrapper',
        'data_width': [4, 8],
        'sparsity': [0.0, 0.5, 0.9],
        'img_w': 25,
        'img_h': 25,
        'img_d': 32,
        'fil_w': 3,
        'fil_h': 3,
        'res_d': 64,
        'stride_w': 1,
        'stride_h': 1,
    }
}

runner = Runner(BaseArchFactory(), Conv2dPwDesign(), VtrExperiment, params)
results = runner.run_all_threaded(desc='lut_explore')

# do as required with results: list of (params, results)
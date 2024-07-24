import os
os.chdir(os.path.dirname(os.path.realpath(__file__))) # change working directory to this file's directory (for background scripts)

from structure.run import Runner
from impl.exp.vtr import VtrExperiment
from impl.arch.base import BaseArchFactory
from impl.design.gemmt.fu import GemmTFuDesign
import structure.consts.keys as keys

params = {
    keys.KEY_EXP: {
        'root_dir': 'experiments/gemmt_fu',
        'verilog_search_dir': os.path.join(os.path.dirname(os.path.realpath(__file__)), 'verilog')
    },
    keys.KEY_ARCH: {
        'lut_size': [3, 4, 5, 6]
    },
    keys.KEY_DESIGN: {
        'data_width': [4, 8],
        'sparsity': [0.0, 0.5, 0.9],
        'row_num': 4,
        'col_num': 4,
        'length': 4
    }
}

runner = Runner(BaseArchFactory(), GemmTFuDesign(), VtrExperiment, params)
results = runner.run_all_threaded(
    desc='lut_explore',
    num_parallel_tasks=4,
    filter_params=['lut_size', 'data_width', 'sparsity'],
    filter_results=['fmax', 'cpd', 'blocks', 'clb']
)

# do as required with results: pandas DataFrame
results.to_csv('sample_results.csv')
import os
os.chdir(os.path.dirname(os.path.realpath(__file__))) # change working directory to this file's directory (for background scripts)

from structure.run import Runner
from impl.exp.vtr import VtrExperiment
from impl.arch.stratix_IV.gen_exp import GenExpArchFactory
from impl.design.gemmt.fu import GemmTFuDesign
from impl.design.gemmt.rp import GemmTRpDesign
import structure.consts.keys as keys

# see structure.consts.shared_requirements for required keys.
params = {
    keys.KEY_EXP: {
        'root_dir': 'experiments/sample',
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

runner = Runner()

# add as many experiments as required.
runner.add_experiments(
    VtrExperiment,     # concrete Experiment class
    GenExpArchFactory(), # concrete ArchFactory
    GemmTFuDesign(),   # concrete Design
    params             # parameters
)
# params[keys.KEY_EXP]['root_dir'] += '/rp'
# runner.add_experiments(
#     VtrExperiment,
#     GenExpArchFactory(),
#     GemmTRpDesign(),
#     params
# )

results = runner.run_all_threaded(
    track_run_time=True,                                    # logs execution time of ALL experiments
    desc='lut_explore',                                     # description of run
    num_parallel_tasks=8,                                   # how many threads to create in parallel
    filter_params=['lut_size', 'data_width', 'sparsity'],   # parameters to include in the DataFrame
    filter_results=['fmax', 'cpd', 'blocks', 'clb']         # results to include in the DataFrame
    #... remaining unrecognized arguments are passed into each Experiment.run()
)

# do as required with results: { experiment root directory: pandas DataFrame }
print(results)
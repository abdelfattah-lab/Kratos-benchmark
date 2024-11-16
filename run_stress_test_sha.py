"""
This is stress testing Stratix 10 LUT Skip (impl.arch.stratix_10.lut_skip).

1. Run conv2d-FU mini parameters on baseline, and get minimum required grid size to fit:
- data width 6, 0% sparsity to maintain nice 5-LUT to adder ratios of 0.25 -> 2.00 from N = 2 to 30 sha instances
2. Clamp grid size for both baseline and LUT Skip, and slowly increase N for conv2d-FU and shaxN until failure for each architecture.
3. Compare between 
"""

# Baseline and modified architectures
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory

# Designs
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.conv_2d.stress_test.fu_and_shaxN import Conv2dFuAndShaxNDesign

# Parameters
import runs.benchmarks.kratos_mini as mini
import runs.benchmarks.kratos as kratos

# Experiment
from impl.exp.vtr import VtrExperiment

# Runner and typing
from structure.run import Runner
from structure.arch import ArchFactory

# Constants
import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH

# utilities
import util.derived_metrics as derived_metrics
from util.formatting import pretty
from util.calc import merge_op
from util.results import save_and_plot
from util.plot import plot_xy

# Python libraries
import os.path as path
import pandas as pd

# Define base parameters
BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': True,
        'allow_skip_existing': True,
        'adder_cin_global': False,
        'soft_multiplier_adders': True,
        'route_chan_width': 400,
    },
    keys.KEY_ARCH: {
        # fixed architecture parameters for both baseline and explored
        'cin_mux_stride': 0,
        'enable_lut6': False,
    },
    keys.KEY_DESIGN: {
        'sparsity': 0,
        'data_width': 6,
    }
}

# Define filtered parameters and results
FILTER_PARAMS = ['sha_num', 'data_width', 'per_fle_area']
FILTER_RESULTS = ['fmax', 'cpd', 'twl', 'concurrent_lut5s']
FILTER_BLOCKS = ['clb', 'fle', 'lut5', 'adder']

PLOT_COLS = ['fmax', 'cpd', 'twl', 'clb', 'fle', 'lut5/adder', 'lut5_concurrency', 'area_fle', 'adp_fle']
AVOID_NORM_COLS = ['per_fle_area', 'concurrent_lut5s', 'lut5/adder', 'lut5_concurrency']

# Make ArchFactory and Design instances
BASE_ARCH = BaseArchFactory()
MOD_ARCH = LUTSkipArchFactory()
BASE_DESIGN = Conv2dFuDesign()
SHA_DESIGN = Conv2dFuAndShaxNDesign()

# 1. Run baseline and get grid size
print("(!) Running initial sizing...")
base_exp = VtrExperiment(BASE_ARCH, BASE_DESIGN, mini.get_conv_2d_fu_params(BASE_PARAMS))
base_exp.run()
if base_exp.process:
    base_exp.process.wait()
base_results = base_exp.get_result()

grid_w, grid_h = base_results.get('gridx', 0), base_results.get('gridy', 0)
if grid_w == 0 or grid_h == 0:
    print("(!) Failed to determine grid size.")
    exit()

print(f"(!) Sizing to {grid_w} x {grid_h}.")

# 2.1 Fix grid size
BASE_PARAMS[keys.KEY_ARCH]['fixed_size'] = (grid_w, grid_h)

# 2.2 Define run function
def get_max_N(arch: ArchFactory) -> list[dict[str, any]]:
    """
    Returns the result dictionary of all possible instances to fit in the architecture.
    """
    # Define runner.
    runner = Runner()

    # Keep running in batches of 3 until failure.
    sha_num_start = 1 # start of batch
    main_df = None
    
    while True:
        # set batch of 3
        possible_sha_values = list(range(sha_num_start, sha_num_start+3))
        params = kratos.get_conv_2d_fu_and_shaxN_params(BASE_PARAMS)
        params[keys.KEY_DESIGN]['sha_num'] = possible_sha_values

        # run batch of 3
        runner.add_experiments(VtrExperiment, arch, SHA_DESIGN, params)
        results = runner.run_all_threaded(
            verbose=True,
            desc=f'sha_nums {sha_num_start} to {sha_num_start+2}',
            num_parallel_tasks=3,
            filter_params=FILTER_PARAMS,
            filter_results=FILTER_RESULTS + FILTER_BLOCKS,
            result_kwargs=dict(
                extract_blocks_list=FILTER_BLOCKS,
            ),
            notify_via_tele=False,
        )
        runner.clear_experiments()
        if len(results) == 0:
            # all failed; return existing records
            break
        
        # get maximum sha success
        df = list(results.values())[0]
        if main_df is None:
            main_df = df
        else:
            main_df = pd.concat([main_df, df], ignore_index=True)

        # break if less than 3 records (at least one failure)
        if df.shape[0] < 3:
            break

        # increment for next batch
        sha_num_start += 3

    # apply derived metrics
    main_df = derived_metrics.apply_adder_avg_util(main_df)
    main_df = derived_metrics.apply_area_fle(main_df)
    main_df = derived_metrics.apply_adp_fle(main_df)
    main_df = derived_metrics.apply_lut5_to_adder_ratio(main_df)
    main_df = derived_metrics.apply_lut5_concurrency(main_df)
    
    # return all found records
    main_df.sort_values(by='sha_num', inplace=True)
    return main_df

# get all possible instances for each architecture
print("(!) Getting all possible instances for base architecture...")
base_df = get_max_N(BASE_ARCH)
print("(!) Getting all possible instances for modified architecture...")
mod_df = get_max_N(MOD_ARCH)

# Print maximums
print("(!) Maximum for base architecture:")
pretty(base_df.loc[base_df['sha_num'].idxmax()].to_dict(), 1)
print("(!) Maximum for modified architecture:")
pretty(mod_df.loc[mod_df['sha_num'].idxmax()].to_dict(), 1)

# Merge on 'sha_num' and normalize to baseline
norm_df = merge_op(mod_df, base_df, lambda a, b: a/b, 
                   merge_on=['sha_num'],
                   ignore=AVOID_NORM_COLS + ['data_width', 'per_fle_area'])

# Save results
def plot_fn(save_dir: str, filesafe_name: str, df: pd.DataFrame):
    plot_xy(
        df=df,
        group_identifiers=['data_width'],
        x_axis_col=['sha_num'],
        x_axis_label=['SHA instances'],
        y_axis_col=PLOT_COLS,
        y_axis_label=[f"{'*' if c in AVOID_NORM_COLS else ''}{TRANSLATIONS_GRAPH.get(c, c)}" for c in PLOT_COLS],
        short_labels=dict(data_width='dw'),
        save_path=path.join(save_dir, f"{filesafe_name}.png"),
        normalized_y_axes=list(set(PLOT_COLS) - set(AVOID_NORM_COLS)),
        )

save_and_plot(
    results=dict(stress_test_sha=norm_df),
    plot_fn=plot_fn,
)
"""
This is stress testing both a baseline and modified architecture, with a Kratos design and stress test plugin.

1. Run Kratos parameters on baseline, and get minimum required grid size to fit:
- e.g., conv2d-FU with shaxN plugin: data width 6, 0% sparsity to maintain nice 5-LUT to adder ratios of 0.25 -> 2.00 from N = 2 to 30 sha instances
2. Clamp grid size for both baseline and LUT Skip, and slowly increase stress test parameter until failure for each architecture.
3. Compare final metrics.
"""

# Baseline and modified architectures
from impl.arch.stratix_10.fair.base import BaseArchFactory
from impl.arch.stratix_10.fair.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.lut_skip_scratch3 import LUTSkip3ArchFactory # @2.19 20:08, 10 dummy inputs
from impl.arch.stratix_10.four_bit_adder import FourBitDoubleChainArchFactory

# Designs
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

# Plugins
from impl.plugin.shaxN import ShaxNPlugin

# Parameters
import runs.benchmarks.kratos_mini as mini
import runs.benchmarks.kratos as kratos

# Experiment
from impl.exp.vtr import VtrExperiment

# Runner and typing
from structure.run import Runner
from typing import Type
from structure.arch import ArchFactory
from structure.design import PluginDesign
from structure.plugin import Plugin

# Constants
import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH

# utilities
import util.derived_metrics as derived_metrics
from util.formatting import pretty
from util.calc import merge_op
from util.results import save_and_plot
from util.plot import plot_xy
# from util.external_notifs import telegram_notify

# Python libraries
import os.path as path
import pandas as pd
from copy import deepcopy
from time import sleep

# Define base parameters
BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': True,
        'allow_skip_existing': True,
        'adder_cin_global': False,
        'soft_multiplier_adders': True,
        'route_chan_width': 400,
        'force_denser_packing': False,
        'target_ext_pin_util' : '0.9,0.9',
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

# Define derived metrics
def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = derived_metrics.apply_adder_avg_util(df)
    df = derived_metrics.apply_area_fle(df)
    df = derived_metrics.apply_adp_fle(df)
    df = derived_metrics.apply_lut5_to_adder_ratio(df)
    df = derived_metrics.apply_lut5_concurrency(df)

    return df

# Make ArchFactory and Design instances
BASE_ARCH = LUTSkip3ArchFactory()
MOD_ARCH = FourBitDoubleChainArchFactory()

# Define design class list and plugin, N parameter
PLUGIN = ShaxNPlugin()
N_PARAM = 'sha_num'
DESIGN_CLASS_LIST = [
    # Mini benchmarks
    (Conv1dFuDesign, mini.get_conv_1d_fu_params(BASE_PARAMS)),
    # (Conv1dPwDesign, mini.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign, mini.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign, mini.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign, mini.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign, mini.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign, mini.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign, mini.get_gemms_params(BASE_PARAMS)),
    
    # Kratos benchmarks
    # (Conv1dFuDesign, kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    # (Conv1dPwDesign, kratos.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign, kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dRpDesign, kratos.get_conv_2d_rp_params(BASE_PARAMS)),
    # (Conv2dPwDesign, kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign, kratos.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign, kratos.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign, kratos.get_gemms_params(BASE_PARAMS)),
]

# Other args
MACHINE_NAME = "Beluga"

# Define run function
def get_max_N(arch: ArchFactory, DesignClass: Type[PluginDesign], plugin: Plugin, base_params: dict[str, any], N_param: str) -> pd.DataFrame:
    """
    Returns the DataFrame of all possible instances to fit in the architecture.
    """
    # Define runner.
    runner = Runner()

    # Keep running in batches of 3 until failure.
    N_start = 1 # start of batch
    main_df = None
    
    while True:
        # set batch of 3
        possible_N_values = list(range(N_start, N_start+3))
        params = deepcopy(base_params)
        params[keys.KEY_EXP]['root_dir'] = path.join(params[keys.KEY_EXP]['root_dir'], arch.__class__.__name__)
        params[keys.KEY_DESIGN][N_param] = possible_N_values

        # run batch of 3
        runner.add_experiments(VtrExperiment, arch, DesignClass(plugin=plugin), params)
        results = runner.run_all_threaded(
            verbose=True,
            desc=f'N {N_start} to {N_start+2}',
            num_parallel_tasks=3,
            filter_params=FILTER_PARAMS,
            filter_results=FILTER_RESULTS + FILTER_BLOCKS,
            result_kwargs=dict(
                extract_blocks_list=FILTER_BLOCKS,
            ),
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
        N_start += 3

    # apply derived metrics
    main_df = add_derived_metrics(main_df)
    
    # return all found records
    main_df.sort_values(by=N_param, inplace=True)
    return main_df

def run_seq(DesignClass: Type[PluginDesign], plugin: Plugin, base_params: dict[str, any], N_param: str) -> dict[str, pd.DataFrame]:
    """
    Returns:
    {
        'base': DataFrame,
        'mod': DataFrame,
        'norm': DataFrame,
    }
    """

    design_name = DesignClass.__name__
    # notify_via_tele(f"Starting design {design_name}.")

    # 1. Run baseline with 1 instance and get grid size
    print("(!) Running initial sizing...")
    params = deepcopy(base_params)
    params[keys.KEY_EXP]['root_dir'] = path.join(params[keys.KEY_EXP]['root_dir'], BASE_ARCH.__class__.__name__)
    params[keys.KEY_DESIGN][N_param] = 1
    base_exp = VtrExperiment(BASE_ARCH, DesignClass(plugin=plugin), params)
    base_exp.run()
    if base_exp.process:
        base_exp.process.wait()
    base_results = base_exp.get_result()
    print(base_results)

    grid_w, grid_h = base_results.get('gridx', 0), base_results.get('gridy', 0)
    if grid_w == 0 or grid_h == 0:
        print("(!) Failed to determine grid size.")
        return None
    

    print(f"(!) Sizing to {grid_w} x {grid_h}.")

    # 2.1 Fix grid size
    base_params[keys.KEY_ARCH]['fixed_size'] = (grid_w, grid_h)

    # get all possible instances for each architecture
    print("(!) Getting all possible instances for base architecture...")
    base_df = get_max_N(BASE_ARCH, DesignClass, plugin, base_params, N_param)
    print("(!) Getting all possible instances for modified architecture...")
    mod_df = get_max_N(MOD_ARCH, DesignClass, plugin, base_params, N_param)

    # Print maximums
    base_max = base_df.loc[base_df[N_param].idxmax()].to_dict()
    mod_max = mod_df.loc[mod_df[N_param].idxmax()].to_dict()
    print("(!) Maximum for base architecture:")
    pretty(base_max, 1)
    print("(!) Maximum for modified architecture:")
    pretty(mod_max, 1)
    

    # Merge on 'sha_num' and normalize to baseline
    norm_df = merge_op(mod_df, base_df, lambda a, b: a/b, 
                    merge_on=[N_param],
                    ignore=AVOID_NORM_COLS + ['data_width', 'per_fle_area'])

    return dict(
        base=base_df,
        mod=mod_df,
        norm=norm_df,
    )


#### MAIN RUN SEQUENCE ####
base_dfs = {}
mod_dfs = {}
norm_dfs = {}
for DesignClass, base_params in DESIGN_CLASS_LIST:
    design_name = DesignClass.__name__
    

    print(f"(!) ---- At design '{design_name}' ----")
    dfs = run_seq(DesignClass, PLUGIN, base_params, N_PARAM)
    if dfs is None:
        continue

    base_dfs[design_name] = dfs['base']
    mod_dfs[design_name] = dfs['mod']
    norm_dfs[design_name] = dfs['norm']

# Save raw results
def do_with_dir_fn(save_dir: str) -> None:
    def save_df(df, name, suffix):
        df.to_csv(path.join(save_dir, f"{name}_{suffix}"))

    for key in base_dfs.keys():
        base_df = base_dfs[key]
        mod_df = mod_dfs[key]

        save_df(base_df, key, 'base_raw')
        save_df(mod_df, key, 'mod_raw')

# Save results
def plot_fn(save_dir: str, filesafe_name: str, df: pd.DataFrame):
    plot_xy(
        df=df,
        group_identifiers=['data_width'],
        x_axis_col=[N_PARAM],
        x_axis_label=['N'],
        y_axis_col=PLOT_COLS,
        y_axis_label=[f"{'*' if c in AVOID_NORM_COLS else ''}{TRANSLATIONS_GRAPH.get(c, c)}" for c in PLOT_COLS],
        short_labels=dict(data_width='dw'),
        save_path=path.join(save_dir, f"{filesafe_name}.png"),
        normalized_y_axes=list(set(PLOT_COLS) - set(AVOID_NORM_COLS)),
        )
save_and_plot(
    results=norm_dfs,
    do_with_dir_fn=do_with_dir_fn,
    plot_fn=plot_fn,
)

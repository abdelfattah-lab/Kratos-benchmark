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

# Input sharing architectures
from impl.arch.stratix_10.sharing_1 import LUTSkipArchShare1
from impl.arch.stratix_10.sharing_2 import LUTSkipArchShare2
from impl.arch.stratix_10.sharing_3 import LUTSkipArchShare3
from impl.arch.stratix_10.sharing_4 import LUTSkipArchShare4

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

# utilities
import util.derived_metrics as derived_metrics
from util.formatting import pretty
from util.calc import merge_op
from util.external_notifs import telegram_notify

# Python libraries
import os.path as path
import os
from datetime import datetime as dt
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
BASE_STRATIX_ARCH = BaseArchFactory()
FOURSHARING_ARCH = LUTSkipArchShare4()
THREESHARING_ARCH = LUTSkipArchShare3()
TWOSHARING_ARCH = LUTSkipArchShare2()
ONESHARING_ARCH =LUTSkipArchShare1()
BASEDD5_ARCH = LUTSkipArchFactory()

# Define design class list and plugin, N parameter
PLUGIN = ShaxNPlugin()
N_PARAM = 'sha_num'
DESIGN_CLASS_LIST = [
    # Mini benchmarks
    (Conv1dFuDesign, mini.get_conv_1d_fu_params(BASE_PARAMS)),
    #(Conv1dPwDesign, mini.get_conv_1d_pw_params(BASE_PARAMS)),
    (Conv2dFuDesign, mini.get_conv_2d_fu_params(BASE_PARAMS)),
    #(Conv2dRpDesign, mini.get_conv_2d_rp_params(BASE_PARAMS)),
    #(Conv2dPwDesign, mini.get_conv_2d_pw_params(BASE_PARAMS)),
    (GemmTFuDesign,  mini.get_gemmt_fu_params(BASE_PARAMS)),
    #(GemmTRpDesign,  mini.get_gemmt_rp_params(BASE_PARAMS)),
    #(GemmSDesign,    mini.get_gemms_params(BASE_PARAMS)),
    
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
NOTIFY_VIA_TELE = True
MACHINE_NAME = "Beluga"

# define notify function
def notify_via_tele(msg: str) -> None:
    if not NOTIFY_VIA_TELE:
        return
    
    telegram_notify(f"[{MACHINE_NAME}] Stress test: {msg}")

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

    if main_df is None:
        return pd.DataFrame()

    main_df = add_derived_metrics(main_df)
    
    # return all found records
    main_df.sort_values(by=N_param, inplace=True)
    return main_df

def run_seq(DesignClass: Type[PluginDesign], plugin: Plugin, base_params: dict[str, any], N_param: str) -> dict[str, pd.DataFrame]:
    """
    Returns:
    {
        'base_stratix': DataFrame,
        'fourshare': DataFrame,
        'threeshare': DataFrame,
        'twoshare': DataFrame,
        'oneshare': DataFrame,
        'base_dd5': DataFrame,
    }
    """

    design_name = DesignClass.__name__
    notify_via_tele(f"Starting design {design_name}.")

    # 1. Run baseline with 1 instance and get grid size
    print("(!) Running initial sizing...")
    params = deepcopy(base_params)
    params[keys.KEY_EXP]['root_dir'] = path.join(params[keys.KEY_EXP]['root_dir'], BASE_STRATIX_ARCH.__class__.__name__)
    params[keys.KEY_DESIGN][N_param] = 1
    base_exp = VtrExperiment(BASE_STRATIX_ARCH, DesignClass(plugin=plugin), params)
    base_exp.run()
    if base_exp.process:
        base_exp.process.wait()
    base_results = base_exp.get_result()

    grid_w, grid_h = base_results.get('gridx', 0), base_results.get('gridy', 0)
    if grid_w == 0 or grid_h == 0:
        print("(!) Failed to determine grid size.")
        return None
    

    notify_via_tele(f"sizing {design_name} to {grid_w} x {grid_h}.")
    print(f"(!) Sizing to {grid_w} x {grid_h}.")

    # 2.1 Fix grid size
    sweep_params = deepcopy(base_params)
    sweep_params[keys.KEY_ARCH]['fixed_size'] = (grid_w, grid_h)

    # get all possible instances for each architecture
    print("(!) Getting all possible instances for base Stratix-10 architecture...")
    base_stratix_df = get_max_N(BASE_STRATIX_ARCH, DesignClass, plugin, sweep_params, N_param)
    print("(!) Getting all possible instances for 4Z architecture...")
    fourshare_df = get_max_N(FOURSHARING_ARCH, DesignClass, plugin, sweep_params, N_param)
    print("(!) Getting all possible instances for 3Z architecture...")
    threeshare_df = get_max_N(THREESHARING_ARCH, DesignClass, plugin, sweep_params, N_param)
    print("(!) Getting all possible instances for 2Z architecture...")
    twoshare_df = get_max_N(TWOSHARING_ARCH, DesignClass, plugin, sweep_params, N_param)
    print("(!) Getting all possible instances for 1Z architecture...")
    oneshare_df = get_max_N(ONESHARING_ARCH, DesignClass, plugin, sweep_params, N_param)
    print("(!) Getting all possible instances for base DD5 architecture...")
    base_dd5_df = get_max_N(BASEDD5_ARCH, DesignClass, plugin, sweep_params, N_param)

    # Print maximums
    if not base_stratix_df.empty:
        base_stratix_max = base_stratix_df.loc[base_stratix_df[N_param].idxmax()].to_dict()
        print("(!) Maximum for base Stratix-10 architecture:")
        pretty(base_stratix_max, 1)
    else:
        print("(!) Maximum for base Stratix-10 architecture: No successful runs")

    if not fourshare_df.empty:
        fourshare_max = fourshare_df.loc[fourshare_df[N_param].idxmax()].to_dict()
        print("(!) Maximum for 4Z architecture:")
        pretty(fourshare_max, 1)
    else:
        print("(!) Maximum for 4Z architecture: No successful runs")

    if not threeshare_df.empty:
        threeshare_max = threeshare_df.loc[threeshare_df[N_param].idxmax()].to_dict()
        print("(!) Maximum for 3Z architecture:")
        pretty(threeshare_max, 1)
    else:
        print("(!) Maximum for 3Z architecture: No successful runs")

    if not twoshare_df.empty:
        twoshare_max = twoshare_df.loc[twoshare_df[N_param].idxmax()].to_dict()
        print("(!) Maximum for 2Z architecture:")
        pretty(twoshare_max, 1)
    else:
        print("(!) Maximum for 2Z architecture: No successful runs")

    if not oneshare_df.empty:
        oneshare_max = oneshare_df.loc[oneshare_df[N_param].idxmax()].to_dict()
        print("(!) Maximum for 1Z architecture:")
        pretty(oneshare_max, 1)
    else:
        print("(!) Maximum for 1Z architecture: No successful runs")

    if not base_dd5_df.empty:
        base_dd5_max = base_dd5_df.loc[base_dd5_df[N_param].idxmax()].to_dict()
        print("(!) Maximum for base DD5 architecture:")
        pretty(base_dd5_max, 1)
    else:
        print("(!) Maximum for base DD5 architecture: No successful runs")

    return dict(
        base_stratix=base_stratix_df,
        fourshare=fourshare_df,
        threeshare=threeshare_df,
        twoshare=twoshare_df,
        oneshare=oneshare_df,
        base_dd5=base_dd5_df,
    )

#### MAIN RUN SEQUENCE ####
base_stratix_dfs = {}
fourshare_dfs = {}
threeshare_dfs = {}
twoshare_dfs = {}
oneshare_dfs = {}
base_dd5_dfs = {}

for DesignClass, base_params in DESIGN_CLASS_LIST:
    design_name = DesignClass.__name__
    

    print(f"(!) ---- At design '{design_name}' ----")
    dfs = run_seq(DesignClass, PLUGIN, base_params, N_PARAM)
    if dfs is None:
        continue

    base_stratix_dfs[design_name] = dfs['base_stratix']
    fourshare_dfs[design_name] = dfs['fourshare']
    threeshare_dfs[design_name] = dfs['threeshare']
    twoshare_dfs[design_name] = dfs['twoshare']
    oneshare_dfs[design_name] = dfs['oneshare']
    base_dd5_dfs[design_name] = dfs['base_dd5']

# Save results

def make_results_dir(parent: str = "results") -> str:
    save_dir = path.join(parent, dt.now().strftime("%d%b%y-%H.%M.%S"))
    os.makedirs(save_dir, exist_ok=True)
    return save_dir

def save_all_csvs(save_dir: str) -> None:
    def save_df(df, name, suffix):
        df.to_csv(path.join(save_dir, f"{name}_{suffix}.csv"), index=False)

    for key in base_stratix_dfs.keys():
        save_df(base_stratix_dfs[key], key, 'base_stratix_raw')
        save_df(fourshare_dfs[key],    key, 'fourshare_raw')
        save_df(threeshare_dfs[key],   key, 'threeshare_raw')
        save_df(twoshare_dfs[key],     key, 'twoshare_raw')
        save_df(oneshare_dfs[key],     key, 'oneshare_raw')
        save_df(base_dd5_dfs[key],     key, 'base_dd5_raw')

save_dir = make_results_dir("results")
save_all_csvs(save_dir)
notify_via_tele(f"Saved CSVs to {save_dir}")
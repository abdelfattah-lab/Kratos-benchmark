import structure.consts.keys as keys
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory
from impl.exp.vtr import VtrExperiment
from structure.run import Runner
from structure.arch import ArchFactory
from structure.design import Design
from util.calc import merge_op
from util.results import save_and_plot
from util.plot import plot_xy

from typing import Type
import os.path as path
from os import sep
import pandas as pd
from copy import deepcopy

def run_vtr_denoised_stress_test(
        design_pair_list: list[tuple[tuple[Type[Design], dict[str, any]], tuple[Type[Design], dict[str, any]]]],
        filter_params_baseline: list[str],
        new_arch: Type[ArchFactory] = LUTSkipArchFactory,
        base_arch: Type[ArchFactory] = BaseArchFactory,
        x_axis: list[str] = None,
        group_cols: list[str] = None,
        group_cols_short_labels: dict[str, str] = {},
        filter_results: list[str] = ['fmax', 'cpd', 'twl', 'area_total', 'area_total_used'],
        filter_blocks: list[str] = ['clb', 'fle'],
        seeds: tuple[int, int, int] = (1239, 5741, 1473),
        merge_designs: bool = False,
        avoid_norm: list[str] = [],
        translations: dict[str, str] = {},
        **runner_kwargs
    ) -> None:
    """
    Runs the following sequence:
    0. Design pairs are read as (base_design, stress_test_design).
    1. Runs all provided designs on base_arch and new_arch on provided seeds.
    2. Averages results across all seeds for each architecture.
    3. For each architecture, normalize gains/losses in stress_test_design to base_design.
    4. Plots normalized results with base and stress test designs in separate groups, and saves both baseline and normalized results to the default results folder, under the latest timestamp.

    Required arguments:
    * design_pair_list:[((Design, params: dict[str, any]), (Design, params: dict[str, any])), ...], all the design pairs, and their associated full base parameters. You can generate these parameters with the functions under `runs.benchmarks`.
    * filter_params_baseline:[str, ...], parameters (non-architecture) that are varied and should be extracted into a DataFrame (e.g., sparsity, data width).
    
    Optional arguments:
    * new_arch:class<ArchFactory>, ArchFactory class to be used as 'new' architecture. Default: impl.arch.stratix_IV.gen_exp.GenExpArchFactory  
    * base_arch:class<ArchFactory>, ArchFactory class to be used as 'base' architecture. Default: impl.arch.stratix_IV.base.BaseArchFactory  
    * x_axis: list[str], list of columns (1 or 2) that should be used as the graph's x-axis. Should be a subset of the keys of variable_arch_params. If None, then all keys of variable_arch_params is used. Default: None
    * group_cols: list[str], list of columns that should be used to group lines together. If None, then 'filter_params_baseline' is used. Note that a 'design' column is always added. Default: None
    * group_cols_short_labels:dict[str, str], short translations for parameter keys (e.g., 'sparsity': 's').
    * filter_results:list[str], list of parameters to extract from VPR (excluding Pb types blocks; see filter_blocks). All will be baseline normalized (unless also in avoid_norm) and plotted.
    * filter_blocks:list[str], list of Pb type blocks to extract from VPR. All will be baseline normalized (unless also in avoid_norm) and plotted.
    * seeds: (int, int, int), a tuple of 3 seeds to use for averaging.
    * merge_designs:bool, will take the geometric mean of all designs as the final result and generate an additional 'merged' result if True. Default: False
    * avoid_norm:list[str], list of columns that should not be normalized (i.e., the value stays absolute). Default: empty list
    * translations:dict[str, str], dictionary mapping columns -> long names. If not present in the dictionary, then the column name is re-used. Default: empty dictionary
    
    Remaining keyword arguments are passed directly to Runner.run_all_threaded().
    """
    # Sanity checks
    if len(x_axis) < 1 or len(x_axis) > 2:
        raise ValueError("x_axis must be of length of either 1 or 2!")
    
    # Ensure parameters for post-processing are present
    if 'cpd' not in filter_results:
        filter_results.append('cpd')
    if 'clb' not in filter_blocks:
        filter_blocks.append('clb')
    
    # Define variables
    DESIGN_COL = 'design'
    DESIGN_SHORT_LABEL = 'des'
    runner = Runner()

    exp_types = {
        'baseline': base_arch(),
        'new': new_arch(),
    }
    exp_results = {
        'baseline': {},
        'new': {}
    }
    design_mappings = {}

    # add all experiments for all seeds
    for seed in seeds:
        for design_pair in design_pair_list:
            for exp_type, arch in exp_types.items():
                design_root_dirs = []
                for design, params in design_pair:
                    p = deepcopy(params)
                    p[keys.KEY_EXP]['seed']  = seed
                    
                    # use the root directory to keep track of base and stress test design.
                    design_root_dir = p[keys.KEY_EXP]['root_dir']
                    design_root_dirs.append(design_root_dir)

                    p[keys.KEY_EXP]['root_dir'] = path.join(design_root_dir, f"{exp_type}-{seed}")
                    runner.add_experiments(VtrExperiment, arch, design, p)
                
                # map base -> stress test
                design_mappings[design_root_dirs[0]] = design_root_dirs[1]

    # run all experiments
    filter_results += filter_blocks
    results = runner.run_all_threaded(
        filter_params=filter_params_baseline,
        filter_results=filter_results,
        result_kwargs=dict(
            extract_blocks_list=filter_blocks
        ),
        **runner_kwargs
    )

    # process results
    for exp_dir, df in results.items():
        # process experiment directory
        exp_dir_split = exp_dir.split(sep)
        true_exp_dir = sep.join(exp_dir_split[:-1])
        exp_type, seed = exp_dir_split[-1].split('-')

        df['adp_used'] = df['area_total_used'] * df['cpd']

        # concatenate DataFrames
        df_dict = exp_results[exp_type]
        if true_exp_dir not in df_dict:
            df_dict[true_exp_dir] = df
        else:
            df_dict[true_exp_dir] = pd.concat([df_dict[true_exp_dir], df], ignore_index=True)
    
    # add post-processing keys
    filter_results.append('adp_used')       # ADP, used area

    # take means of each DataFrame
    for exp_type, dfs in exp_results.items():
        # used if merge_designs is True
        merged = None

        for key, df in dfs.items():
            flt = filter_params_baseline.copy()
            
            seed_mean = df.groupby(by=flt).mean().reset_index()
            if merge_designs:
                # merge all DataFrames into one DataFrame
                if merged is None:
                    merged = seed_mean.copy(deep=True)
                else:
                    # multiply columns
                    merged = merge_op(merged, seed_mean, lambda a, b: a * b, flt)
            
            # save DataFrame individually
            exp_results[exp_type][key] = seed_mean

        if merge_designs:
            # drop all other keys
            keys_to_drop = list(exp_results[exp_type].keys())
            # for key in keys_to_drop:
            #     exp_results[exp_type].pop(key, None)
            
            # take the n-th root (geometric mean)
            for col in filter_results:
                merged[col] **= 1/(len(keys_to_drop))
            exp_results[exp_type]['merged'] = merged

    # baseline normalization and post-processing
    norm_results = {}
    for base_design, stress_design in design_mappings.items():
        # normalize gains/losses of stress_design to base_design for both baseline and new architecture
        df_base_arch = merge_op(exp_results['baseline'][stress_design], exp_results['baseline'][base_design], lambda a, b: (a-b) / b, filter_params_baseline, ignore=avoid_norm)
        df_stress_arch = merge_op(exp_results['new'][stress_design], exp_results['new'][base_design], lambda a, b: (a-b) / b, filter_params_baseline, ignore=avoid_norm)

        print("base gains:")
        print(df_base_arch)
        
        print("stress gains:")
        print(df_stress_arch)

        # add distinguishing columns
        df_base_arch[DESIGN_COL] = 'base'
        df_stress_arch[DESIGN_COL] = 'stress'

        # perform concat
        norm_results[base_design + '+' + stress_design] = pd.concat([df_stress_arch, df_base_arch], ignore_index=True)

    # save all raw results
    def do_with_dir_fn(dir: str):
        for key, results in exp_results.items():
            for exp_dir, df in results.items():
                df.to_csv(path.join(dir, f"{exp_dir.replace(path.sep, '_')}_{key}_results_raw.csv"))
        

    # define plot function
    if group_cols is None:
        group_cols = filter_params_baseline
    group_cols.append(DESIGN_COL)
    group_cols_short_labels[DESIGN_COL] = DESIGN_SHORT_LABEL
    def plot_fn(save_dir: str, filesafe_name: str, df: pd.DataFrame) -> None:
        plot_xy(df, group_cols, x_axis, filter_results,
                x_axis_label=[translations.get(c, c) for c in x_axis],
                y_axis_label=[f"{'*' if c in avoid_norm else ''}{translations.get(c, c)}" for c in filter_results],
                save_path=path.join(save_dir, f"{filesafe_name}_graphs.png"),
                short_labels=group_cols_short_labels)
    
    # save into results directory
    save_and_plot(norm_results, do_with_dir_fn=do_with_dir_fn, plot_fn=plot_fn)
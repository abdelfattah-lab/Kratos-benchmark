import structure.consts.keys as keys
from impl.arch.stratix_IV.base import BaseArchFactory
from impl.arch.stratix_IV.gen_exp_parallel_carry import GenExpParallelCCArchFactory
from impl.exp.vtr import VtrExperiment
from structure.run import Runner
from structure.arch import ArchFactory
from structure.design import Design
from util.calc import merge_op
from util.results import save_and_plot
from util.plot import plot_xy
from util.search import query_df

from typing import Type, Callable
import os.path as path
from os import sep
import pandas as pd
from copy import deepcopy

def run_vtr_denoised_v1(
        design_list: list[tuple[Type[Design], dict[str, any]]],
        variable_arch_params: dict[str, list[any]],
        filter_params_baseline: list[str],
        new_arch: Type[ArchFactory] = GenExpParallelCCArchFactory,
        base_arch: Type[ArchFactory] = BaseArchFactory,
        group_normalize_on: list[str] = None,
        normalize_each_group_on: dict[str, any] = None,
        x_axis: list[str] = None,
        group_cols: list[str] = None,
        group_cols_short_labels: dict[str, str] = {},
        filter_params_add: list[str] = [],
        filter_results: list[str] = ['fmax', 'cpd', 'rcw', 'area_total', 'area_total_used'],
        filter_blocks: list[str] = ['clb', 'fle'],
        seeds: tuple[int, int, int] = (1239, 5741, 1473),
        merge_designs: bool = False,
        avoid_norm: list[str] = [],
        avoid_plot: list[str] = [],
        translations: dict[str, str] = {},
        df_processing_fn: Callable[[pd.DataFrame], tuple[pd.DataFrame, list[str]]] = None,
        **runner_kwargs
    ) -> None:
    """
    Runs the following sequence:
    1. Runs all provided designs on v0 and new_arch on provided seeds.
    2. Averages results across all seeds for each architecture.
    3. Normalize results, depending on normalize_on: (Baseline normalization)
    - If provided, then group DataFrame into rows based on each unique value of group_normalize_on, select the row within each group based on the columns and values provided in normalize_each_group_on, and use this row as the baseline for each group.
    - If not provided, then use v0 as baseline.
    4. Plots normalized results, and saves both baseline and normalized results to the default results folder, under the latest timestamp.

    Required arguments:
    * design_list:[(Design, params: dict[str, any]), ...], all the designs and their associated full base parameters. You can generate these parameters with the functions under `runs.benchmarks`.
    * variable_arch_params:dict[str, [...]], variable parameters that are added to the baseline architecture parameters, intended for the v1 architecture.
    * filter_params_baseline:[str, ...], parameters (non-architecture) that are varied and should be extracted into a DataFrame (e.g., sparsity, data width).
    
    Optional arguments:
    * new_arch:class<ArchFactory>, ArchFactory class to be used as 'new' architecture. Default: impl.arch.stratix_IV.gen_exp.GenExpArchFactory  
    * base_arch:class<ArchFactory>, ArchFactory class to be used as 'base' architecture. Default: impl.arch.stratix_IV.base.BaseArchFactory  
    * normalize_group_on: list[str], if provided, then perform group normalization as described in step 3. Provide an empty list to group the entire DataFrame as one group. Default: None
    * normalize_each_group_on:dict[str, any], if provided, then use a row that is uniquely identified by each column: value pair, to use as the baseline for all others in the group. Must be provided if group_normalize_on is not None. Default: None
    * x_axis: list[str], list of columns (1 or 2) that should be used as the graph's x-axis. Should be a subset of the keys of variable_arch_params. If None, then all keys of variable_arch_params is used. Default: None
    * group_cols: list[str], list of columns that should be used to group lines together. If None, then 'filter_params_baseline' is used. Default: None
    * group_cols_short_labels:dict[str, str], short translations for parameter keys (e.g., 'sparsity': 's').
    * filter_params_add:list[str], list of parameters to extract from input parameters, but not use for merging databases. Put parameters here if they cause empty DataFrames. Default: empty list
    * filter_results:list[str], list of parameters to extract from VPR (excluding Pb types blocks; see filter_blocks). All will be baseline normalized (unless also in avoid_norm) and plotted.
    * filter_blocks:list[str], list of Pb type blocks to extract from VPR. All will be baseline normalized (unless also in avoid_norm) and plotted.
    * seeds: (int, int, int), a tuple of 3 seeds to use for averaging.
    * merge_designs:bool, will take the geometric mean of all designs as the final result and generate an additional 'merged' result if True. Default: False
    * avoid_norm:list[str], list of columns that should not be normalized (i.e., the value stays absolute). Default: empty list
    * avoid_norm:list[str], list of columns that should not be plotted (i.e., required by another derived metric, but should not be presented). Default: empty list
    * translations:dict[str, str], dictionary mapping columns -> long names. If not present in the dictionary, then the column name is re-used. Default: empty dictionary
    * df_processing_fn: (pd.DataFrame) -> (pd.DataFrame, list[str]), function called on each mean DataFrame from 3 seeds to add any derived metrics. Returns (new DataFrame, keys to add to filter_results).  Default: None
    Remaining keyword arguments are passed directly to Runner.run_all_threaded().
    """
    # x-axis is derived from variable architecture parameters
    filter_params_new = list(variable_arch_params.keys()) 
    if x_axis is None:
        x_axis = filter_params_new
    
    # Sanity checks
    if len(x_axis) < 1 or len(x_axis) > 2:
        raise ValueError("x_axis must be of length of either 1 or 2!")
    if group_normalize_on is not None and normalize_each_group_on is None:
        raise ValueError("normalize_each_group_on must be provided if group_normalize_on is provided!")

    # Check if baseline is to be used
    should_use_baseline = group_normalize_on is None

    # Define variables
    runner = Runner()

    exp_types = {
        'baseline': base_arch(),
        'new': new_arch(),
    }
    exp_results = {
        'baseline': {},
        'new': {}
    }

    if not should_use_baseline:
        # skip baseline generation
        del exp_types['baseline']
        del exp_results['baseline']
    
    # Setup Runner
    runner = Runner()
    
    # add all experiments for all seeds
    for seed in seeds:
        for (design, params) in design_list:
            for exp_type, arch in exp_types.items():
                p = deepcopy(params)
                p[keys.KEY_EXP]['seed']  = seed
                p[keys.KEY_EXP]['root_dir'] = path.join(p[keys.KEY_EXP]['root_dir'], f"{exp_type}-{seed}")
                if exp_type != 'baseline':
                    p[keys.KEY_ARCH] |= variable_arch_params
                runner.add_experiments(VtrExperiment, arch, design, p)

    # run all experiments
    filter_results += filter_blocks
    results = runner.run_all_threaded(
        filter_params=filter_params_baseline + filter_params_add + filter_params_new,
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

        # concatenate DataFrames (and take mean if complete)
        df_dict = exp_results[exp_type]
        if true_exp_dir not in df_dict:
            df_dict[true_exp_dir] = df
        else:
            df_dict[true_exp_dir] = pd.concat([df_dict[true_exp_dir], df], ignore_index=True)

    # take means of each DataFrame
    for exp_type, dfs in exp_results.items():
        # used if merge_designs is True
        merged = None

        for key, df in dfs.items():
            flt = filter_params_baseline.copy()
            if exp_type != 'baseline':
                flt += filter_params_new
            
            seed_mean = df.groupby(by=flt).mean().reset_index()

            # add post-processing (if any)
            if df_processing_fn is not None:
                seed_mean, new_keys = df_processing_fn(seed_mean)
                # added this way to preserve existing order
                for df_key in new_keys:
                    if df_key not in filter_results:
                        filter_results.append(df_key)

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
    new_raw_results = {}
    norm_results = exp_results['new']
    for key, df in norm_results.items():
        # save a raw copy
        new_raw_results[key] = df

        if should_use_baseline:
            # perform merge and divide by baseline
            norm_results[key] = merge_op(df, exp_results['baseline'][key], lambda a, b: a / b, filter_params_baseline, ignore=avoid_norm)
        else:
            # normalize within DataFrame, in groups
            def normalize_group(group):
                # normalize within each group
                baseline_query = query_df(group, normalize_each_group_on)
                if baseline_query is None:
                    raise ValueError(f"Could not find a row that matches these column: values; {normalize_each_group_on}")
                if baseline_query.shape[0] > 1:
                    raise ValueError(f"More than one row matches column: values - try being more specific; {normalize_each_group_on}")
                
                baseline_row = baseline_query.iloc[0]
                norm_cols = list(set(filter_results) - set(avoid_norm))
                group[norm_cols] = group[norm_cols].div(baseline_row[norm_cols], axis=1)

                return group
            
            norm_results[key] = df.groupby(group_normalize_on, group_keys=False).apply(normalize_group)

    # save baseline results
    def do_with_dir_fn(dir: str):
        # save raw results
        for exp_dir, df in new_raw_results.items():
            df.to_csv(path.join(dir, f"{exp_dir.replace(path.sep, '_')}_raw_results.csv"))

        if not should_use_baseline:
            # skip baseline CSV generation
            return
        
        for exp_dir, df in exp_results['baseline'].items():
            df.to_csv(path.join(dir, f"{exp_dir.replace(path.sep, '_')}_baseline_results.csv"))

    # define plot function
    if group_cols is None:
        group_cols = filter_params_baseline
    filter_results = [x for x in filter_results if x not in avoid_plot]
    def plot_fn(save_dir: str, filesafe_name: str, df: pd.DataFrame) -> None:
        plot_xy(df, group_cols, x_axis, filter_results,
                x_axis_label=[translations.get(c, c) for c in x_axis],
                y_axis_label=[f"{'*' if c in avoid_norm else ''}{translations.get(c, c)}" for c in filter_results],
                save_path=path.join(save_dir, f"{filesafe_name}_graphs.png"),
                short_labels=group_cols_short_labels,
                normalized_y_axes=list(set(filter_results) - set(avoid_norm)),
                )
    
    # save into results directory
    save_and_plot(norm_results, do_with_dir_fn=do_with_dir_fn, plot_fn=plot_fn)
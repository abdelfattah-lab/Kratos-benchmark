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

from typing import Type
import os.path as path
from os import sep
import pandas as pd
from copy import deepcopy

def run_vtr_denoised_same_arch(
        design_list: list[tuple[Type[Design], dict[str, any]]],
        compare_param_key: str,
        base_param_value: any,
        filter_params: list[str],
        x_axis: list[str],
        arch: Type[ArchFactory] = BaseArchFactory,
        compare_param_order: list[any] = None,
        short_label: str = None,
        filter_results: list[str] = ['fmax', 'cpd', 'rcw', 'area_total', 'area_total_used'],
        filter_blocks: list[str] = ['clb', 'fle'],
        seeds: tuple[int, int, int] = (1239, 5741, 1473),
        merge_designs: bool = False,
        avoid_norm: list[str] = [],
        translations: dict[str, str] = {},
        **runner_kwargs
    ) -> None:
    """
    Runs the following sequence:
    1. Runs all provided designs on arch provided on provided seeds.
    2. Averages results across all seeds for each possible parameter value in compare_param_key.
    3. Normalize results to base_param_value.
    4. Plots normalized results, and saves both baseline and normalized results to the default results folder, under the latest timestamp.

    Required arguments:
    * compare_param_key:str, the parameter key that is varied. One parameter value, base_param_value, is used as the baseline value for the remaining values.
    * base_param_value:any, the baseline parameter value.
    * filter_params:[str, ...], parameters (non-architecture) that are varied and should be extracted into a DataFrame (e.g., sparsity, data width).
    * x_axis: list[str], list of columns (1 or 2) that should be used as the graph's x-axis.
    
    Optional arguments:
    * arch:class<ArchFactory>, ArchFactory class to be used as architecture. Default: impl.arch.stratix_IV.base.BaseArchFactory  
    * compare_param_order:list[any], the order of the 'bar' chart grouping. If None, then any order will suffice. Default: None
    * short_label:str, short label to be used in place of compare_param_key. If None, then the first three characters are used. Default: None
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
    
    # Setup Runner and architecture
    runner = Runner()
    arch_inst = arch()
    # add all experiments for all seeds
    for seed in seeds:
        for (design, params) in design_list:
            p = deepcopy(params)
            p[keys.KEY_EXP]['seed']  = seed
            p[keys.KEY_EXP]['root_dir'] = path.join(p[keys.KEY_EXP]['root_dir'], f"seed-{seed}")
            runner.add_experiments(VtrExperiment, arch_inst, design, p)

    # run all experiments
    # add compare_param_key
    exp_filter_params = [*filter_params]
    if compare_param_key not in exp_filter_params:
        exp_filter_params.append(compare_param_key)
    filter_results += filter_blocks
    results = runner.run_all_threaded(
        filter_params=exp_filter_params,
        filter_results=filter_results,
        result_kwargs=dict(
            extract_blocks_list=filter_blocks
        ),
        **runner_kwargs
    )

    # process results
    df_dict: dict[str, pd.DataFrame] = {}
    mean_dict: dict[str, pd.DataFrame] = {}
    norm_dict: dict[str, pd.DataFrame] = {}

    for exp_dir, df in results.items():
        # process experiment directory
        exp_dir_split = exp_dir.split(sep)
        true_exp_dir = sep.join(exp_dir_split[:-1])
        _, seed = exp_dir_split[-1].split('-')

        # concatenate DataFrames (and take mean if complete)
        if true_exp_dir not in df_dict:
            df_dict[true_exp_dir] = df
        else:
            df_dict[true_exp_dir] = pd.concat([df_dict[true_exp_dir], df], ignore_index=True)

    # take means of each DataFrame
    merged = None # used if merge_designs is True
    for exp_dir, df in df_dict.items():
        seed_mean = df.groupby(by=exp_filter_params).mean().reset_index()
        if merge_designs:
            # merge all DataFrames into one DataFrame
            if merged is None:
                merged = seed_mean.copy(deep=True)
            else:
                # multiply columns
                merged = merge_op(merged, seed_mean, lambda a, b: a * b, exp_filter_params)
        
        # save DataFrame individually
        mean_dict[exp_dir] = seed_mean

    if merge_designs:
        # drop all other keys
        keys_to_drop = list(mean_dict.keys())
        # for key in keys_to_drop:
        #     mean_dict.pop(key, None)
        
        # take the n-th root (geometric mean)
        for col in filter_results:
            merged[col] **= 1/(len(keys_to_drop))
        mean_dict['merged'] = merged

    # baseline normalization and post-processing
    for key, df in mean_dict.items():
        print(f"-- normalizing {key}")
        # normalize within DataFrame, in groups
        def normalize_group(group):
            # normalize within each group
            baseline_query = query_df(group, {compare_param_key: base_param_value})
            if baseline_query is None:
                raise ValueError(f"Could not find a row that matches these column: values; {compare_param_key}: {base_param_value}")
            if baseline_query.shape[0] > 1:
                raise ValueError(f"More than one row matches column: values - try being more specific; {compare_param_key}: {base_param_value}")
            
            baseline_row = baseline_query.iloc[0]
            norm_cols = list(set(filter_results) - set(avoid_norm))
            group[norm_cols] = group[norm_cols].div(baseline_row[norm_cols], axis=1)

            return group
        
        norm_dict[key] = df.groupby(filter_params, group_keys=False).apply(normalize_group)

    # define dir function (save raw values)
    def do_with_dir_fn(save_dir: str):
        for key, df in mean_dict.items():
            df.to_csv(path.join(save_dir, f"{key.replace('/', '_')}_raw.csv"))

    # define plot function
    def plot_fn(save_dir: str, filesafe_name: str, df: pd.DataFrame) -> None:
        plot_xy(df, [compare_param_key], x_axis, filter_results,
                x_axis_label=[translations.get(c, c) for c in x_axis],
                y_axis_label=[f"{'*' if c in avoid_norm else ''}{translations.get(c, c)}" for c in filter_results],
                save_path=path.join(save_dir, f"{filesafe_name}_graphs.png"),
                short_labels={
                    compare_param_key: short_label if not short_label is None else compare_param_key[:3]
                },
                plot_type_2d='bar',
                group_order=compare_param_order,
                )
    
    # save into results directory
    save_and_plot(norm_dict, do_with_dir_fn=do_with_dir_fn, plot_fn=plot_fn)
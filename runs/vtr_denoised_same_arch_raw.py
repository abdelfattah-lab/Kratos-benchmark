import structure.consts.keys as keys
from impl.exp.vtr import VtrExperiment
from structure.run import Runner
from structure.arch import ArchFactory
from structure.design import Design
from util.results import save_and_plot

from typing import Type, Callable
import os.path as path
from os import sep
import pandas as pd
from copy import deepcopy

def run_vtr_denoised_same_arch_raw(
        design_list: list[tuple[Design, dict[str, any]]],
        filter_params: list[str],
        arch: Type[ArchFactory],
        filter_results: list[str] = ['fmax', 'cpd', 'rcw', 'area_total', 'area_total_used'],
        filter_blocks: list[str] = ['clb', 'fle'],
        seeds: tuple[int, int, int] = (1239, 5741, 1473),
        df_processing_fn: Callable[[pd.DataFrame], tuple[pd.DataFrame, list[str]]] = None,
        save_to_folder: bool = True,
        prefix: str = '',
        **runner_kwargs
    ) -> pd.DataFrame | str | None:
    """
    Runs the following sequence:
    1. Runs all provided designs on arch provided on provided seeds.
    2. Averages results across all seeds for each possible parameter value in compare_param_key.
    3. Save all provided designs into a large .csv. Formal design names, from Design.get_formal_name(), are saved under a column 'impl'.

    Required arguments:
    * filter_params:[str, ...], parameters (non-architecture) that are varied and should be extracted into a DataFrame (e.g., sparsity, data width).
    * arch:class<ArchFactory>, ArchFactory class to be used as architecture.
    
    Optional arguments:
    * filter_results:list[str], list of parameters to extract from VPR (excluding Pb types blocks; see filter_blocks). All will be baseline normalized (unless also in avoid_norm) and plotted.
    * filter_blocks:list[str], list of Pb type blocks to extract from VPR. All will be baseline normalized (unless also in avoid_norm) and plotted.
    * seeds: (int, int, int), a tuple of 3 seeds to use for averaging.
    * df_processing_fn: (pd.DataFrame) -> (pd.DataFrame, list[str]), function called on each mean DataFrame from 3 seeds to add any derived metrics. Returns (new DataFrame, keys to add to filter_results).  Default: None
    * save_to_folder: bool, whether to save results to folder (True) or just return the runner results (False). Default: True
    * prefix: str, prefix for the results folder name (e.g., 'full-run-' creates 'results/full-run-<timestamp>'). Default: ''
    Remaining keyword arguments are passed directly to Runner.run_all_threaded().

    Returns:
    * str: absolute path to the folder created by save_and_plot when save_to_folder is True.
    * pd.DataFrame: combined DataFrame when save_to_folder is False.
    """
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
    filter_results += filter_blocks
    runner_kwargs |= dict(
        use_formal_name_as_key=True,
    )
    results = runner.run_all_threaded(
        filter_params=filter_params,
        filter_results=filter_results,
        result_kwargs=dict(
            extract_blocks_list=filter_blocks
        ),
        **runner_kwargs
    )

    # process results
    df_dict: dict[str, pd.DataFrame] = {}

    for impl, df in results.items():
        # concatenate DataFrames (and take mean if complete)
        if impl not in df_dict:
            df_dict[impl] = df
        else:
            df_dict[impl] = pd.concat([df_dict[impl], df], ignore_index=True)

    # take means of each DataFrame
    all_df = None
    for impl, df in df_dict.items():
        seed_mean = df.groupby(filter_params).mean().reset_index()

        # add post-processing (if any)
        if df_processing_fn is not None:
            seed_mean, new_keys = df_processing_fn(seed_mean)
            # added this way to preserve existing order
            for df_key in new_keys:
                if df_key not in filter_results:
                    filter_results.append(df_key)

        # save DataFrame individually
        if 'impl' not in seed_mean.columns:
            seed_mean.insert(0, 'impl', impl)
        if all_df is None:
            all_df = seed_mean
        else:
            all_df = pd.concat([all_df, seed_mean], ignore_index=True)

    # save into results directory (or return)
    if save_to_folder:
        return save_and_plot(dict(all=all_df), prefix=prefix)
    else:
        return all_df
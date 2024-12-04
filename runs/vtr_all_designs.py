from structure.design import Design
from structure.run import Runner
from structure.arch import ArchFactory
from impl.exp.vtr import VtrExperiment
from util.results import save_and_plot
from util.plot import plot_xy

from typing import Type, Callable
import pandas as pd
import os.path as path

def run_vtr_all_designs(
        arch: ArchFactory,
        design_list: list[tuple[Type[Design], dict[str, any]]],
        filter_params: list[str],
        x_axis: list[str],
        group_col: list[str],
        filter_results: list[str] = ['fmax', 'cpd', 'rcw', 'area_total', 'area_total_used'],
        filter_blocks: list[str] = ['clb', 'fle'],
        translations: dict[str, str] = {},
        group_cols_short_labels: dict[str, str] = {},
        df_processing_fn: Callable[[pd.DataFrame], tuple[pd.DataFrame, list[str]]] = None,
        rotate_x_axis_labels: bool = False,
        **runner_kwargs,
    ) -> None:
    """
    Simply runs all provided designs, and reports if any failed.
    
    Required arguments:
    * arch: ArchFactory, ArchFactory to run the designs on.
    * design_list:[(Design, params: dict[str, any]), ...], all the designs and their associated full base parameters. You can generate these parameters with the functions under `runs.benchmarks`.
    * filter_params:[str, ...], parameters that should be extracted into a DataFrame (e.g., sparsity, data width).
    * x_axis: list[str], list of columns (1 or 2) that should be used as the graph's x-axis.

    Optional arguments:
    * filter_results:list[str], list of parameters to extract from VPR (excluding Pb types blocks; see filter_blocks). All will be baseline normalized (unless also in avoid_norm) and plotted.
    * filter_blocks:list[str], list of Pb type blocks to extract from VPR. All will be baseline normalized (unless also in avoid_norm) and plotted.
    * translations:dict[str, str], dictionary mapping columns -> long names. If not present in the dictionary, then the column name is re-used. Default: empty dictionary
    * group_cols_short_labels:dict[str, str], short translations for parameter keys (e.g., 'sparsity': 's').
    * df_processing_fn: (pd.DataFrame) -> (pd.DataFrame, list[str]), function called on each result DataFrame to add any derived metrics. Returns (new DataFrame, keys to add to filter_results).  Default: None
    * rotate_x_axis_labels: bool, rotate the x-axis labels to prevent overlap. Use if x-axis labels are long, e.g., strings. Default: False
    
    Remaining keyword arguments are passed directly to Runner.run_all_threaded().
    """

    # Define variables
    runner = Runner()

    # add experiments
    for (design, params) in design_list:
        runner.add_experiments(VtrExperiment, arch, design, params)

    # run all experiments
    filter_results += filter_blocks
    results = runner.run_all_threaded(
        filter_params=filter_params,
        filter_results=filter_results,
        result_kwargs=dict(
            extract_blocks_list=filter_blocks
        ),
        **runner_kwargs
    )

    if df_processing_fn is not None:
        for exp_dir, df in results.items():
            df, new_filters = df_processing_fn(df)
            for key in new_filters:
                if key not in filter_results:
                    filter_results.append(key)

            results[exp_dir] = df

    # define plot function
    def plot_fn(save_dir: str, filesafe_name: str, df: pd.DataFrame) -> None:
        plot_xy(df, group_col, x_axis, filter_results,
                x_axis_label=[translations.get(c, c) for c in x_axis],
                y_axis_label=[f"{translations.get(c, c)}" for c in filter_results],
                save_path=path.join(save_dir, f"{filesafe_name}_graphs.png"),
                short_labels=group_cols_short_labels,
                rotate_x_axis_labels=rotate_x_axis_labels,
                )
    
    # save into results directory
    save_and_plot(results, plot_fn=plot_fn)
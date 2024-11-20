"""
Use VPR with a BlifDesign to explore packing only.
"""

import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH
from structure.run import Runner

# implementations
from impl.exp.vpr import VprExperiment
from impl.blif.concurrency import Concurrent5LUTAdderBlifDesign
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory

import util.derived_metrics as derived
from util.results import save_and_plot
from util.plot import plot_xy

import os
import numpy as np
import pandas as pd

# Define variables used
ARCH = LUTSkipArchFactory()
BLIF_DESIGN = Concurrent5LUTAdderBlifDesign()
BASE_PARAMS = {
    keys.KEY_EXP: {
        'allow_skipping': True,
        'root_dir': 'experiments/vpr-pack/conc',
        'route_chan_width': 400,
        'force_denser_packing': [True, False],
        'ending': 'pack',
    },
    keys.KEY_DESIGN: {
        'adder_count': 1000,
        'lut5_adder_ratio': list(np.round(np.linspace(0.1, 2, 20), 1)),
    },
    keys.KEY_ARCH: {
        'cin_mux_stride': 0,
        'enable_lut6': False,
    },
}



# Setup runner
runner = Runner()
runner.add_experiments(VprExperiment, ARCH, BLIF_DESIGN, BASE_PARAMS)

# Run all
FILTER_PARAMS = ['force_denser_packing', 'lut5_adder_ratio']
FILTER_RESULTS = ['concurrent_lut5s']
FILTER_BLOCKS = ['lut5']
results = runner.run_all_threaded(
    desc='pack-only synthetic N-M concurrency',
    filter_params=FILTER_PARAMS,
    filter_results=FILTER_RESULTS+FILTER_BLOCKS,
    result_kwargs=dict(
        extract_blocks_list=FILTER_BLOCKS,
    ),
    num_parallel_tasks=12,
)

# modify DataFrames
for exp_dir, df in results.items():
    df = derived.apply_lut5_concurrency(df)
    results[exp_dir] = df

FILTER_RESULTS += [
    'lut5_concurrency',
]
ycols = FILTER_RESULTS + FILTER_BLOCKS
def plot_fn(save_dir: str, filesafe_name: str, df: pd.DataFrame) -> None:
    plot_xy(df,
            x_axis_col=['lut5_adder_ratio'],
            x_axis_label=['5-LUT/Adders'],
            group_identifiers=['force_denser_packing'],
            short_labels=dict(force_denser_packing='dp'),
            y_axis_col=ycols,
            y_axis_label=[TRANSLATIONS_GRAPH.get(c, c) for c in ycols],
            save_path=os.path.join(save_dir, f"{filesafe_name}_graph.png"),
    )

save_and_plot(results, plot_fn=plot_fn)
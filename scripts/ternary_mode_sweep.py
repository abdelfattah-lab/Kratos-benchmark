#!/usr/bin/env python3
"""
Compare different DCC3 multiplication implementations side by side across multiple circuits.

Configurations compared:
- base (baseline)
- dcc2
- dcc3 (soft_multiplier_adders)
- dcc3 (wallace_ternary)
- dcc3 (ternary_adder_dp)

Output: Grouped bar charts with circuits on x-axis, configurations as grouped bars.
Each metric (area, cpd, adp) gets its own subplot column.
"""

import structure.consts.keys as keys
from runs.vtr_denoised_same_arch_raw import run_vtr_denoised_same_arch_raw
from utils import VERILOG_DIR
import runs.benchmarks.kratos as kratos
import util.derived_metrics as derived_metrics

# Architecture imports
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.four_bit_adder import (
    DCC2ArchFactory,
    DCC3ArchFactory,
)

# Design imports
from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_1d.pw import Conv1dPwDesign
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.conv_2d.pw import Conv2dPwDesign
from impl.design.gemmt.fu import GemmTFuDesign
from impl.design.gemmt.rp import GemmTRpDesign
from impl.design.gemms import GemmSDesign

import copy
import numpy as np
import os.path as path
from pathlib import Path
from datetime import datetime as dt
from pandas import DataFrame
import pandas as pd
from typing import Type, Sequence
import matplotlib.pyplot as plt

# =============================================================================
# CONFIGURATION
# =============================================================================

# Sparsity to test
SPARSITY = 0.5

# All configurations to compare (arch_class, config_dict, display_name)
CONFIGS_TO_COMPARE = [
    # (BaseArchFactory, {
    #     'name': 'base',
    #     'compressor_tree_type': 'wallace',
    # }, 'base'),

    # (DCC2ArchFactory, {
    #     'name': 'dcc2',
    #     'compressor_tree_type': 'wallace',
    # }, 'dcc2'),

    (DCC3ArchFactory, {
        'name': 'dcc3_sma',
        'soft_multiplier_adders': True,
    }, 'dcc3 (cascade)'),

    (DCC3ArchFactory, {
        'name': 'dcc3_tdp',
        'ternary_adder_dp': True,
    }, 'dcc3 (tdp)'),

    (DCC3ArchFactory, {
        'name': 'dcc3_wallace',
        'soft_multiplier_adders': False,
        'compressor_tree_type': 'wallace',
    }, 'dcc3 (wallace)'),

    (DCC3ArchFactory, {
        'name': 'dcc3_wt',
        'soft_multiplier_adders': False,
        'compressor_tree_type': 'wallace_ternary',
    }, 'dcc3 (wt)'),

    # (DCC3ArchFactory, {
    #     'name': 'dcc3_wt_exp',
    #     'soft_multiplier_adders': False,
    #     'compressor_tree_type': 'wallace_ternary_exp',
    # }, 'dcc3 (wt_exp)'),
]

# Baseline for normalization
BASELINE_NAME = 'dcc3_sma'

# Run configuration
NUM_PARALLEL_TASKS = 1
VERBOSE = False

# Results folder prefix (e.g., 'compare-' creates 'results/compare-<timestamp>')
RUN_PREFIX = 'compare-'

# Metrics to plot (metric_key, y_label)
METRICS_TO_PLOT: Sequence[tuple[str, str]] = (
    ('area_fle', 'Area (Normalized)'),
    ('cpd', 'CPD (Normalized)'),
    ('adp_fle', 'ADP (Normalized)'),
)

# Bar colors for each configuration
BAR_COLORS = {
    'base': '#808080',
    'dcc2': '#ff7f0e',
    'dcc3_sma': '#2ca02c',
    'dcc3_wallace': '#d62728',
    'dcc3_wt': '#1f77b4',
    'dcc3_tdp': '#9467bd',
}

# =============================================================================
# PARAMETERS
# =============================================================================

def get_base_params() -> dict:
    """Get base parameters."""
    return {
        keys.KEY_EXP: {
            'verilog_search_dir': str(VERILOG_DIR),
            'allow_skipping': True,
            'adder_cin_global': False,
            'route_chan_width': 400,
            'target_ext_pin_util': '0.9,0.9',
            'compressor_tree_type': 'wallace',
            'soft_multiplier_adders': False,
            'ternary_adder_dp': False,
            'ternary_adder_chains': False,
            'tree_base': 3
        },
        keys.KEY_ARCH: {
            'cin_mux_stride': 0,
        },
        keys.KEY_DESIGN: {
            'data_width': 6,
            'sparsity': SPARSITY,
            'tree_base': 3
        }
    }

# Designs to run
BASE_PARAMS = get_base_params()
DESIGN_LIST = [
    # (VtrBenchmarkLoaderDesign(), vtr_bm.get_all_vtr_bm_params(BASE_PARAMS)),
    (Conv1dFuDesign(), kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), kratos.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    (GemmTRpDesign(), kratos.get_gemmt_rp_params(BASE_PARAMS)),
    (GemmSDesign(), kratos.get_gemms_params(BASE_PARAMS)),
]


FILTER_PARAMS = ['per_fle_area', 'data_width', 'sparsity', 'compressor_tree_type', 'soft_multiplier_adders', 'ternary_adder_dp']
FILTER_RESULTS = ['fmax', 'cpd', 'twl']
FILTER_BLOCKS = ['clb', 'fle', 'fle1', 'fle2', 'lut5', 'lut6', 'adder']

# =============================================================================
# DERIVED METRICS
# =============================================================================

def add_derived_metrics(df: DataFrame) -> tuple[DataFrame, list[str]]:
    """Add derived metrics to the DataFrame."""
    # Add mult_method column
    def get_mult_method(row):
        if row.get('ternary_adder_dp', False):
            return 'tdp'
        elif row.get('soft_multiplier_adders', False):
            return 'sma'
        else:
            return row.get('compressor_tree_type', 'wallace')
    df['mult_method'] = df.apply(get_mult_method, axis=1)

    df = derived_metrics.dcc1_gather_fle(df)
    df = derived_metrics.apply_area_fle(df)
    df = derived_metrics.apply_adp_fle(df)

    return df, ['mult_method', 'area_fle', 'adp_fle']

# =============================================================================
# EXPERIMENT RUNNING
# =============================================================================

def apply_overrides(design_list: list, arch_config: dict) -> list:
    """Apply architecture-specific overrides to design list parameters."""
    overridden_list = []
    for design, params in design_list:
        new_params = copy.deepcopy(params)

        if 'compressor_tree_type' in arch_config:
            new_params[keys.KEY_EXP]['compressor_tree_type'] = arch_config['compressor_tree_type']
        if 'soft_multiplier_adders' in arch_config:
            new_params[keys.KEY_EXP]['soft_multiplier_adders'] = arch_config['soft_multiplier_adders']
        if 'ternary_adder_dp' in arch_config:
            new_params[keys.KEY_EXP]['ternary_adder_dp'] = arch_config['ternary_adder_dp']
        if 'allow_skipping' in arch_config:
            new_params[keys.KEY_EXP]['allow_skipping'] = arch_config['allow_skipping']

        overridden_list.append((design, new_params))
    return overridden_list


def run_single_config(arch_class: Type, arch_config: dict) -> pd.DataFrame | None:
    """Run a single architecture configuration across all designs."""
    config_name = arch_config['name']

    print(f"\n{'='*60}")
    print(f"Running: {config_name} ({arch_class.__name__})")
    print(f"  compressor_tree_type: {arch_config.get('compressor_tree_type', 'default')}")
    print(f"  soft_multiplier_adders: {arch_config.get('soft_multiplier_adders', False)}")
    print(f"  ternary_adder_dp: {arch_config.get('ternary_adder_dp', False)}")
    print(f"{'='*60}\n")

    design_list = apply_overrides(DESIGN_LIST, arch_config)

    df = run_vtr_denoised_same_arch_raw(
        arch=arch_class,
        design_list=design_list,
        filter_params=FILTER_PARAMS,
        filter_results=FILTER_RESULTS.copy(),
        filter_blocks=FILTER_BLOCKS,
        df_processing_fn=add_derived_metrics,
        verbose=VERBOSE,
        seeds=(1239,),
        num_parallel_tasks=NUM_PARALLEL_TASKS,
        save_to_folder=False,
        desc=f'{config_name}',
    )

    if df is not None:
        df.insert(0, 'config_name', config_name)

    return df


def run_all_configs() -> pd.DataFrame:
    """Run all configurations and return combined DataFrame."""
    all_dfs = []

    for arch_class, arch_config, _ in CONFIGS_TO_COMPARE:
        df = run_single_config(arch_class, arch_config)
        if df is not None:
            all_dfs.append(df)

    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()


# =============================================================================
# NORMALIZATION
# =============================================================================

def normalize_df(df: pd.DataFrame, baseline_name: str) -> pd.DataFrame:
    """Normalize numeric columns against baseline configuration, per implementation."""
    base_df = df[df['config_name'] == baseline_name].copy()
    if base_df.empty:
        print(f"Warning: Baseline '{baseline_name}' not found!")
        return pd.DataFrame()

    result_rows = []
    implementations = df['impl'].unique()

    for impl in implementations:
        impl_base = base_df[base_df['impl'] == impl]
        if impl_base.empty:
            continue
        base_row = impl_base.iloc[0]

        impl_df = df[df['impl'] == impl]
        for _, row in impl_df.iterrows():
            norm_row = {
                'config_name': row['config_name'],
                'impl': row['impl'],
                'mult_method': row.get('mult_method', ''),
            }

            for col in df.columns:
                if col in ['config_name', 'impl', 'mult_method', 'compressor_tree_type',
                           'soft_multiplier_adders', 'ternary_adder_dp']:
                    continue
                if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
                    base_val = base_row[col]
                    if base_val != 0 and not pd.isna(base_val):
                        norm_row[col] = row[col] / base_val
                    else:
                        norm_row[col] = np.nan

            result_rows.append(norm_row)

    return pd.DataFrame(result_rows)


# =============================================================================
# PLOTTING
# =============================================================================

def _geom_mean(series: pd.Series) -> float:
    """Geometric mean of positive, non-NaN values."""
    vals = series.dropna().astype(float)
    vals = vals[vals > 0]
    if vals.empty:
        return float("nan")
    return float(np.exp(np.log(vals).mean()))


def plot_comparison(
    df: pd.DataFrame,
    output_path: Path,
    metrics: Sequence[tuple[str, str]] = METRICS_TO_PLOT,
    group_padding: float = 0.3,
) -> None:
    """
    Plot normalized metrics as grouped bar charts.

    Args:
        df: DataFrame with raw metrics (will be normalized internally)
        output_path: Path to save the plot
        metrics: Sequence of (metric_column, y_label) tuples
        group_padding: Fraction of group width for padding between groups
    """
    norm_df = normalize_df(df, BASELINE_NAME)
    if norm_df.empty:
        print("Cannot create plot: normalization failed")
        return

    # Get config order and display names
    config_names = [cfg[1]['name'] for cfg in CONFIGS_TO_COMPARE]
    display_names = {cfg[1]['name']: cfg[2] for cfg in CONFIGS_TO_COMPARE}

    # Filter to only configs that exist in data
    configs = [c for c in config_names if c in norm_df['config_name'].unique()]
    implementations = norm_df['impl'].unique()
    num_impls = len(implementations)
    num_configs = len(configs)

    # Calculate bar width
    bar_width = (1.0 - group_padding) / num_configs

    # Calculate offsets to center the group of bars
    offsets = np.linspace(
        -(num_configs - 1) * bar_width / 2,
        (num_configs - 1) * bar_width / 2,
        num_configs
    )

    fig, axes = plt.subplots(1, len(metrics), figsize=(5 * len(metrics), 5), sharey=False)
    if len(metrics) == 1:
        axes = [axes]

    x_positions = np.arange(num_impls + 1)  # +1 for Geomean

    for ax, (metric, ylabel) in zip(axes, metrics):
        if metric not in norm_df.columns:
            ax.text(0.5, 0.5, f'No data for {metric}', ha='center', va='center', transform=ax.transAxes)
            continue

        for config_name, offset in zip(configs, offsets):
            config_df = norm_df[norm_df['config_name'] == config_name]
            values = config_df.set_index('impl').reindex(implementations)[metric].values
            geo = _geom_mean(config_df[metric])
            values_with_geo = np.concatenate([values, [geo]])

            color = BAR_COLORS.get(config_name, '#333333')
            label = display_names.get(config_name, config_name)

            bars = ax.bar(
                x_positions + offset,
                values_with_geo,
                width=bar_width,
                label=label,
                color=color,
            )

            # Add value labels
            for bar, value in zip(bars, values_with_geo):
                if np.isnan(value):
                    label_text = "NaN"
                else:
                    label_text = f"{value:.2f}x"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    label_text,
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    rotation=0,
                )

        ax.axhline(1.0, color='black', linestyle='--', linewidth=1, alpha=0.7)
        ax.set_xticks(x_positions)
        ax.set_xticklabels([*implementations, 'Geomean'], rotation=30, ha='right', fontsize=9)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_ylim(bottom=0)
        ax.yaxis.grid(True, linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)
        ax.legend(loc='upper right', fontsize=8)

    fig.suptitle(f'DCC3 Multiplication Method Comparison (sparsity={SPARSITY})', fontsize=13, fontweight='bold')
    fig.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved plot: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Create output directory
    timestamp = dt.now().strftime("%d%b%y-%H.%M.%S")
    folder_name = f"{RUN_PREFIX}{timestamp}" if RUN_PREFIX else timestamp
    output_dir = Path("results") / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Run all configurations
    combined_df = run_all_configs()

    if combined_df.empty:
        print("No results generated!")
        return

    # Save raw results
    combined_df.to_csv(output_dir / 'all_results.csv', index=False)
    print(f"\nSaved: all_results.csv")

    # Save normalized results
    norm_df = normalize_df(combined_df, BASELINE_NAME)
    if not norm_df.empty:
        norm_df.to_csv(output_dir / 'normalized_results.csv', index=False)
        print(f"Saved: normalized_results.csv")

    # Generate plot
    plot_comparison(combined_df, output_dir / 'comparison.png')

    print(f"\nAll outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()

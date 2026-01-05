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
import runs.benchmarks.kratos_tiny as tiny
import runs.benchmarks.kratos_mini as mini
import util.derived_metrics as derived_metrics

# Architecture imports
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.four_bit_adder import (
    DCC2ArchFactory,
    DCC3ExpArchFactory,
)
from structure.run import run_parallel_arch_experiments

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

# =============================================================================
# MULTIPLICATION MODES
# =============================================================================
# Each mode maps to its experiment parameter overrides.
# Priority when determining method: ternary_adder_dp > soft_multiplier_adders > compressor_tree_type

MULT_MODES = {
    'cascade': {
        'soft_multiplier_adders': True,
    },
    'tdp': {
        'ternary_adder_dp': True,
    },
    'wallace': {
        'soft_multiplier_adders': False,
        'compressor_tree_type': 'wallace',
    },
    'wallace_ternary': {
        'soft_multiplier_adders': False,
        'compressor_tree_type': 'wallace_ternary',
    },
    # 'wallace_ternary_exp': {
    #     'soft_multiplier_adders': False,
    #     'compressor_tree_type': 'wallace_ternary_exp',
    # },
}

# Display names for each mode (for plotting)
MODE_DISPLAY_NAMES = {
    'cascade': 'dcc3 (cascade)',
    'tdp': 'dcc3 (tdp)',
    'wallace': 'dcc3 (wallace)',
    'wallace_ternary': 'dcc3 (wt)',
}

# Modes to run (subset of MULT_MODES keys)
MODES_TO_RUN = ['cascade', 'tdp', 'wallace', 'wallace_ternary']

# Architecture class for all modes (can be overridden per-mode if needed)
DEFAULT_ARCH_CLASS = DCC3ExpArchFactory

# Build CONFIGS_TO_COMPARE from MULT_MODES for backward compatibility
CONFIGS_TO_COMPARE = [
    (DEFAULT_ARCH_CLASS, {'name': f'dcc3_{mode}', **MULT_MODES[mode]}, MODE_DISPLAY_NAMES[mode])
    for mode in MODES_TO_RUN
]

# Baseline for normalization (must match a config name from CONFIGS_TO_COMPARE)
BASELINE_NAME = 'dcc3_cascade'

# Run configuration
NUM_PARALLEL_TASKS = 7      # Parallelism within each mode (designs per mode)
NUM_MODE_WORKERS = 4        # Parallelism between modes (set > 1 for concurrent modes)
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
    'dcc3_cascade': '#2ca02c',
    'dcc3_wallace': '#d62728',
    'dcc3_wallace_ternary': '#1f77b4',
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
    (Conv1dFuDesign(), tiny.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), tiny.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    (GemmTRpDesign(), tiny.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), kratos.get_gemms_params(BASE_PARAMS)),
]

FILTER_PARAMS = ['per_fle_area', 'data_width', 'sparsity', 'compressor_tree_type', 'soft_multiplier_adders', 'ternary_adder_dp']
FILTER_RESULTS = ['fmax', 'cpd', 'twl', 'chain_molecules', 'simple_chain_molecules', 'total_chain_molecules', 'chain_ratio', 'arithmetic_1chain', 'arithmetic_2chains']
FILTER_BLOCKS = ['clb', 'fle', 'fle1', 'fle2', 'lut5', 'lut6', 'adder', 'ble5', 'ble6', 'flut5', 'arithmetic']

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

    # Calculate FLE mode breakdown (scaled from BLE5 modes)
    # NOTE: Counter-intuitive naming in VPR!
    # arithmetic_1chain = ONE ternary chain (2 adders connected as a ternary unit)
    # arithmetic_2chains = TWO independent/simple chains (2 separate adder chains)
    # fle_lut = flut5 * (fle / ble5) + ble6 (for LUT6 mode)
    df['fle_chain'] = 0.0       # Ternary chains (arithmetic_1chain)
    df['fle_simple_chain'] = 0.0  # Simple/independent chains (arithmetic_2chains)
    df['fle_lut'] = 0.0
    if 'fle' in df.columns and 'ble5' in df.columns and 'flut5' in df.columns:
        mask = (df['ble5'] > 0)
        scale = df.loc[mask, 'fle'] / df.loc[mask, 'ble5']

        # Split arithmetic into chain vs simple_chain (note: naming is inverted!)
        if 'arithmetic_1chain' in df.columns:
            df.loc[mask, 'fle_chain'] = df.loc[mask, 'arithmetic_1chain'].fillna(0) * scale
        if 'arithmetic_2chains' in df.columns:
            df.loc[mask, 'fle_simple_chain'] = df.loc[mask, 'arithmetic_2chains'].fillna(0) * scale

        df.loc[mask, 'fle_lut'] = df.loc[mask, 'flut5'] * scale
        # Add ble6 to LUT count if available (LUT6 mode uses ble6)
        if 'ble6' in df.columns:
            df.loc[mask, 'fle_lut'] = df.loc[mask, 'fle_lut'] + df.loc[mask, 'ble6'].fillna(0)

    return df, ['mult_method', 'area_fle', 'adp_fle', 'fle_chain', 'fle_simple_chain', 'fle_lut']

# =============================================================================
# EXPERIMENT RUNNING
# =============================================================================

# Keys from arch_config that should be applied to experiment parameters
MODE_OVERRIDE_KEYS = ['compressor_tree_type', 'soft_multiplier_adders', 'ternary_adder_dp', 'allow_skipping']


def apply_overrides(design_list: list, arch_config: dict) -> list:
    """Apply architecture-specific overrides to design list parameters.

    Copies MODE_OVERRIDE_KEYS from arch_config into each design's experiment params.
    """
    overridden_list = []
    for design, params in design_list:
        new_params = copy.deepcopy(params)
        for key in MODE_OVERRIDE_KEYS:
            if key in arch_config:
                new_params[keys.KEY_EXP][key] = arch_config[key]
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
    """Run all configurations and return combined DataFrame.

    Uses run_parallel_arch_experiments when NUM_MODE_WORKERS > 1 to enable
    concurrent execution across different multiplication modes.
    """
    if NUM_MODE_WORKERS > 1:
        # Build config list for parallel execution: (task_name, arch_class, arch_config)
        arch_configs = [
            (arch_config['name'], arch_class, arch_config)
            for arch_class, arch_config, _ in CONFIGS_TO_COMPARE
        ]

        # Run all modes in parallel
        results = run_parallel_arch_experiments(
            arch_configs=arch_configs,
            runner_fn=run_single_config,
            num_workers=NUM_MODE_WORKERS,
            verbose=VERBOSE,
        )

        # Combine results
        all_dfs = [df for df in results.values() if df is not None]
    else:
        # Sequential execution (original behavior)
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


def plot_detailed_metrics(
    df: pd.DataFrame,
    output_path: Path,
    group_padding: float = 0.3,
) -> None:
    """
    Plot detailed metrics including stacked adder breakdown, ALMs, CPD, and ADP.

    Creates a 4-panel figure showing:
    1. Adders used (stacked: simple_chains vs chains)
    2. ALMs used (fle)
    3. Critical path delay
    4. Area-delay product

    Args:
        df: DataFrame with raw metrics (not normalized)
        output_path: Path to save the plot
        group_padding: Fraction of group width for padding between groups
    """
    # Get config order and display names
    config_names = [cfg[1]['name'] for cfg in CONFIGS_TO_COMPARE]
    display_names = {cfg[1]['name']: cfg[2] for cfg in CONFIGS_TO_COMPARE}

    # Filter to only configs that exist in data
    configs = [c for c in config_names if c in df['config_name'].unique()]
    implementations = df['impl'].unique()
    num_impls = len(implementations)
    num_configs = len(configs)

    if num_configs == 0:
        print("No configurations found in data for detailed metrics plot")
        return

    # Calculate bar width
    bar_width = (1.0 - group_padding) / num_configs

    # Calculate offsets to center the group of bars
    offsets = np.linspace(
        -(num_configs - 1) * bar_width / 2,
        (num_configs - 1) * bar_width / 2,
        num_configs
    )

    # Define the 4 metrics to plot
    metrics_info = [
        ('adder_stacked', 'Adder Chains'),
        ('fle_stacked', 'ALMs (FLE Mode)'),
        ('cpd', 'Critical Path Delay (ns)'),
        ('adp_fle', 'Area-Delay Product'),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(20, 5), sharey=False)

    x_positions = np.arange(num_impls + 1)  # +1 for Geomean

    # Import Patch once at the top of the loop section
    from matplotlib.patches import Patch

    def lighten_color(color, amount=0.5):
        """Lighten a color by blending it with white. amount=0 is original, amount=1 is white."""
        import matplotlib.colors as mcolors
        rgb = mcolors.to_rgb(color)
        # Blend with white
        lightened = tuple(c + (1.0 - c) * amount for c in rgb)
        return lightened

    for ax, (metric, ylabel) in zip(axes, metrics_info):
        if metric == 'adder_stacked':
            # Special handling for stacked bar chart (chains vs simple_chains)
            for config_name, offset in zip(configs, offsets):
                config_df = df[df['config_name'] == config_name]

                # Get chain and simple_chain values per implementation
                chain_vals = []
                simple_chain_vals = []
                for impl in implementations:
                    impl_row = config_df[config_df['impl'] == impl]
                    if impl_row.empty:
                        chain_vals.append(0)
                        simple_chain_vals.append(0)
                    else:
                        chain_vals.append(impl_row['chain_molecules'].values[0] if 'chain_molecules' in impl_row.columns else 0)
                        simple_chain_vals.append(impl_row['simple_chain_molecules'].values[0] if 'simple_chain_molecules' in impl_row.columns else 0)

                # Calculate geomean for each type
                chain_arr = np.array(chain_vals, dtype=float)
                simple_chain_arr = np.array(simple_chain_vals, dtype=float)

                # Geomean (handle zeros)
                chain_geo = _geom_mean(pd.Series(chain_arr[chain_arr > 0])) if np.any(chain_arr > 0) else 0
                simple_chain_geo = _geom_mean(pd.Series(simple_chain_arr[simple_chain_arr > 0])) if np.any(simple_chain_arr > 0) else 0

                chain_vals_with_geo = np.concatenate([chain_arr, [chain_geo]])
                simple_chain_vals_with_geo = np.concatenate([simple_chain_arr, [simple_chain_geo]])

                color = BAR_COLORS.get(config_name, '#333333')
                light_color = lighten_color(color, 0.6)

                # Draw stacked bars: chains on bottom (full color), simple_chains on top (lighter)
                ax.bar(
                    x_positions + offset,
                    chain_vals_with_geo,
                    width=bar_width,
                    color=color,
                    edgecolor='black',
                    linewidth=0.5,
                )
                ax.bar(
                    x_positions + offset,
                    simple_chain_vals_with_geo,
                    width=bar_width,
                    bottom=chain_vals_with_geo,
                    color=light_color,
                    edgecolor='black',
                    linewidth=0.5,
                )

            # Add a custom legend for stacked explanation
            legend_elements = [
                Patch(facecolor='gray', edgecolor='black', linewidth=0.5, label='Chains (ternary)'),
                Patch(facecolor=lighten_color('gray', 0.6), edgecolor='black', linewidth=0.5, label='Simple chains'),
            ]
            ax.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, -0.15), fontsize=8, ncol=2)

        elif metric == 'fle_stacked':
            # Stacked bar chart for FLE mode breakdown (chain vs simple_chain vs LUT)
            for config_name, offset in zip(configs, offsets):
                config_df = df[df['config_name'] == config_name]

                # Get fle_chain, fle_simple_chain, and fle_lut values per implementation
                chain_vals = []
                simple_vals = []
                lut_vals = []
                for impl in implementations:
                    impl_row = config_df[config_df['impl'] == impl]
                    if impl_row.empty:
                        chain_vals.append(0)
                        simple_vals.append(0)
                        lut_vals.append(0)
                    else:
                        chain_vals.append(impl_row['fle_chain'].values[0] if 'fle_chain' in impl_row.columns and not pd.isna(impl_row['fle_chain'].values[0]) else 0)
                        simple_vals.append(impl_row['fle_simple_chain'].values[0] if 'fle_simple_chain' in impl_row.columns and not pd.isna(impl_row['fle_simple_chain'].values[0]) else 0)
                        lut_vals.append(impl_row['fle_lut'].values[0] if 'fle_lut' in impl_row.columns and not pd.isna(impl_row['fle_lut'].values[0]) else 0)

                # Calculate geomean for each type
                chain_arr = np.array(chain_vals, dtype=float)
                simple_arr = np.array(simple_vals, dtype=float)
                lut_arr = np.array(lut_vals, dtype=float)

                chain_geo = _geom_mean(pd.Series(chain_arr[chain_arr > 0])) if np.any(chain_arr > 0) else 0
                simple_geo = _geom_mean(pd.Series(simple_arr[simple_arr > 0])) if np.any(simple_arr > 0) else 0
                lut_geo = _geom_mean(pd.Series(lut_arr[lut_arr > 0])) if np.any(lut_arr > 0) else 0

                chain_with_geo = np.concatenate([chain_arr, [chain_geo]])
                simple_with_geo = np.concatenate([simple_arr, [simple_geo]])
                lut_with_geo = np.concatenate([lut_arr, [lut_geo]])

                color = BAR_COLORS.get(config_name, '#333333')
                medium_color = lighten_color(color, 0.4)
                light_color = lighten_color(color, 0.7)

                # Draw stacked bars: chain (bottom, full), simple_chain (middle, medium), lut (top, light)
                ax.bar(
                    x_positions + offset,
                    chain_with_geo,
                    width=bar_width,
                    color=color,
                    edgecolor='black',
                    linewidth=0.5,
                )
                ax.bar(
                    x_positions + offset,
                    simple_with_geo,
                    width=bar_width,
                    bottom=chain_with_geo,
                    color=medium_color,
                    edgecolor='black',
                    linewidth=0.5,
                )
                ax.bar(
                    x_positions + offset,
                    lut_with_geo,
                    width=bar_width,
                    bottom=chain_with_geo + simple_with_geo,
                    color=light_color,
                    edgecolor='black',
                    linewidth=0.5,
                )

            # Add a custom legend for stacked explanation
            legend_elements = [
                Patch(facecolor='gray', edgecolor='black', linewidth=0.5, label='Chain (ternary)'),
                Patch(facecolor=lighten_color('gray', 0.4), edgecolor='black', linewidth=0.5, label='Simple chain'),
                Patch(facecolor=lighten_color('gray', 0.7), edgecolor='black', linewidth=0.5, label='LUT'),
            ]
            ax.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, -0.15), fontsize=8, ncol=3)

        else:
            # Standard grouped bar chart for other metrics
            if metric not in df.columns:
                ax.text(0.5, 0.5, f'No data for {metric}', ha='center', va='center', transform=ax.transAxes)
                continue

            for config_name, offset in zip(configs, offsets):
                config_df = df[df['config_name'] == config_name]
                values = config_df.set_index('impl').reindex(implementations)[metric].values
                geo = _geom_mean(config_df[metric])
                values_with_geo = np.concatenate([values, [geo]])

                color = BAR_COLORS.get(config_name, '#333333')
                label = display_names.get(config_name, config_name)

                ax.bar(
                    x_positions + offset,
                    values_with_geo,
                    width=bar_width,
                    label=label,
                    color=color,
                    edgecolor='black',
                    linewidth=0.5,
                )

            ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), fontsize=8, ncol=2)

        ax.set_xticks(x_positions)
        ax.set_xticklabels([*implementations, 'Geomean'], rotation=30, ha='right', fontsize=9)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_ylim(bottom=0)
        ax.yaxis.grid(True, linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

    fig.suptitle(f'Detailed Metrics: Adder Chains, ALMs, CPD, ADP (sparsity={SPARSITY})', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.2)  # Make room for bottom legends
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved detailed metrics plot: {output_path}")


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

    # Generate plots
    plot_comparison(combined_df, output_dir / 'comparison.png')
    plot_detailed_metrics(combined_df, output_dir / 'detailed_metrics.png')

    print(f"\nAll outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Sweep tree_base parameter from 2 to 6 for multiple architectures.

Output: Separate PNG for each architecture, with tree_base values as grouped bars.
"""

import structure.consts.keys as keys
from runs.vtr_denoised_same_arch_raw import run_vtr_denoised_same_arch_raw
import runs.benchmarks.kratos_tiny as tiny
import util.derived_metrics as derived_metrics

# Architecture imports
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.four_bit_adder import (
    DCC1ArchFactory,
    DCC2ArchFactory,
    DCC3ArchFactory,
)
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.lut_skip_dcc3 import LUTSkipDCC3ArchFactory

# Design imports
from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_1d.pw import Conv1dPwDesign
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.gemmt.fu import GemmTFuDesign

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

# Architectures to sweep (arch_class, name, extra_config)
ARCHS_TO_RUN: list[tuple[Type, str, dict]] = [
    (BaseArchFactory, 'base', {
        'compressor_tree_type': 'wallace',
    }),
    (DCC2ArchFactory, 'dcc2', {
        'compressor_tree_type': 'wallace',
    }),
    (DCC3ArchFactory, 'dcc3', {
        'compressor_tree_type': 'wallace_ternary',
        'allow_skipping': True,
    }),
    # (LUTSkipArchFactory, 'dd5', {
    #     'compressor_tree_type': 'wallace',
    # }),
    # (LUTSkipDCC3ArchFactory, 'dcc3_dd5', {
    #     'compressor_tree_type': 'wallace_ternary',
    # }),
]

# Tree base values to sweep
TREE_BASE_VALUES = [2, 3, 4, 5, 6]

# Baseline tree_base for normalization (first value by default)
BASELINE_TREE_BASE = 2

# Sparsity to test
SPARSITY = 0.5

# Run configuration
NUM_PARALLEL_TASKS = 5
VERBOSE = False

# Metrics to plot (metric_key, y_label)
METRICS_TO_PLOT: Sequence[tuple[str, str]] = (
    ('area_fle', 'Area'),
    ('cpd', 'CPD'),
    ('adp_fle', 'ADP'),
)

# Bar colors for each tree_base value
BAR_COLORS = {
    2: '#1f77b4',
    3: '#ff7f0e',
    4: '#2ca02c',
    5: '#d62728',
    6: '#9467bd',
}

# =============================================================================
# PARAMETERS
# =============================================================================

def get_base_params() -> dict:
    """Get base parameters."""
    return {
        keys.KEY_EXP: {
            'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
            'allow_skipping': True,
            'adder_cin_global': False,
            'route_chan_width': 400,
            'target_ext_pin_util': '0.9,0.9',
            'compressor_tree_type': 'wallace_ternary',
            'soft_multiplier_adders': False,
            'ternary_adder_dp': False,
        },
        keys.KEY_ARCH: {
            'cin_mux_stride': 0,
        },
        keys.KEY_DESIGN: {
            'data_width': 6,
            'sparsity': SPARSITY,
        }
    }

# Designs to run
BASE_PARAMS = get_base_params()
DESIGN_LIST = [
    (Conv1dFuDesign(), tiny.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), tiny.get_conv_1d_pw_params(BASE_PARAMS)),
    (Conv2dFuDesign(), tiny.get_conv_2d_fu_params(BASE_PARAMS)),
    (GemmTFuDesign(), tiny.get_gemmt_fu_params(BASE_PARAMS)),
]

FILTER_PARAMS = ['per_fle_area', 'data_width', 'sparsity', 'compressor_tree_type', 'tree_base']
FILTER_RESULTS = ['fmax', 'cpd', 'twl']
FILTER_BLOCKS = ['clb', 'fle', 'fle1', 'fle2', 'lut5', 'lut6', 'adder']

# =============================================================================
# DERIVED METRICS
# =============================================================================

def add_derived_metrics(df: DataFrame) -> tuple[DataFrame, list[str]]:
    """Add derived metrics to the DataFrame."""
    df = derived_metrics.dcc1_gather_fle(df)
    df = derived_metrics.apply_area_fle(df)
    df = derived_metrics.apply_adp_fle(df)

    return df, ['area_fle', 'adp_fle']

# =============================================================================
# EXPERIMENT RUNNING
# =============================================================================

def build_design_list_for_arch(arch_config: dict) -> list:
    """
    Build a combined design list with all tree_base variations.
    This allows parallel execution of all tree_base values.
    """
    combined_list = []

    for tree_base in TREE_BASE_VALUES:
        for design, params in DESIGN_LIST:
            new_params = copy.deepcopy(params)
            # Apply tree_base
            new_params[keys.KEY_DESIGN]['tree_base'] = tree_base
            # Apply arch-specific overrides
            if 'compressor_tree_type' in arch_config:
                new_params[keys.KEY_EXP]['compressor_tree_type'] = arch_config['compressor_tree_type']
            if 'allow_skipping' in arch_config:
                new_params[keys.KEY_EXP]['allow_skipping'] = arch_config['allow_skipping']
            if 'soft_multiplier_adders' in arch_config:
                new_params[keys.KEY_EXP]['soft_multiplier_adders'] = arch_config['soft_multiplier_adders']
            if 'ternary_adder_dp' in arch_config:
                new_params[keys.KEY_EXP]['ternary_adder_dp'] = arch_config['ternary_adder_dp']
            combined_list.append((design, new_params))

    return combined_list


def run_all_tree_bases_for_arch(
    arch_class: Type,
    arch_name: str,
    arch_config: dict,
) -> pd.DataFrame:
    """Run all tree_base configurations for one architecture in parallel."""
    print(f"\n{'='*60}")
    print(f"Running: {arch_name} with tree_base={TREE_BASE_VALUES}")
    print(f"  Parallelism: {NUM_PARALLEL_TASKS} tasks")
    print(f"{'='*60}\n")

    # Build combined design list with all tree_base variations
    design_list = build_design_list_for_arch(arch_config)

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
        desc=f'{arch_name}_tree_base_sweep',
    )

    if df is not None:
        df.insert(0, 'arch', arch_name)

    return df if df is not None else pd.DataFrame()


# =============================================================================
# NORMALIZATION
# =============================================================================

def normalize_df(df: pd.DataFrame, baseline_tree_base: int) -> pd.DataFrame:
    """Normalize numeric columns against baseline tree_base, per implementation."""
    base_df = df[df['tree_base'] == baseline_tree_base].copy()
    if base_df.empty:
        print(f"Warning: Baseline tree_base={baseline_tree_base} not found!")
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
                'tree_base': row['tree_base'],
                'impl': row['impl'],
            }

            for col in df.columns:
                if col in ['tree_base', 'impl']:
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


def plot_tree_base_comparison(
    df: pd.DataFrame,
    output_path: Path,
    arch_name: str,
    metrics: Sequence[tuple[str, str]] = METRICS_TO_PLOT,
    normalize: bool = True,
    group_padding: float = 0.3,
) -> None:
    """
    Plot metrics as grouped bar charts.

    Args:
        df: DataFrame with raw metrics
        output_path: Path to save the plot
        arch_name: Architecture name for the title
        metrics: Sequence of (metric_column, y_label) tuples
        normalize: Whether to normalize against baseline
        group_padding: Fraction of group width for padding between groups
    """
    if normalize:
        plot_df = normalize_df(df, BASELINE_TREE_BASE)
        if plot_df.empty:
            print("Cannot create normalized plot: normalization failed")
            return
        suffix = " (Normalized)"
    else:
        plot_df = df.copy()
        suffix = ""

    tree_bases = sorted(plot_df['tree_base'].unique())
    implementations = plot_df['impl'].unique()
    num_impls = len(implementations)
    num_tree_bases = len(tree_bases)

    # Calculate bar width
    bar_width = (1.0 - group_padding) / num_tree_bases

    # Calculate offsets to center the group of bars
    offsets = np.linspace(
        -(num_tree_bases - 1) * bar_width / 2,
        (num_tree_bases - 1) * bar_width / 2,
        num_tree_bases
    )

    fig, axes = plt.subplots(1, len(metrics), figsize=(5 * len(metrics), 5), sharey=False)
    if len(metrics) == 1:
        axes = [axes]

    x_positions = np.arange(num_impls + 1)  # +1 for Geomean

    for ax, (metric, ylabel) in zip(axes, metrics):
        if metric not in plot_df.columns:
            ax.text(0.5, 0.5, f'No data for {metric}', ha='center', va='center', transform=ax.transAxes)
            continue

        for tree_base, offset in zip(tree_bases, offsets):
            tb_df = plot_df[plot_df['tree_base'] == tree_base]
            values = tb_df.set_index('impl').reindex(implementations)[metric].values
            geo = _geom_mean(tb_df[metric])
            values_with_geo = np.concatenate([values, [geo]])

            color = BAR_COLORS.get(tree_base, '#333333')
            label = f'tree_base={tree_base}'

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
                elif normalize:
                    label_text = f"{value:.2f}x"
                else:
                    label_text = f"{value:.1f}"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    label_text,
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    rotation=0,
                )

        if normalize:
            ax.axhline(1.0, color='black', linestyle='--', linewidth=1, alpha=0.7)
        ax.set_xticks(x_positions)
        ax.set_xticklabels([*implementations, 'Geomean'], rotation=30, ha='right', fontsize=9)
        ax.set_ylabel(ylabel + suffix, fontsize=11)
        ax.set_ylim(bottom=0)
        ax.yaxis.grid(True, linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)
        ax.legend(loc='upper right', fontsize=8)

    title = f'Tree Base Sweep on {arch_name} (sparsity={SPARSITY})'
    fig.suptitle(title, fontsize=13, fontweight='bold')
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
    output_dir = Path("results") / f"tree_base_sweep_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Store all results across architectures
    all_arch_results = []

    # Run for each architecture
    for arch_class, arch_name, arch_config in ARCHS_TO_RUN:
        print(f"\n{'#'*60}")
        print(f"# Architecture: {arch_name}")
        print(f"{'#'*60}")

        # Run all tree_base configurations for this architecture
        arch_df = run_all_tree_bases_for_arch(arch_class, arch_name, arch_config)

        if arch_df.empty:
            print(f"No results for {arch_name}, skipping...")
            continue

        all_arch_results.append(arch_df)

        # Save per-architecture CSV
        arch_df.to_csv(output_dir / f'{arch_name}_results.csv', index=False)
        print(f"Saved: {arch_name}_results.csv")

        # Save per-architecture normalized CSV
        norm_df = normalize_df(arch_df, BASELINE_TREE_BASE)
        if not norm_df.empty:
            norm_df.to_csv(output_dir / f'{arch_name}_normalized.csv', index=False)
            print(f"Saved: {arch_name}_normalized.csv")

        # Generate per-architecture plots
        plot_tree_base_comparison(
            arch_df,
            output_dir / f'{arch_name}_tree_base_normalized.png',
            arch_name,
            normalize=True
        )
        plot_tree_base_comparison(
            arch_df,
            output_dir / f'{arch_name}_tree_base_raw.png',
            arch_name,
            normalize=False
        )

    # Save combined results across all architectures
    if all_arch_results:
        combined_df = pd.concat(all_arch_results, ignore_index=True)
        combined_df.to_csv(output_dir / 'all_results.csv', index=False)
        print(f"\nSaved: all_results.csv (combined)")

    print(f"\nAll outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()

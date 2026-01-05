#!/usr/bin/env python3
"""
Run VTR standard benchmarks across multiple architectures, producing:
1. Augmented all_results.csv with 'arch' column
2. Normalized results CSV (normalized against baseline architecture)
3. Plot PNGs for key metrics

Configuration:
- ARCH_CONFIG: Dictionary mapping ArchFactory classes to their configs
- ARCHS_TO_RUN: List of architectures to run
- BASELINE_ARCH_KEY: Which arch label to use as normalization baseline
"""

import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH

from runs.vtr_denoised_same_arch_raw import run_vtr_denoised_same_arch_raw
from structure.run import run_parallel_arch_experiments

import runs.benchmarks.vtr_full_benchmarks as vtr_bm

import util.derived_metrics as derived_metrics

# Architecture imports
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.four_bit_adder import (
    DCC1ArchFactory,
    DCC2ArchFactory,
    DCC3ArchFactory,
    DCC3ExpArchFactory,
)
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.lut_skip_dcc3 import (
  LUTSkipDCC3ArchFactory,
  LUTSkipDCC3ExpArchFactory,
  AdderSkipDCC3ArchFactory
)

# Design imports
from impl.design.vtr_full_benchmarks.loader import VtrBenchmarkLoaderDesign

import copy
import numpy as np
import os
import os.path as path
from pathlib import Path
from datetime import datetime as dt
from pandas import DataFrame
import pandas as pd
from typing import Type, Iterable, Sequence
import matplotlib.pyplot as plt

import matplotlib
matplotlib.use("Agg")

# =============================================================================
# CONFIGURATION
# =============================================================================

ARCH_CONFIG: dict[Type, dict] = {
    BaseArchFactory: {
        "name": "base",
        "compressor_tree_type": "wallace",
        "tree_base": 2,
    },
    LUTSkipArchFactory: {
        "name": "dd5",
        "compressor_tree_type": "wallace",
        "tree_base": 2,
    },
    DCC1ArchFactory: {
        "name": "dcc1",
        "compressor_tree_type": "wallace",
        "tree_base": 2,
    },
    DCC2ArchFactory: {
        "name": "dcc2",
        "compressor_tree_type": "wallace",
        "tree_base": 2,
    },
    DCC3ArchFactory: {
        "name": "dcc3",
        "compressor_tree_type": "wallace_ternary",
        "tree_base": 3,
        "allow_skipping": True,
    },
    DCC3ExpArchFactory: {
        "name": "dcc3_exp",
        "compressor_tree_type": "wallace_ternary",
        "tree_base": 3,
        "allow_skipping": True,
    },
    LUTSkipDCC3ArchFactory: {
        "name": "dcc3_dd5",
        "compressor_tree_type": "wallace_ternary",
        "tree_base": 3,
        "allow_skipping": True,
    },
    LUTSkipDCC3ExpArchFactory: {
        "name": "dcc3_dd5_exp",
        "compressor_tree_type": "wallace_ternary",
        "tree_base": 3,
        "allow_skipping": True,
    },
    AdderSkipDCC3ArchFactory: {
        "name": "dcc3_skip_add",
        "compressor_tree_type": "wallace_ternary",
        "tree_base": 3,
        "allow_skipping": False,
    },
}

# Helper to get arch name from config
def get_arch_name(arch_class: Type) -> str:
    return ARCH_CONFIG[arch_class]["name"]

# Which architecture to use as baseline for normalization
BASELINE_ARCH_KEY: str = "base"

# Base parameters for all experiments
BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': True,
        'avoid_mult': False,
        'adder_cin_global': False,
        'soft_multiplier_adders': False,
        'route_chan_width': 400,
        'compressor_tree_type': 'wallace',
        'ternary_adder_dp': False,
        'parser': 'default',  # avoid bug
    },
    keys.KEY_ARCH: {
        'cin_mux_stride': 0,
    },
    keys.KEY_DESIGN: {
        'sparsity': 0.5,
        'data_width': 6,
        'tree_base': 2,
    }
}

# Designs to run (VTR Standard Benchmarks)
DESIGN_LIST = [
    (VtrBenchmarkLoaderDesign(), vtr_bm.get_all_vtr_bm_params(BASE_PARAMS)),
]

# Which architectures to run (subset of ARCH_CONFIG keys)
ARCHS_TO_RUN: list[Type] = [
    # BaseArchFactory,
    # LUTSkipArchFactory,
    # DCC1ArchFactory,
    # DCC2ArchFactory,
    # DCC3ExpArchFactory,
    # LUTSkipDCC3ExpArchFactory,
    # LUTSkipDCC3ArchFactory,
    AdderSkipDCC3ArchFactory,
]

# Metrics to plot
METRICS_TO_PLOT = (
    ("area_fle", "Area (Normalized)"),
    ("cpd", "Critical Path Delay (Normalized)"),
    ("adp_fle", "Area-Delay Product (Normalized)"),
)

# Filtering parameters
# Note: 'impl' is the individual benchmark name (e.g., 'sha', 'mcml')
FILTER_PARAMS = ['impl', 'per_fle_area', 'data_width', 'sparsity', 'compressor_tree_type', 'soft_multiplier_adders', 'ternary_adder_dp']
FILTER_RESULTS = [
    'fmax', 'cpd', 'twl',
    'concurrent_lut5s', 'concurrent_lut6s',
]
FILTER_BLOCKS = ['clb', 'fle', 'fle1', 'fle2', 'lut5', 'lut6', 'adder']

# Runner settings
NUM_PARALLEL_TASKS = 60      # Parallelism within each architecture (designs per arch)
NUM_ARCH_WORKERS = 1        # Parallelism across architectures (set > 1 for concurrent arch runs)
VERBOSE = True

# Results folder prefix
RUN_PREFIX = 'vtr-'

# =============================================================================
# DERIVED METRICS
# =============================================================================

def add_derived_metrics(df: DataFrame) -> tuple[DataFrame, list[str]]:
    """Add derived metrics to the DataFrame."""
    # Add mult_method column based on flags
    def get_mult_method(row):
        if row.get('ternary_adder_dp', False):
            return 'tdp'
        elif row.get('soft_multiplier_adders', False):
            return 'sma'
        else:
            return row.get('compressor_tree_type', 'wallace')
    df['mult_method'] = df.apply(get_mult_method, axis=1)

    # Gather fle1 + fle2 into fle (for dcc1 architecture)
    df = derived_metrics.dcc1_gather_fle(df)

    df = derived_metrics.apply_adder_avg_util(df)

    # 5-LUT measurements
    df = derived_metrics.apply_lut5_to_adder_ratio(df)
    df = derived_metrics.apply_lut5_concurrency(df)

    # 6-LUT measurements
    df = derived_metrics.apply_lut6_to_adder_ratio(df)
    df = derived_metrics.apply_lut6_concurrency(df)

    # 5/6-LUT measurements
    df = derived_metrics.apply_lut56_to_adder_ratio(df)
    df = derived_metrics.apply_lut56_concurrency(df)

    # Area calculations
    df = derived_metrics.apply_area_fle(df)

    # ADP
    df = derived_metrics.apply_adp_fle(df)

    return df, [
        'mult_method',
        'adder_avg_util',
        'lut5/adder',
        'lut5_concurrency',
        'lut6/adder',
        'lut6_concurrency',
        'lut56/adder',
        'lut56_concurrency',
        'area_fle',
        'adp_fle',
    ]

# =============================================================================
# NORMALIZATION
# =============================================================================

DEFAULT_KEY_PRIORITY: Sequence[str] = (
    "impl",
    "data_width",
    "sparsity",
)
COPIED_COLUMNS: Sequence[str] = ("arch", "mult_method")


def is_numeric_series(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def resolve_keys(
    base_df: pd.DataFrame,
    new_df: pd.DataFrame,
    requested_keys: Iterable[str] | None = None,
) -> list[str]:
    if requested_keys:
        requested_keys = list(requested_keys)
        missing = [
            key for key in requested_keys
            if key not in base_df.columns or key not in new_df.columns
        ]
        if missing:
            raise KeyError(f"Requested key(s) not in both CSVs: {', '.join(missing)}")
        return requested_keys

    keys = [
        key for key in DEFAULT_KEY_PRIORITY
        if key in base_df.columns and key in new_df.columns
    ]
    if not keys:
        raise KeyError("No shared key columns found between baseline and new CSV")
    return keys


def normalize_dataframe(
    base_df: pd.DataFrame,
    new_df: pd.DataFrame,
    join_keys: Sequence[str],
) -> pd.DataFrame:
    """Normalize new_df metrics against base_df."""
    join_keys = list(join_keys)

    for key in join_keys:
        if key not in base_df.columns:
            raise KeyError(f"Key '{key}' not found in baseline CSV")
        if key not in new_df.columns:
            raise KeyError(f"Key '{key}' not found in new CSV")

    if base_df.duplicated(subset=join_keys).any():
        raise ValueError(f"Baseline has duplicate rows for join keys: {', '.join(join_keys)}")

    # Drop copied columns from baseline
    base_for_join = base_df.drop(
        columns=[col for col in COPIED_COLUMNS if col not in join_keys],
        errors="ignore",
    )

    common_cols = [
        col for col in base_for_join.columns.intersection(new_df.columns)
        if col not in join_keys and col not in COPIED_COLUMNS
    ]
    numeric_cols = [
        col for col in common_cols
        if is_numeric_series(base_for_join[col]) and is_numeric_series(new_df[col])
    ]

    merged = new_df.merge(
        base_for_join,
        on=list(join_keys),
        how="left",
        suffixes=("_new", "_base"),
        indicator=True,
    )
    unmatched = merged["_merge"] != "both"
    if unmatched.any():
        missing_rows = merged.loc[unmatched, join_keys]
        print(
            f"  Note: {unmatched.sum()} rows have no baseline match (will show NaN for normalized metrics). "
            f"First few:\n{missing_rows.head().to_string(index=False)}"
        )
    merged = merged.drop(columns="_merge")

    result = merged[list(join_keys)].copy()
    for col in COPIED_COLUMNS:
        if col in result.columns:
            continue
        source_col = f"{col}_new"
        if source_col in merged.columns:
            result[col] = merged[source_col]
        elif col in merged.columns:
            result[col] = merged[col]
        elif col in new_df.columns:
            result[col] = new_df[col]

    for col in numeric_cols:
        new_col = f"{col}_new"
        base_col = f"{col}_base"
        if new_col not in merged.columns or base_col not in merged.columns:
            continue
        denom = merged[base_col].replace({0: np.nan})
        result[col] = merged[new_col] / denom

    lead_columns = list(dict.fromkeys(
        [col for col in COPIED_COLUMNS if col in result.columns] + list(join_keys)
    ))
    ordered_columns = lead_columns + [col for col in result.columns if col not in lead_columns]
    result = result[ordered_columns]
    return result


def normalize_all_against_baseline(
    combined_df: pd.DataFrame,
    baseline_arch: str,
) -> pd.DataFrame:
    """Normalize all architectures against the baseline architecture."""
    base_df = combined_df[combined_df["arch"] == baseline_arch].copy()

    results = []
    for arch in combined_df["arch"].unique():
        if arch == baseline_arch:
            continue
        new_df = combined_df[combined_df["arch"] == arch].copy()
        join_keys = resolve_keys(base_df, new_df)
        normalized = normalize_dataframe(base_df, new_df, join_keys)
        results.append(normalized)

    if not results:
        return pd.DataFrame()

    combined = pd.concat(results, ignore_index=True)
    combined = combined.sort_values(["impl"], kind="mergesort").reset_index(drop=True)
    return combined

# =============================================================================
# PLOTTING
# =============================================================================

BAR_COLORS = {
    "base": "#808080",
    "dd5": "#B85353",
    "dcc1": "#569EE3",
    "dcc2": "#3373B0",
    "dcc3": "#85CC7E",
    "dcc3_dd5": "#E3D154",
    "dcc3_skip_add": "#A89D44",
    "dcc3_exp": "#85CC7E",
}


def _geom_mean(series: pd.Series) -> float:
    """Geometric mean of positive, non-NaN values."""
    vals = series.dropna().astype(float)
    vals = vals[vals > 0]
    if vals.empty:
        return float("nan")
    return float(np.exp(np.log(vals).mean()))


def plot_normalized_metrics(
    df: pd.DataFrame,
    output_path: Path,
    metrics: Sequence[tuple[str, str]] = METRICS_TO_PLOT,
    group_padding: float = 0.3,
) -> None:
    """Plot normalized metrics as grouped bar charts.

    Args:
        df: DataFrame with normalized metrics
        output_path: Path to save the plot
        metrics: Sequence of (metric_column, y_label) tuples
        group_padding: Fraction of group width to use as padding between groups (0.0-0.5)
    """
    arches = [a for a in df["arch"].unique() if a in BAR_COLORS]
    implementations = df["impl"].unique()
    num_impls = len(implementations)
    num_arches = len(arches)

    # Calculate bar width dynamically:
    # Total group width is 1.0 (distance between x_positions)
    # We want: num_arches * bar_width + padding = 1.0
    # So: bar_width = (1.0 - padding) / num_arches
    bar_width = (1.0 - group_padding) / num_arches

    # Calculate offsets to center the group of bars at each x position
    offsets = np.linspace(
        -(num_arches - 1) * bar_width / 2,
        (num_arches - 1) * bar_width / 2,
        num_arches
    )

    num_plots = len(metrics) + 1  # +1 for summary plot
    fig, axes = plt.subplots(num_plots, 1, figsize=(12, 4 * num_plots), sharey=False)
    if num_plots == 1:
        axes = [axes]

    x_positions = np.arange(num_impls + 1)  # +1 for Geomean

    for ax, (metric, ylabel) in zip(axes, metrics):
        max_val = 0
        for arch, offset in zip(arches, offsets):
            arch_df = df[df["arch"] == arch]
            values = arch_df.set_index("impl").reindex(implementations)[metric].values
            geo = _geom_mean(arch_df[metric])
            values_with_geo = np.concatenate([values, [geo]])

            # Track max value for ylim
            valid_values = [v for v in values_with_geo if not np.isnan(v)]
            if valid_values:
                max_val = max(max_val, max(valid_values))

            color = BAR_COLORS.get(arch, None)
            bars = ax.bar(
                x_positions + offset,
                values_with_geo,
                width=bar_width,
                label=arch,
                color=color,
                edgecolor='black',
                linewidth=0.8,
            )

            for bar, value in zip(bars, values_with_geo):
                if np.isnan(value):
                    label = "NaN"
                else:
                    label = f"{value:.2f}"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01,
                    label,
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    rotation=90,
                )

        ax.axhline(1.0, color="black", linestyle="--", linewidth=1, alpha=0.7)
        ax.grid(axis='y', linestyle='-', alpha=0.3, color='gray')
        ax.set_axisbelow(True)
        ax.set_xticks(x_positions)
        ax.set_xticklabels([*implementations, "Geomean"], rotation=30, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0, top=max_val * 1.15)  # Add 15% headroom for text labels

    # Summary plot: geomean of each metric grouped by architecture
    summary_ax = axes[-1]
    summary_metrics = [
        ("area_fle", "Area", "#f5a19c"),
        ("cpd", "Delay", "#96bbf5"),
        ("adp_fle", "ADP", "#8ccd8c"),
    ]
    num_summary_metrics = len(summary_metrics)
    summary_bar_width = bar_width  # Use same bar width as main plots
    summary_offsets = np.linspace(
        -(num_summary_metrics - 1) * summary_bar_width / 2,
        (num_summary_metrics - 1) * summary_bar_width / 2,
        num_summary_metrics
    )
    arch_x_positions = np.arange(num_arches)

    max_val = 0
    for (metric_col, metric_label, metric_color), offset in zip(summary_metrics, summary_offsets):
        geomeans = []
        for arch in arches:
            arch_df = df[df["arch"] == arch]
            geo = _geom_mean(arch_df[metric_col])
            geomeans.append(geo)
            if not np.isnan(geo):
                max_val = max(max_val, geo)

        bars = summary_ax.bar(
            arch_x_positions + offset,
            geomeans,
            width=summary_bar_width,
            label=metric_label,
            color=metric_color,
            edgecolor='black',
            linewidth=0.8,
        )

        for bar, value in zip(bars, geomeans):
            if np.isnan(value):
                label = "NaN"
            else:
                label = f"{value:.2f}"
            summary_ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                label,
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=90,
            )

    summary_ax.axhline(1.0, color="black", linestyle="--", linewidth=1, alpha=0.7)
    summary_ax.grid(axis='y', linestyle='-', alpha=0.3, color='gray')
    summary_ax.set_axisbelow(True)
    summary_ax.set_xticks(arch_x_positions)
    summary_ax.set_xticklabels(arches, rotation=30, ha="right")
    summary_ax.set_ylabel("Normalized Value")
    summary_ax.set_ylim(bottom=0, top=max_val * 1.15)
    summary_ax.legend(loc='upper right')

    # Add shared legend for the first three plots above the summary plot
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=len(arches), bbox_to_anchor=(0.5, 1 / num_plots + 0.02), fontsize=8)

    fig.tight_layout(rect=[0, 0, 1, 1])
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved plot: {output_path}")

# =============================================================================
# MAIN
# =============================================================================

def apply_arch_overrides(design_list: list, arch_config: dict) -> list:
    """Apply per-architecture overrides to the design list parameters."""
    overridden_list = []
    for design, params in design_list:
        # Deep copy params to avoid mutating the original
        new_params = copy.deepcopy(params)

        # Apply experiment overrides from arch_config
        if 'allow_skipping' in arch_config:
            new_params[keys.KEY_EXP]['allow_skipping'] = arch_config['allow_skipping']
        if 'compressor_tree_type' in arch_config:
            new_params[keys.KEY_EXP]['compressor_tree_type'] = arch_config['compressor_tree_type']
        if 'soft_multiplier_adders' in arch_config:
            new_params[keys.KEY_EXP]['soft_multiplier_adders'] = arch_config['soft_multiplier_adders']
        if 'ternary_adder_dp' in arch_config:
            new_params[keys.KEY_EXP]['ternary_adder_dp'] = arch_config['ternary_adder_dp']

        # Apply design overrides from arch_config
        if 'tree_base' in arch_config:
            new_params[keys.KEY_DESIGN]['tree_base'] = arch_config['tree_base']

        overridden_list.append((design, new_params))
    return overridden_list


def run_single_arch(arch_class: Type, arch_config: dict) -> pd.DataFrame | None:
    """Run all designs on a single architecture and return DataFrame with arch column."""
    arch_name = arch_config["name"]

    print(f"\n{'='*60}")
    print(f"Running architecture: {arch_name} ({arch_class.__name__})")
    print(f"  compressor_tree_type: {arch_config.get('compressor_tree_type', 'default')}")
    print(f"  allow_skipping: {arch_config.get('allow_skipping', 'default')}")
    print(f"  soft_multiplier_adders: {arch_config.get('soft_multiplier_adders', 'default')}")
    print(f"{'='*60}\n")

    # Apply per-architecture overrides to design parameters
    design_list = apply_arch_overrides(DESIGN_LIST, arch_config)

    df = run_vtr_denoised_same_arch_raw(
        arch=arch_class,
        design_list=design_list,
        filter_params=FILTER_PARAMS,
        filter_results=FILTER_RESULTS.copy(),
        filter_blocks=FILTER_BLOCKS,
        df_processing_fn=add_derived_metrics,
        verbose=VERBOSE,
        # seeds=(1239,),
        num_parallel_tasks=NUM_PARALLEL_TASKS,
        save_to_folder=False,
        desc=f'{arch_name} architecture run',
    )

    if df is not None:
        df.insert(0, 'arch', arch_name)

    return df


def normalize_single_arch(
    base_df: pd.DataFrame,
    arch_df: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize a single architecture's results against the baseline."""
    join_keys = resolve_keys(base_df, arch_df)
    return normalize_dataframe(base_df, arch_df, join_keys)


def plot_single_arch_metrics(
    normalized_df: pd.DataFrame,
    arch_name: str,
    output_path: Path,
    metrics: Sequence[tuple[str, str]] = METRICS_TO_PLOT,
) -> None:
    """Plot normalized metrics for a single architecture as a bar chart.

    Args:
        normalized_df: DataFrame with normalized metrics for a single architecture
        arch_name: Name of the architecture being plotted
        output_path: Path to save the plot
        metrics: Sequence of (metric_column, y_label) tuples
    """
    implementations = normalized_df["impl"].unique()
    num_impls = len(implementations)

    num_plots = len(metrics) + 1  # +1 for summary plot
    fig, axes = plt.subplots(num_plots, 1, figsize=(12, 4 * num_plots), sharey=False)
    if num_plots == 1:
        axes = [axes]

    x_positions = np.arange(num_impls + 1)  # +1 for Geomean
    bar_width = 0.6

    color = BAR_COLORS.get(arch_name, "#1f77b4")

    for ax, (metric, ylabel) in zip(axes, metrics):
        values = normalized_df.set_index("impl").reindex(implementations)[metric].values
        geo = _geom_mean(normalized_df[metric])
        values_with_geo = np.concatenate([values, [geo]])

        # Track max value for ylim
        valid_values = [v for v in values_with_geo if not np.isnan(v)]
        max_val = max(valid_values) if valid_values else 1.0

        bars = ax.bar(
            x_positions,
            values_with_geo,
            width=bar_width,
            color=color,
            label=arch_name,
            edgecolor='black',
            linewidth=0.8,
        )

        for bar, value in zip(bars, values_with_geo):
            if np.isnan(value):
                label = "NaN"
            else:
                label = f"{value:.2f}"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                label,
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=90,
            )

        ax.axhline(1.0, color="black", linestyle="--", linewidth=1, alpha=0.7)
        ax.grid(axis='y', linestyle='-', alpha=0.3, color='gray')
        ax.set_axisbelow(True)
        ax.set_xticks(x_positions)
        ax.set_xticklabels([*implementations, "Geomean"], rotation=30, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0, top=max_val * 1.15)

    # Summary plot: geomean of each metric for this architecture
    summary_ax = axes[-1]
    summary_metrics = [
        ("area_fle", "Area", "#f5a19c"),
        ("cpd", "Delay", "#96bbf5"),
        ("adp_fle", "ADP", "#8ccd8c"),
    ]

    metric_x_positions = np.arange(len(summary_metrics))
    geomeans = []
    colors = []
    labels = []

    for metric_col, metric_label, metric_color in summary_metrics:
        geo = _geom_mean(normalized_df[metric_col])
        geomeans.append(geo)
        colors.append(metric_color)
        labels.append(metric_label)

    valid_geomeans = [g for g in geomeans if not np.isnan(g)]
    max_val = max(valid_geomeans) if valid_geomeans else 1.0

    bars = summary_ax.bar(
        metric_x_positions,
        geomeans,
        width=bar_width,
        color=colors,
        edgecolor='black',
        linewidth=0.8,
    )

    for bar, value in zip(bars, geomeans):
        if np.isnan(value):
            label = "NaN"
        else:
            label = f"{value:.2f}"
        summary_ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            label,
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=90,
        )

    summary_ax.axhline(1.0, color="black", linestyle="--", linewidth=1, alpha=0.7)
    summary_ax.grid(axis='y', linestyle='-', alpha=0.3, color='gray')
    summary_ax.set_axisbelow(True)
    summary_ax.set_xticks(metric_x_positions)
    summary_ax.set_xticklabels(labels, rotation=30, ha="right")
    summary_ax.set_ylabel("Normalized Value")
    summary_ax.set_ylim(bottom=0, top=max_val * 1.15)

    fig.suptitle(f"{arch_name} vs {BASELINE_ARCH_KEY} (baseline)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Saved plot: {output_path}")


def run_all_architectures() -> tuple[list[pd.DataFrame], dict[str, pd.DataFrame]]:
    """Run all architectures and return results.

    Uses run_parallel_arch_experiments when NUM_ARCH_WORKERS > 1 to enable
    concurrent execution across different architectures.

    Returns:
        Tuple of (all_results list, arch_results dict by arch name)
    """
    # Build config list: (task_name, arch_class, arch_config)
    arch_configs = []
    for arch_class in ARCHS_TO_RUN:
        if arch_class not in ARCH_CONFIG:
            print(f"Warning: {arch_class.__name__} not in ARCH_CONFIG, skipping")
            continue
        arch_config = ARCH_CONFIG[arch_class]
        arch_configs.append((arch_config["name"], arch_class, arch_config))

    if NUM_ARCH_WORKERS > 1:
        # Parallel execution across architectures
        print(f"\nRunning {len(arch_configs)} architecture(s) with {NUM_ARCH_WORKERS} parallel workers...")
        results_dict = run_parallel_arch_experiments(
            arch_configs=arch_configs,
            runner_fn=run_single_arch,
            num_workers=NUM_ARCH_WORKERS,
            verbose=VERBOSE,
        )
        # Convert to expected format
        all_results = [df for df in results_dict.values() if df is not None]
        arch_results = {name: df for name, df in results_dict.items() if df is not None}
    else:
        # Sequential execution (original behavior)
        all_results = []
        arch_results = {}
        for arch_name, arch_class, arch_config in arch_configs:
            df = run_single_arch(arch_class, arch_config)
            if df is not None:
                all_results.append(df)
                arch_results[arch_name] = df

    return all_results, arch_results


def main():
    # Create output directory with timestamp
    timestamp = dt.now().strftime("%d%b%y-%H.%M.%S")
    folder_name = f"{RUN_PREFIX}{timestamp}" if RUN_PREFIX else timestamp
    output_dir = Path("results") / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Run all architectures (parallel or sequential based on NUM_ARCH_WORKERS)
    all_results, arch_results = run_all_architectures()

    # Save individual architecture results
    for arch_name, df in arch_results.items():
        arch_csv_path = output_dir / f"{arch_name}_results.csv"
        df.to_csv(arch_csv_path, index=False)
        print(f"  Saved individual results: {arch_csv_path}")

    if not all_results:
        print("No results generated!")
        return

    # Combine all results
    combined_df = pd.concat(all_results, ignore_index=True)

    # Save augmented results CSV
    augmented_csv_path = output_dir / "all_results.csv"
    combined_df.to_csv(augmented_csv_path, index=False)
    print(f"\nSaved augmented results: {augmented_csv_path}")

    # Normalize and plot for each architecture individually
    if BASELINE_ARCH_KEY in arch_results:
        base_df = arch_results[BASELINE_ARCH_KEY]

        for arch_name, arch_df in arch_results.items():
            if arch_name == BASELINE_ARCH_KEY:
                continue

            print(f"\nProcessing {arch_name} vs {BASELINE_ARCH_KEY}...")

            try:
                normalized_df = normalize_single_arch(base_df, arch_df)

                # Save individual normalized CSV
                normalized_csv_path = output_dir / f"{arch_name}_normalized.csv"
                normalized_df.to_csv(normalized_csv_path, index=False)
                print(f"  Saved normalized results: {normalized_csv_path}")

                # Generate individual plot
                plot_path = output_dir / f"{arch_name}_normalized.png"
                plot_single_arch_metrics(normalized_df, arch_name, plot_path)

            except Exception as e:
                print(f"  Warning: Could not normalize {arch_name}: {e}")

        # Also generate the combined normalized results and plot
        normalized_df = normalize_all_against_baseline(combined_df, BASELINE_ARCH_KEY)
        if not normalized_df.empty:
            normalized_csv_path = output_dir / "all_results_normalized.csv"
            normalized_df.to_csv(normalized_csv_path, index=False)
            print(f"\nSaved combined normalized results: {normalized_csv_path}")

            # Generate combined plots
            plot_path = output_dir / "all_normalized_metrics.png"
            plot_normalized_metrics(normalized_df, plot_path)
        else:
            print("Warning: Normalization produced empty results")
    else:
        print(f"Warning: Baseline architecture '{BASELINE_ARCH_KEY}' not found in results")
        print("Skipping normalization and plotting")

    print(f"\nAll outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()

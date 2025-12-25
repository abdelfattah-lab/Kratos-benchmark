#!/usr/bin/env python3
"""
Run multiple designs across multiple architectures, producing:
1. Augmented all_results.csv with 'arch' column
2. Normalized results CSV (normalized against baseline architecture)
3. Plot PNGs for key metrics

Configuration:
- ARCH_MAP: Dictionary mapping ArchFactory classes to string labels
- DESIGN_LIST: List of (Design, params) tuples to run
- BASELINE_ARCH_KEY: Which arch label to use as normalization baseline
"""

import structure.consts.keys as keys
from structure.consts.translation import TRANSLATIONS_GRAPH
from utils import VERILOG_DIR

from runs.vtr_denoised_same_arch_raw import run_vtr_denoised_same_arch_raw

import runs.benchmarks.kratos as kratos
import runs.benchmarks.kratos_tiny as tiny

import util.derived_metrics as derived_metrics

# Architecture imports
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.four_bit_adder import (
    DCC1ArchFactory,
    DCC2ArchFactory,
    DCC2FaithfulArchFactory,
    DCC3ArchFactory,
)
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.lut_skip_dcc3 import LUTSkipDCC3ArchFactory

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
import os
import os.path as path
from pathlib import Path
from datetime import datetime as dt
from pandas import DataFrame
import pandas as pd
from typing import Type, Iterable, Sequence
import matplotlib.pyplot as plt

# =============================================================================
# CONFIGURATION
# =============================================================================

ARCH_CONFIG: dict[Type, dict] = {
    BaseArchFactory: {
        "name": "base",
        "compressor_tree_type": "wallace",
    },
    DCC1ArchFactory: {
        "name": "dcc1",
        "compressor_tree_type": "wallace",
    },
    DCC2ArchFactory: {
        "name": "dcc2",
        # "soft_multiplier_adders": True,
        "compressor_tree_type": "wallace",
    },
    DCC3ArchFactory: {
        "name": "dcc3",
        # "compressor_tree_type": "cascade",
        # "soft_multiplier_adders": True,
        "compressor_tree_type": "wallace_ternary",
        "tree_base": 3,
        # "ternary_adder_dp": True,  # Use 3D DP to find optimal triplets for ternary adder chains
        "allow_skipping": False,
    },
    LUTSkipArchFactory: {
        "name": "dd5",
        "compressor_tree_type": "wallace",
    },
    DCC2FaithfulArchFactory: {
        "name": "dcc2_f",
        "compressor_tree_type": "wallace",
    },
    LUTSkipDCC3ArchFactory: {
        "name": "dcc3_dd5",
        "compressor_tree_type": "wallace_ternary",
        "allow_skipping": False,
        # "ternary_adder_dp": True,
    }
}

# Helper to get arch name from config
def get_arch_name(arch_class: Type) -> str:
    return ARCH_CONFIG[arch_class]["name"]

# Which architecture to use as baseline for normalization
BASELINE_ARCH_KEY: str = "base"

# Base parameters for all experiments
# Note: 'allow_skipping', 'compressor_tree_type', 'soft_multiplier_adders', 'ternary_adder_dp' can be overridden per-architecture in ARCH_CONFIG
BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': str(VERILOG_DIR),
        'allow_skipping': True,
        'adder_cin_global': False,
        'route_chan_width': 400,
        'target_ext_pin_util': '0.9,0.9',
        'compressor_tree_type': 'wallace',  # default, can be overridden per-arch
        'soft_multiplier_adders': False,  # default, can be overridden per-arch (True uses cascade adder chain)
        'ternary_adder_dp': False,  # default, can be overridden per-arch (True uses 3D DP for ternary adders)
    },
    keys.KEY_ARCH: {
        'cin_mux_stride': 0,
    },
    keys.KEY_DESIGN: {
        'data_width': 6,
        'sparsity': [0.5],
    }
}

# Designs to run
DESIGN_LIST = [
    (Conv1dFuDesign(), kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    # (Conv1dPwDesign(), tiny.get_conv_1d_pw_params(BASE_PARAMS)),
    (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), tiny.get_conv_2d_pw_params(BASE_PARAMS)),
    (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign(), tiny.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), tiny.get_gemms_params(BASE_PARAMS)),
]

# Which architectures to actually run (subset of ARCH_MAP keys)
ARCHS_TO_RUN: list[Type] = [
    BaseArchFactory,
    LUTSkipArchFactory,
    # DCC1ArchFactory,
    DCC2ArchFactory,
    # DCC2FaithfulArchFactory,
    DCC3ArchFactory,
    # LUTSkipDCC3ArchFactory,
]

# Metrics to plot
METRICS_TO_PLOT = (
    ("area_fle", "Area (Normalized)"),
    ("cpd", "Critical Path Delay (Normalized)"),
    ("adp_fle", "Area-Delay Product (Normalized)"),
)

# Filtering parameters
FILTER_PARAMS = ['per_fle_area', 'data_width', 'sparsity', 'compressor_tree_type', 'soft_multiplier_adders', 'ternary_adder_dp']
FILTER_RESULTS = [
    'fmax', 'cpd', 'twl', 'mrcu',
    'rcu_0.1', 'rcu_0.2', 'rcu_0.3', 'rcu_0.4', 'rcu_0.5',
    'rcu_0.6', 'rcu_0.7', 'rcu_0.8', 'rcu_0.9', 'rcu_1.0',
    'concurrent_lut5s', 'concurrent_lut6s',
]
FILTER_BLOCKS = ['clb', 'fle', 'fle1', 'fle2', 'lut5', 'lut6', 'adder']

# Runner settings
NUM_PARALLEL_TASKS = 3
VERBOSE = True

# Results folder prefix (e.g., 'full-run-' creates 'results/full-run-<timestamp>')
RUN_PREFIX = 'full-run-'

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
# NORMALIZATION (adapted from normalize_multi_csv.py)
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
    combined = combined.sort_values(["impl", "arch"], kind="mergesort").reset_index(drop=True)
    return combined

# =============================================================================
# PLOTTING (adapted from plot_normalized_metrics.py)
# =============================================================================

BAR_COLORS = {
    "base": "#808080",
    "dcc1": "#2c9b22",
    "dcc2": "#ff7f0e",
    "dcc2_f": "#aa1204",
    "dcc3": "#9467bd",
    "dd5": "#1f77b4",
    "dcc3_dd5": "#d62728",
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

    fig, axes = plt.subplots(1, len(metrics), figsize=(14, 4.5), sharey=False)
    if len(metrics) == 1:
        axes = [axes]

    x_positions = np.arange(num_impls + 1)  # +1 for Geomean

    for ax, (metric, ylabel) in zip(axes, metrics):
        for arch, offset in zip(arches, offsets):
            arch_df = df[df["arch"] == arch]
            values = arch_df.set_index("impl").reindex(implementations)[metric].values
            geo = _geom_mean(arch_df[metric])
            values_with_geo = np.concatenate([values, [geo]])

            color = BAR_COLORS.get(arch, None)
            bars = ax.bar(
                x_positions + offset,
                values_with_geo,
                width=bar_width,
                label=arch,
                color=color,
            )

            for bar, value in zip(bars, values_with_geo):
                if np.isnan(value):
                    label = "NaN"
                else:
                    label = f"{value:.2f}x"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    label,
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    rotation=0,
                )

        ax.axhline(1.0, color="black", linestyle="--", linewidth=1, alpha=0.7)
        ax.set_title(metric.replace("_", " ").title())
        ax.set_xticks(x_positions)
        ax.set_xticklabels([*implementations, "Geomean"], rotation=30, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        ax.legend()

    fig.tight_layout()
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
        seeds=(1239,),
        num_parallel_tasks=NUM_PARALLEL_TASKS,
        save_to_folder=False,  # Don't save individual results
        desc=f'{arch_name} architecture run',
    )

    if df is not None:
        df.insert(0, 'arch', arch_name)

    return df


def main():
    # Create output directory with timestamp
    timestamp = dt.now().strftime("%d%b%y-%H.%M.%S")
    folder_name = f"{RUN_PREFIX}{timestamp}" if RUN_PREFIX else timestamp
    output_dir = Path("results") / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Run all architectures
    all_results = []
    for arch_class in ARCHS_TO_RUN:
        if arch_class not in ARCH_CONFIG:
            print(f"Warning: {arch_class.__name__} not in ARCH_CONFIG, skipping")
            continue
        arch_config = ARCH_CONFIG[arch_class]
        df = run_single_arch(arch_class, arch_config)
        if df is not None:
            all_results.append(df)

    if not all_results:
        print("No results generated!")
        return

    # Combine all results
    combined_df = pd.concat(all_results, ignore_index=True)

    # Save augmented results CSV
    augmented_csv_path = output_dir / "all_results.csv"
    combined_df.to_csv(augmented_csv_path, index=False)
    print(f"\nSaved augmented results: {augmented_csv_path}")

    # Normalize results
    if BASELINE_ARCH_KEY in combined_df["arch"].values:
        normalized_df = normalize_all_against_baseline(combined_df, BASELINE_ARCH_KEY)
        if not normalized_df.empty:
            normalized_csv_path = output_dir / "all_results_normalized.csv"
            normalized_df.to_csv(normalized_csv_path, index=False)
            print(f"Saved normalized results: {normalized_csv_path}")

            # Generate plots
            plot_path = output_dir / "normalized_metrics.png"
            plot_normalized_metrics(normalized_df, plot_path)
        else:
            print("Warning: Normalization produced empty results")
    else:
        print(f"Warning: Baseline architecture '{BASELINE_ARCH_KEY}' not found in results")
        print("Skipping normalization and plotting")

    print(f"\nAll outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()

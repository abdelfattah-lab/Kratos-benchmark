import json
import os.path as path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import structure.consts.keys as keys

from runs.vtr_denoised_same_arch_raw import run_vtr_denoised_same_arch_raw

import runs.benchmarks.kratos as kratos
import runs.benchmarks.kratos_tiny as tiny

import util.derived_metrics as derived_metrics

from impl.arch.stratix_10.four_bit_adder_sweep import FourBitDCC2SweepArchFactory, FourBitDCC2SweepFaithfulArchFactory
from impl.arch.stratix_10.base_sweep import BaseSweepArchFactory

from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_1d.pw import Conv1dPwDesign
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.conv_2d.pw import Conv2dPwDesign
from impl.design.gemmt.fu import GemmTFuDesign
from impl.design.gemmt.rp import GemmTRpDesign
from impl.design.gemms import GemmSDesign

SWEEP_ARCH_FACTORY = FourBitDCC2SweepFaithfulArchFactory

FLE_PER_CLB_SWEEP = [2, 4, 6, 8, 10]
BASELINE_FLE_PER_CLB = 10
RUN_SEEDS = (1239, 5741, 1473)

GROUP_KEYS = ["impl", "data_width", "sparsity", "compressor_tree_type"]
EXCLUDED_COLUMNS = {"fle_per_clb"}

METRICS: Sequence[tuple[str, str]] = (
    ("cpd", "CPD"),
    ("area_fle", "Area (FLE)"),
    ("adp_fle", "ADP (FLE)"),
    ("clb_avg_util", "CLB Avg Util"),
)

COUNT_METRICS: Sequence[tuple[str, str]] = (
    ("clb", "CLBs"),
    ("fle", "FLEs"),
    ("lut5", "LUT5s"),
    ("lut6", "LUT6s"),
    ("adder", "Adders"),
)

FILTER_PARAMS = ['fle_per_clb', 'per_fle_area', 'data_width', 'sparsity', 'compressor_tree_type']
FILTER_RESULTS_BASE = [
    'fmax', 'cpd', 'twl', 'mrcu',
    'rcu_0.1', 'rcu_0.2', 'rcu_0.3', 'rcu_0.4', 'rcu_0.5',
    'rcu_0.6', 'rcu_0.7', 'rcu_0.8', 'rcu_0.9', 'rcu_1.0',
    'concurrent_lut5s', 'concurrent_lut6s',
]
FILTER_BLOCKS = [
    'clb', 'fle',
    'lut5', 'lut6',
    'adder',
]

RUN_DESCRIPTION = f'(s10) DCC2 fle sweep {FLE_PER_CLB_SWEEP}'
RUNNER_SETTINGS = {
    'verbose': True,
    'num_parallel_tasks': 3,
}

BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': False,
        'adder_cin_global': False,
        'route_chan_width': 400,
        'target_ext_pin_util': '0.9,0.9',
        'compressor_tree_type': 'wallace',
        # ... additional Experiment.run() parameters
    },
    keys.KEY_ARCH: {
        'cin_mux_stride': 0,
        'fle_per_clb': FLE_PER_CLB_SWEEP,
    },
    keys.KEY_DESIGN: {
        'data_width': 6,
        'sparsity': [0.5], # 0% - 90%
    }
}

DESIGN_LIST = [
    # Kratos benchmarks
    # (Conv1dFuDesign(), kratos.get_conv_1d_fu_params(BASE_PARAMS)),
    # (Conv1dPwDesign(), kratos.get_conv_1d_pw_params(BASE_PARAMS)),
    # (Conv2dFuDesign(), kratos.get_conv_2d_fu_params(BASE_PARAMS)),
    # (Conv2dPwDesign(), kratos.get_conv_2d_pw_params(BASE_PARAMS)),
    # (GemmTFuDesign(), kratos.get_gemmt_fu_params(BASE_PARAMS)),
    # (GemmTRpDesign(), kratos.get_gemmt_rp_params(BASE_PARAMS)),
    # (GemmSDesign(), kratos.get_gemms_params(BASE_PARAMS)),

    # Tiny benchmarks
    (Conv1dFuDesign(), tiny.get_conv_1d_fu_params(BASE_PARAMS)),
    (Conv1dPwDesign(), tiny.get_conv_1d_pw_params(BASE_PARAMS)),
    (Conv2dFuDesign(), tiny.get_conv_2d_fu_params(BASE_PARAMS)),
    (Conv2dPwDesign(), tiny.get_conv_2d_pw_params(BASE_PARAMS)),
    (GemmTFuDesign(), tiny.get_gemmt_fu_params(BASE_PARAMS)),
    (GemmTRpDesign(), tiny.get_gemmt_rp_params(BASE_PARAMS)),
    (GemmSDesign(), tiny.get_gemms_params(BASE_PARAMS)),
]

def json_safe(value):
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)

def add_derived_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = derived_metrics.apply_adder_avg_util(df)
    
    # 5-LUT measurements
    df = derived_metrics.apply_lut5_to_adder_ratio(df)
    df = derived_metrics.apply_lut5_concurrency(df)

    # 5-LUT measurements
    df = derived_metrics.apply_lut6_to_adder_ratio(df)
    df = derived_metrics.apply_lut6_concurrency(df)

    # 5/6-LUT measurements
    df = derived_metrics.apply_lut56_to_adder_ratio(df)
    df = derived_metrics.apply_lut56_concurrency(df)
    
    # Area calculations
    df = derived_metrics.apply_area_fle(df)

    # ADP
    df = derived_metrics.apply_adp_fle(df)

    new_keys = [
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

    if 'fle_per_clb' in df.columns and 'clb' in df.columns and 'fle' in df.columns:
        df['clb_avg_util'] = 0.0
        mask = (df['clb'] > 0) & (df['fle_per_clb'] > 0)
        df.loc[mask, 'clb_avg_util'] = df.loc[mask, 'fle'] / (df.loc[mask, 'clb'] * df.loc[mask, 'fle_per_clb'])
        new_keys.append('clb_avg_util')

    return df, new_keys


def normalize_by_fle(df: pd.DataFrame, baseline_fle: int) -> pd.DataFrame:
    if 'fle_per_clb' not in df.columns:
        raise KeyError("Input data must contain 'fle_per_clb'.")

    group_keys = [key for key in GROUP_KEYS if key in df.columns]
    if 'impl' not in df.columns:
        raise KeyError("Input data must contain 'impl' for per-design normalization.")
    if not group_keys:
        raise ValueError("No grouping columns available for normalization.")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    metric_cols = [
        col for col in numeric_cols
        if col not in group_keys and col not in EXCLUDED_COLUMNS
    ]
    if not metric_cols:
        raise ValueError("No numeric columns remain to normalize after exclusions.")

    baseline_df = df[df['fle_per_clb'] == baseline_fle]
    if baseline_df.empty:
        raise ValueError(
            f"No baseline rows found with fle_per_clb == {baseline_fle}; cannot normalize."
        )

    if baseline_df.duplicated(subset=group_keys).any():
        dupes = baseline_df[baseline_df.duplicated(subset=group_keys, keep=False)]
        preview_cols = group_keys + ['fle_per_clb']
        raise ValueError(
            "Baseline rows are not unique for some key combinations. Example:\n"
            + dupes[preview_cols].head().to_string(index=False)
        )

    renamed = baseline_df[group_keys + metric_cols].rename(
        columns={col: f"{col}__baseline" for col in metric_cols}
    )
    merged = df.merge(renamed, on=group_keys, how='left')
    baseline_cols = [f"{col}__baseline" for col in metric_cols]

    missing_baseline = merged[baseline_cols].isna().any(axis=1)
    if missing_baseline.any():
        bad_keys = merged.loc[missing_baseline, group_keys + ['fle_per_clb']]
        raise ValueError(
            "Missing baseline row (fle_per_clb == "
            f"{baseline_fle}) for some entries. First few:\n"
            + bad_keys.head().to_string(index=False)
        )

    for col, base_col in zip(metric_cols, baseline_cols):
        denom = merged[base_col].replace({0: np.nan})
        merged[col] = merged[col] / denom
    merged = merged.drop(columns=baseline_cols)

    return merged


def geometric_mean(series: pd.Series) -> float:
    values = series.dropna().astype(float)
    if values.empty:
        return float('nan')
    if (values < 0).any():
        raise ValueError("Geometric mean is undefined for negative values.")
    if (values == 0).any():
        return 0.0
    return float(np.exp(np.log(values).mean()))


def apply_filters(df: pd.DataFrame, filters: dict[str, object | None]) -> pd.DataFrame:
    out = df.copy()
    for column, value in filters.items():
        if value is None or column not in out.columns:
            continue
        out = out[out[column] == value]
    return out


def validate_columns(df: pd.DataFrame, metrics: Sequence[tuple[str, str]]) -> None:
    missing = [col for col, _ in metrics if col not in df.columns]
    if missing:
        raise KeyError("Column(s) not found in data: " + ", ".join(sorted(set(missing))))
    if 'fle_per_clb' not in df.columns:
        raise KeyError("Data must contain 'fle_per_clb' for plotting.")


def build_geomean_dataframe(df: pd.DataFrame, metrics: Sequence[tuple[str, str]]) -> pd.DataFrame:
    validate_columns(df, metrics)
    grouped = df.groupby('fle_per_clb')
    rows: list[dict[str, float]] = []
    for fle_val, group in grouped:
        record = {'fle_per_clb': fle_val}
        for col, _ in metrics:
            record[col] = geometric_mean(group[col])
        rows.append(record)
    return pd.DataFrame(rows)


def plot_grouped_bars(
        ax: plt.Axes,
        df: pd.DataFrame,
        metrics: Sequence[tuple[str, str]],
        draw_baseline: bool,
        title: str,
        y_label: str,
    ) -> None:
    grouped = df.groupby('fle_per_clb').mean(numeric_only=True)
    if grouped.empty:
        raise ValueError("No data available after filtering; nothing to plot.")

    fle_values = sorted(grouped.index.tolist())
    num_metrics = len(metrics)
    num_groups = len(fle_values)

    x = np.arange(num_metrics)
    bar_width = min(0.8 / max(num_groups, 1), 0.2)
    offsets = (np.arange(num_groups) - (num_groups - 1) / 2) * bar_width

    for offset, fle in zip(offsets, fle_values):
        heights = [grouped.at[fle, col] for col, _ in metrics]
        ax.bar(
            x + offset,
            heights,
            width=bar_width,
            label=f"FLE/CLB = {fle}",
        )

    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in metrics])
    ax.set_ylabel(y_label)
    ax.set_title(title)
    if draw_baseline:
        ax.axhline(1.0, color='red', linestyle='--', linewidth=1.0, label='Baseline = 1.0')
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.4)


def plot_design_metrics(
        normalized_df: pd.DataFrame,
        impl_name: str,
        save_dir: str,
    ) -> None:
    filters = {'impl': impl_name}
    df_norm = apply_filters(normalized_df, filters)
    df_counts = df_norm

    if df_norm.empty or df_counts.empty:
        print(f"(!) Skipping plot for {impl_name}: no data after filtering.")
        return

    validate_columns(df_norm, METRICS)
    validate_columns(df_counts, COUNT_METRICS)

    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=False)
    plot_grouped_bars(
        axes[0],
        df_norm,
        METRICS,
        draw_baseline=True,
        title=f"{impl_name}: normalized metrics vs. fle_per_clb",
        y_label="Normalized Value",
    )
    plot_grouped_bars(
        axes[1],
        df_counts,
        COUNT_METRICS,
        draw_baseline=True,
        title=f"{impl_name}: normalized resource counts vs. fle_per_clb",
        y_label="Normalized Count",
    )

    plt.tight_layout(h_pad=3.0)
    safe_impl = impl_name.replace(path.sep, "_").replace(" ", "_")
    output_png = path.join(save_dir, f"{safe_impl}_fle_metric_bars.png")
    fig.savefig(output_png, dpi=300)
    plt.close(fig)
    print(f"(!) Wrote plot to {output_png}")


def plot_geomean_metrics(
        normalized_df: pd.DataFrame,
        save_dir: str,
    ) -> None:
    norm_geo_df = build_geomean_dataframe(normalized_df, METRICS)
    count_geo_df = build_geomean_dataframe(normalized_df, COUNT_METRICS)

    if norm_geo_df.empty or count_geo_df.empty:
        print("(!) Skipping geomean plot: insufficient data.")
        return

    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=False)
    plot_grouped_bars(
        axes[0],
        norm_geo_df,
        METRICS,
        draw_baseline=True,
        title="Geomean: normalized metrics vs. fle_per_clb",
        y_label="Normalized Value (Geomean)",
    )
    plot_grouped_bars(
        axes[1],
        count_geo_df,
        COUNT_METRICS,
        draw_baseline=True,
        title="Geomean: normalized resource counts vs. fle_per_clb",
        y_label="Normalized Count (Geomean)",
    )

    plt.tight_layout(h_pad=3.0)
    output_png = path.join(save_dir, "geomean_fle_metric_bars.png")
    fig.savefig(output_png, dpi=300)
    plt.close(fig)
    print(f"(!) Wrote geomean plot to {output_png}")


def save_experiment_summary(
        save_dir: str,
        raw_csv: str,
        normalized_csv: str,
    ) -> None:
    design_entries = [
        {
            'design_class': design.__class__.__name__,
            'params': json_safe(params),
        }
        for design, params in DESIGN_LIST
    ]

    summary = {
        'description': RUN_DESCRIPTION,
        'arch_factory': SWEEP_ARCH_FACTORY.__name__,
        'fle_per_clb_sweep': FLE_PER_CLB_SWEEP,
        'seeds': list(RUN_SEEDS),
        'base_params': json_safe(BASE_PARAMS),
        'designs': design_entries,
        'filters': {
            'params': FILTER_PARAMS,
            'results': FILTER_RESULTS_BASE,
            'blocks': FILTER_BLOCKS,
        },
        'runner_settings': {
            **RUNNER_SETTINGS,
            'save_to_folder': True,
        },
        'derived_metrics_fn': 'add_derived_metrics',
        'normalization': {
            'baseline_fle_per_clb': BASELINE_FLE_PER_CLB,
            'group_keys': GROUP_KEYS,
            'metrics': [{'column': col, 'label': label} for col, label in METRICS],
            'count_metrics': [{'column': col, 'label': label} for col, label in COUNT_METRICS],
        },
        'results': {
            'raw_csv': raw_csv,
            'normalized_csv': normalized_csv,
        },
    }

    summary_path = path.join(save_dir, "experiment_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"(!) Wrote experiment summary to {summary_path}")

folder = run_vtr_denoised_same_arch_raw(
    arch=SWEEP_ARCH_FACTORY,
    design_list=DESIGN_LIST,
    filter_params=list(FILTER_PARAMS),
    filter_results=list(FILTER_RESULTS_BASE),
    filter_blocks=FILTER_BLOCKS,
    df_processing_fn=add_derived_metrics,
    seeds=RUN_SEEDS,
    # notify='telegram',
    # notify_batch=5,
    save_to_folder=True,
    desc=RUN_DESCRIPTION,
    **RUNNER_SETTINGS,
)

if folder is not None:
    all_results_csv = path.join(folder, "all_results.csv")
    if not path.exists(all_results_csv):
        raise FileNotFoundError(f"Expected results CSV not found at {all_results_csv}")

    all_df = pd.read_csv(all_results_csv)
    normalized_df = normalize_by_fle(all_df, BASELINE_FLE_PER_CLB)

    normalized_csv = path.join(folder, "all_results_normalized_by_fle.csv")
    normalized_df.to_csv(normalized_csv, index=False)
    print(f"(!) Wrote normalized CSV to {normalized_csv}")

    impl_values = normalized_df['impl'].dropna().unique().tolist()
    for impl_name in sorted(impl_values):
        plot_design_metrics(normalized_df, impl_name, folder)

    plot_geomean_metrics(normalized_df, folder)
    save_experiment_summary(folder, all_results_csv, normalized_csv)

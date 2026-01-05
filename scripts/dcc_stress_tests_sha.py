#!/usr/bin/env python3
"""
End-to-End Stress Test (Mini) for DCC3 architectures.

Based on the paper's stress test methodology using mini Kratos circuits:
- conv1d-FU-mini
- conv2d-FU-mini
- gemmt-FU-mini

Tests five architectures:
1. Base (baseline for sizing)
2. DD5 (LUT Skip)
3. DCC3 (4-bit double carry chain)
4. LUTSkip-DCC3 (LUT Skip on DCC3)
5. AdderSkip-DCC3 (Adder Skip on DCC3)

Procedure for each design:
1. Run Kratos design on baseline to determine minimum required grid size
2. Clamp grid size for all five architectures
3. Incrementally add SHA circuit instances (via ShaxN plugin) until failure
4. Compare final metrics across architectures
"""

# Architecture imports
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.lut_skip import LUTSkipArchFactory  # DD5
from impl.arch.stratix_10.four_bit_adder import DCC3ArchFactory
from impl.arch.stratix_10.lut_skip_dcc3 import LUTSkipDCC3ExpArchFactory, AdderSkipDCC3ArchFactory

# Designs
from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.gemmt.fu import GemmTFuDesign

# Plugins
from impl.plugin.shaxN import ShaxNPlugin

# Parameters
import runs.benchmarks.kratos_mini as mini

# Experiment
from impl.exp.vtr import VtrExperiment

# Runner and typing
from structure.run import Runner, MultiArchRunner
from structure.arch import ArchFactory
from structure.design import PluginDesign
from structure.plugin import Plugin
from typing import Type

# Constants
import structure.consts.keys as keys
from utils import VERILOG_DIR

# Utilities
import util.derived_metrics as derived_metrics
from util.formatting import pretty

# Python libraries
from pathlib import Path
from datetime import datetime as dt
from copy import deepcopy
import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

ARCH_INSTANCES = {
    'base': BaseArchFactory(),
    # 'dd5': LUTSkipArchFactory(),
    # 'dcc3': DCC3ArchFactory(),
    'lutskip_dcc3': LUTSkipDCC3ExpArchFactory(),
    # 'adderskip_dcc3': AdderSkipDCC3ArchFactory(),
}

ARCH_CLASSES = {
    'base': BaseArchFactory,
    # 'dd5': LUTSkipArchFactory,
    # 'dcc3': DCC3ArchFactory,
    'lutskip_dcc3': LUTSkipDCC3ExpArchFactory,
    # 'adderskip_dcc3': AdderSkipDCC3ArchFactory,
}

# Per-architecture parameter overrides (applied on top of BASE_PARAMS)
ARCH_PARAM_OVERRIDES = {
    'base': {
        keys.KEY_EXP: {'compressor_tree_type': 'wallace'},
        keys.KEY_DESIGN: {'tree_base': 2},
    },
    # 'dd5': {
    #     keys.KEY_EXP: {'compressor_tree_type': 'wallace'},
    #     keys.KEY_DESIGN: {'tree_base': 2},
    # },
    # dcc3, lutskip_dcc3, adderskip_dcc3 use defaults (tree_base=3, wallace_ternary)
    'lutskip_dcc3': {
        keys.KEY_EXP: {
            'allow_skipping': True,
            'allow_skip_existing': False,
        },
    },
}

# this runs the initial sizing
BASELINE_ARCH_NAME = 'base'

BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': str(VERILOG_DIR),
        'allow_skipping': True,
        'allow_skip_existing': False,
        'adder_cin_global': False,
        'soft_multiplier_adders': False,
        'route_chan_width': 400,
        'compressor_tree_type': 'wallace_ternary',
        'ternary_adder_dp': False,
        'force_denser_packing': False,
        'target_ext_pin_util': '0.9,0.9',
    },
    keys.KEY_ARCH: {
        'cin_mux_stride': 0,
        'enable_lut6': True,
    },
    keys.KEY_DESIGN: {
        'sparsity': 0,
        'data_width': 6,
        'tree_base': 3,
    }
}

# Plugin and stress test parameter
PLUGIN = ShaxNPlugin()
N_PARAM = 'sha_num'

# Design list with mini parameters (matching paper: conv1d-FU-mini, conv2d-FU-mini, gemmt-FU-mini)
DESIGN_CLASS_LIST = [
    (Conv1dFuDesign, mini.get_conv_1d_fu_params),
    (Conv2dFuDesign, mini.get_conv_2d_fu_params),
    (GemmTFuDesign, mini.get_gemmt_fu_params),
]

# Define filtered parameters and results
FILTER_PARAMS = ['sha_num', 'data_width', 'per_fle_area', 'compressor_tree_type']
FILTER_RESULTS = ['fmax', 'cpd', 'twl', 'concurrent_lut5s', 'concurrent_adders']
FILTER_BLOCKS = ['clb', 'fle', 'lut5', 'lut6', 'adder']

NUM_PARALLEL_TASKS = 1  # Experiments per architecture batch (used in sequential mode)
VERBOSE = True
SEEDS = (1239, 5741, 1473)
RUN_PREFIX = 'dcc3-stress-test-mini-'


# =============================================================================
# DERIVED METRICS
# =============================================================================

def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived metrics to the DataFrame."""
    df = derived_metrics.apply_adder_avg_util(df)
    df = derived_metrics.apply_area_fle(df)
    df = derived_metrics.apply_adp_fle(df)
    df = derived_metrics.apply_lut5_to_adder_ratio(df)
    df = derived_metrics.apply_lut5_concurrency(df)
    return df


def apply_arch_overrides(base_params: dict, arch_name: str) -> dict:
    """Apply per-architecture parameter overrides."""
    params = deepcopy(base_params)
    if arch_name in ARCH_PARAM_OVERRIDES:
        for key_section, overrides in ARCH_PARAM_OVERRIDES[arch_name].items():
            if key_section in params:
                params[key_section].update(overrides)
    return params


# =============================================================================
# CORE FUNCTIONS (following run_stress_test.py pattern)
# =============================================================================

def get_max_N(
    arch: ArchFactory,
    arch_name: str,
    DesignClass: Type[PluginDesign],
    plugin: Plugin,
    base_params: dict,
    N_param: str,
    num_parallel_tasks: int = NUM_PARALLEL_TASKS,
    batch_size: int = 3,
    seeds: tuple[int, ...] = SEEDS,
) -> pd.DataFrame | None:
    """
    Returns the DataFrame of all possible instances that fit in the architecture.
    Runs batches until failure, averaging results across seeds.

    Args:
        num_parallel_tasks: Number of experiments to run in parallel within this architecture.
        batch_size: Number of N values to try per batch.
        seeds: Tuple of seeds to run each experiment with. Results are averaged across seeds.
    """
    runner = Runner()
    N_start = 1
    main_df = None
    num_seeds = len(seeds)

    while True:
        possible_N_values = list(range(N_start, N_start + batch_size))

        # Run all (N_value, seed) combinations
        for seed in seeds:
            params = apply_arch_overrides(base_params, arch_name)
            params[keys.KEY_EXP]['root_dir'] = str(
                Path(params[keys.KEY_EXP]['root_dir']) / arch_name / f"seed-{seed}"
            )
            params[keys.KEY_EXP]['seed'] = seed
            params[keys.KEY_DESIGN][N_param] = possible_N_values
            runner.add_experiments(VtrExperiment, arch, DesignClass(plugin=plugin), params)

        results = runner.run_all_threaded(
            verbose=VERBOSE,
            desc=f'{arch_name} N {N_start}-{N_start + batch_size - 1} ({num_seeds} seeds)',
            num_parallel_tasks=num_parallel_tasks,
            filter_params=FILTER_PARAMS + ['seed'],
            filter_results=FILTER_RESULTS + FILTER_BLOCKS,
            result_kwargs=dict(extract_blocks_list=FILTER_BLOCKS),
        )
        runner.clear_experiments()

        if len(results) == 0:
            break

        # Combine results from all seeds and average
        batch_df = pd.concat(results.values(), ignore_index=True)

        # Group by N_param and average across seeds
        group_cols = [c for c in FILTER_PARAMS if c in batch_df.columns and c != 'seed']
        numeric_cols = batch_df.select_dtypes(include='number').columns.tolist()
        avg_df = batch_df.groupby(group_cols, as_index=False)[numeric_cols].mean()

        # Count successful N values (need all seeds to succeed for a valid average)
        success_counts = batch_df.groupby(N_param).size()
        successful_N = success_counts[success_counts == num_seeds].index.tolist()
        avg_df = avg_df[avg_df[N_param].isin(successful_N)]

        if avg_df.empty:
            break

        if main_df is None:
            main_df = avg_df
        else:
            main_df = pd.concat([main_df, avg_df], ignore_index=True)

        # Break if not all N values succeeded (at least one failure)
        if len(successful_N) < batch_size:
            break

        N_start += batch_size

    if main_df is not None:
        main_df = add_derived_metrics(main_df)
        main_df.sort_values(by=N_param, inplace=True)

    return main_df


def _run_initial_sizing(
    DesignClass: Type[PluginDesign],
    plugin: Plugin,
    base_params: dict,
    N_param: str,
) -> tuple[int, int] | None:
    """Run baseline to determine grid size. Returns (grid_w, grid_h) or None on failure."""
    design_name = DesignClass.__name__
    baseline_arch = ARCH_INSTANCES[BASELINE_ARCH_NAME]

    print(f"\n(!) Running initial sizing for {design_name} on {BASELINE_ARCH_NAME}...")

    # Apply baseline architecture's parameter overrides
    sizing_params = apply_arch_overrides(base_params, BASELINE_ARCH_NAME)
    sizing_params[keys.KEY_EXP]['root_dir'] = str(
        Path(sizing_params[keys.KEY_EXP]['root_dir']) / BASELINE_ARCH_NAME
    )
    sizing_params[keys.KEY_DESIGN][N_param] = 1

    base_exp = VtrExperiment(baseline_arch, DesignClass(plugin=plugin), sizing_params)
    base_exp.run()
    if base_exp.process:
        base_exp.process.wait()
    base_results = base_exp.get_result()

    grid_w, grid_h = base_results.get('gridx', 0), base_results.get('gridy', 0)
    if grid_w == 0 or grid_h == 0:
        print(f"(!) Failed to determine grid size for {design_name}.")
        return None

    print(f"(!) Sizing {design_name} to {grid_w} x {grid_h}.")
    return (grid_w, grid_h)


def run_seq(
    DesignClass: Type[PluginDesign],
    plugin: Plugin,
    base_params: dict,
    N_param: str,
    num_parallel_tasks: int = NUM_PARALLEL_TASKS,
    batch_size: int = 3,
) -> dict[str, pd.DataFrame] | None:
    """
    Run stress test SEQUENTIALLY across all architectures.

    Args:
        num_parallel_tasks: Number of experiments to run in parallel within each architecture.
        batch_size: Number of SHA N values to try per batch.

    Returns:
        {arch_name: DataFrame, ...} or None on failure
    """
    design_name = DesignClass.__name__

    # 1. Run initial sizing
    grid_size = _run_initial_sizing(DesignClass, plugin, base_params, N_param)
    if grid_size is None:
        return None

    # 2. Fix grid size
    base_params[keys.KEY_ARCH]['fixed_size'] = grid_size

    # 3. Run stress test on each architecture sequentially
    results = {}
    for arch_name, arch in ARCH_INSTANCES.items():
        print(f"\n{'='*60}")
        print(f"(!) {design_name}: Getting max instances for {arch_name}...")
        print(f"{'='*60}")

        df = get_max_N(arch, arch_name, DesignClass, plugin, base_params, N_param,
                       num_parallel_tasks=num_parallel_tasks, batch_size=batch_size)

        if df is not None and not df.empty:
            max_row = df.loc[df[N_param].idxmax()]
            print(f"(!) Maximum for {arch_name}:")
            pretty(max_row.to_dict(), 1)
            results[arch_name] = df
        else:
            print(f"(!) No successful runs for {arch_name}")

    return results if results else None


def run_parallel(
    DesignClass: Type[PluginDesign],
    plugin: Plugin,
    base_params: dict,
    N_param: str,
    total_parallel_tasks: int = 45,
    batch_size: int = 3,
) -> dict[str, pd.DataFrame] | None:
    """
    Run stress test IN PARALLEL across all architectures.

    All architectures run concurrently, with experiments distributed across them.

    Args:
        total_parallel_tasks: Total number of concurrent VTR processes.
            Distributed as: all archs run in parallel, each with
            (total_parallel_tasks // num_archs) internal parallelism.
            E.g., with 5 archs and total_parallel_tasks=15, each arch runs 3 experiments at once.
        batch_size: Number of SHA N values to try per batch.

    Returns:
        {arch_name: DataFrame, ...} or None on failure
    """
    design_name = DesignClass.__name__
    num_archs = len(ARCH_CLASSES)

    # Calculate per-architecture parallelism
    # Each batch runs: batch_size N values × num_seeds = experiments per batch
    num_seeds = len(SEEDS)
    per_arch_tasks = max(1, total_parallel_tasks // num_archs)
    print(f"(!) Parallel mode: {num_archs} archs × {per_arch_tasks} tasks/arch = {num_archs * per_arch_tasks} total concurrent processes")
    print(f"(!) Each batch: {batch_size} N values × {num_seeds} seeds = {batch_size * num_seeds} experiments")

    # 1. Run initial sizing (must be sequential)
    grid_size = _run_initial_sizing(DesignClass, plugin, base_params, N_param)
    if grid_size is None:
        return None

    # 2. Fix grid size
    base_params[keys.KEY_ARCH]['fixed_size'] = grid_size

    # 3. Set up MultiArchRunner (all archs run in parallel)
    mar = MultiArchRunner(num_arch_workers=num_archs)

    shared_args = {
        'DesignClass': DesignClass,
        'plugin': plugin,
        'base_params': base_params,
        'N_param': N_param,
        'per_arch_tasks': per_arch_tasks,
        'batch_size': batch_size,
    }

    for arch_name, arch_class in ARCH_CLASSES.items():
        mar.add_task(arch_name, arch_class, {'name': arch_name}, shared_args)

    # 4. Define runner function (creates fresh arch instance per thread)
    def run_arch_stress_test(arch_class, arch_config, args):
        arch_name = arch_config['name']
        arch_instance = arch_class()  # Fresh instance for this thread
        return get_max_N(
            arch_instance,
            arch_name,
            args['DesignClass'],
            args['plugin'],
            deepcopy(args['base_params']),  # deepcopy to avoid race conditions
            args['N_param'],
            num_parallel_tasks=args['per_arch_tasks'],
            batch_size=args['batch_size'],
        )

    # 5. Run all architectures in parallel
    print(f"\n{'='*60}")
    print(f"(!) {design_name}: Running stress test for ALL {num_archs} architectures in parallel...")
    print(f"{'='*60}")

    arch_results = mar.run_all(run_arch_stress_test, verbose=True)

    # 6. Process results
    results = {}
    for arch_name, df in arch_results.items():
        if df is not None and not df.empty:
            max_row = df.loc[df[N_param].idxmax()]
            print(f"(!) Maximum for {arch_name}:")
            pretty(max_row.to_dict(), 1)
            results[arch_name] = df
        else:
            print(f"(!) No successful runs for {arch_name}")

    return results if results else None


# =============================================================================
# MAIN
# =============================================================================

def main(parallel: bool = False, num_parallel_tasks: int = 45, batch_size: int = 3):
    """
    Run the stress test.

    Args:
        parallel: If True, run ALL architectures in parallel.
        num_parallel_tasks: Total number of concurrent VTR processes.
            - Sequential mode: experiments per architecture batch
            - Parallel mode: total concurrent processes (distributed across all archs)
        batch_size: Number of SHA N values to try per batch.
    """
    # Create output directory
    timestamp = dt.now().strftime("%d%b%y-%H.%M.%S")
    folder_name = f"{RUN_PREFIX}{timestamp}"
    output_dir = Path("results") / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Run stress test for each design
    all_results = {}

    for DesignClass, get_params_fn in DESIGN_CLASS_LIST:
        design_name = DesignClass.__name__

        print(f"\n{'#'*70}")
        print(f"# Starting stress test for: {design_name}")
        print(f"{'#'*70}")

        # Get base parameters for this design
        base_params = get_params_fn(deepcopy(BASE_PARAMS))

        # Run stress test
        if parallel:
            results = run_parallel(DesignClass, PLUGIN, base_params, N_PARAM, num_parallel_tasks, batch_size)
        else:
            results = run_seq(DesignClass, PLUGIN, base_params, N_PARAM, num_parallel_tasks, batch_size)

        if results:
            all_results[design_name] = results

            # Save raw results
            for arch_name, df in results.items():
                csv_path = output_dir / f"{design_name}_{arch_name}_raw.csv"
                df.to_csv(csv_path, index=False)
                print(f"Saved: {csv_path}")

    if not all_results:
        print("No results generated!")
        return all_results

    # Create summary
    summary_data = []
    for design_name, arch_results in all_results.items():
        baseline_max = arch_results.get(BASELINE_ARCH_NAME, pd.DataFrame({N_PARAM: [0]}))[N_PARAM].max()

        for arch_name, df in arch_results.items():
            max_n = df[N_PARAM].max()
            max_row = df[df[N_PARAM] == max_n].iloc[0]
            improvement = ((max_n / baseline_max) - 1) * 100 if baseline_max > 0 else 0

            summary_data.append({
                'design': design_name,
                'architecture': arch_name,
                'max_sha_instances': int(max_n),
                'improvement_vs_baseline': f"{improvement:.1f}%",
                'cpd_at_max': f"{max_row.get('cpd', 0):.3f}",
                'clb_at_max': int(max_row.get('clb', 0)),
                'lut5_concurrency': f"{max_row.get('lut5_concurrency', 0) * 100:.1f}%",
            })

    summary_df = pd.DataFrame(summary_data)
    summary_path = output_dir / "summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"\nSaved summary: {summary_path}")
    print("\nSummary:")
    print(summary_df.to_string(index=False))

    print(f"\nAll outputs saved to: {output_dir}")
    return all_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stress Test (Mini)")
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run ALL architectures in parallel (fully parallel mode)"
    )
    parser.add_argument(
        "--num-parallel", "-n",
        type=int,
        default=45,
        help="Total concurrent VTR processes (default: 45). "
             "In parallel mode: distributed across 5 archs. "
             "In sequential mode: experiments per batch."
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=3,
        help="Number of SHA N values per batch (default: 3). "
             "Each batch runs batch_size × 3 seeds experiments."
    )
    args = parser.parse_args()

    main(parallel=args.parallel, num_parallel_tasks=args.num_parallel, batch_size=args.batch_size)

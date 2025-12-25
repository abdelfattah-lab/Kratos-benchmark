"""
Multiplier Benchmark Runner

Runs VTR flow on multiplier benchmarks from vtr-updated-dcc3 using different
architectures (base, DCC2, DCC3) and compressor tree types (wallace, cascade).

Outputs a CSV with FLE/ALM usage statistics.

Usage:
    python run_multiplier_benchmark.py

Requirements:
    - VTR_ROOT environment variable must be set to the vtr-updated-dcc3 directory
"""

import structure.consts.keys as keys
from structure.design import StandardizedSdcDesign
from utils import REPO_ROOT
from impl.exp.vtr import VtrExperiment
from structure.run import Runner
from impl.arch.stratix_10.base import BaseArchFactory
from impl.arch.stratix_10.four_bit_adder import FourBitDCC1ArchFactory, FourBitDCC2ArchFactory, FourBitDCC3ArchFactory

import os
import os.path as path
from copy import deepcopy
import pandas as pd
from datetime import datetime


# --- Design class for loading multiplier benchmarks ---

class MultiplierLoaderDesign(StandardizedSdcDesign):
    """
    Loads multiplier Verilog benchmarks from the VTR benchmark directory.
    """
    def __init__(self):
        super().__init__('mult', '', 'mult_nxn')

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        defaults = {
            'verilog_dir': self._get_multiplier_dir(),
        }
        return self.verify_required_keys(defaults, ['impl'], params)

    def _get_multiplier_dir(self) -> str:
        vtr_root = os.environ.get('VTR_ROOT')
        if vtr_root is None:
            raise ValueError("VTR_ROOT environment variable not set!")
        return path.join(vtr_root, 'vtr_flow', 'benchmarks', 'arithmetic', 'multipliers')

    def get_name(self, impl: str, **_kwargs):
        return f"mult-{impl}"

    def get_formal_name(self) -> str:
        return 'multiplier'

    def gen_wrapper(self, verilog_dir: str, impl: str, **_kwargs) -> str:
        impl_path = path.join(verilog_dir, f"{impl}.v")
        if not path.exists(impl_path):
            raise FileNotFoundError(f"Multiplier benchmark not found: {impl_path}")

        with open(impl_path, 'r') as f:
            return f.read()


# --- Configuration ---

# List of multiplier benchmarks to run
MULTIPLIER_BENCHMARKS = [
    'mult_4x4',
    'mult_5x5',
    'mult_6x6',
    'mult_7x7',
    'mult_8x8',
    'mult_9x9',
]

# Architecture configurations: (Factory class, name, compressor_tree_type)
ARCH_CONFIGS = [
    (BaseArchFactory, 'base', 'cascade'),
    (FourBitDCC1ArchFactory, 'dcc1', 'cascade'),
    (FourBitDCC2ArchFactory, 'dcc2', 'cascade'),
    (FourBitDCC3ArchFactory, 'dcc3', 'cascade'),
]

# Seeds for averaging (use single seed for faster runs, multiple for more stable results)
SEEDS = [1239]  # Add more seeds like [1239, 5741, 1473] for averaging

# Number of parallel tasks
NUM_PARALLEL_TASKS = 1


def get_base_params(compressor_tree_type: str) -> dict:
    """Generate base parameters for a given compressor tree type."""
    return {
        keys.KEY_EXP: {
            'verilog_search_dir': str(REPO_ROOT),
            'allow_skipping': True,
            'avoid_mult': True,  # Use soft multipliers only
            'adder_cin_global': False,
            'route_chan_width': 400,
            'compressor_tree_type': compressor_tree_type,
            'parser': 'default',  # Use default parser for VTR benchmarks
        },
        keys.KEY_ARCH: {},
        keys.KEY_DESIGN: {},
    }


def get_multiplier_params(base_params: dict, impl: str, root_dir: str) -> dict:
    """Generate parameters for a specific multiplier benchmark."""
    params = deepcopy(base_params)
    params[keys.KEY_EXP]['root_dir'] = root_dir
    params[keys.KEY_DESIGN]['impl'] = impl
    return params


def run_multiplier_benchmarks():
    """Main function to run all multiplier benchmarks."""

    # Verify VTR_ROOT is set
    vtr_root = os.environ.get('VTR_ROOT')
    if vtr_root is None:
        print("ERROR: VTR_ROOT environment variable not set!")
        print("Please set it to the vtr-updated-dcc3 directory:")
        print("  export VTR_ROOT=/home/anthony/repos/vtr-updated-dcc3")
        return

    print(f"VTR_ROOT: {vtr_root}")
    print(f"Running {len(MULTIPLIER_BENCHMARKS)} multiplier benchmarks")
    print(f"With {len(ARCH_CONFIGS)} architecture configurations")
    print(f"Seeds: {SEEDS}")
    print()

    # Results storage
    all_results = []

    # Run experiments for each architecture configuration
    for arch_factory, arch_name, compressor_type in ARCH_CONFIGS:
        print(f"\n{'='*60}")
        print(f"Architecture: {arch_name}, Compressor: {compressor_type}")
        print('='*60)

        runner = Runner()
        arch_inst = arch_factory()
        design = MultiplierLoaderDesign()

        base_params = get_base_params(compressor_type)

        # Add experiments for all multipliers and seeds
        for seed in SEEDS:
            for mult_impl in MULTIPLIER_BENCHMARKS:
                root_dir = path.join(
                    'experiments', 'multiplier_benchmark',
                    arch_name, compressor_type,
                    f"seed-{seed}"
                )
                params = get_multiplier_params(base_params, mult_impl, root_dir)
                params[keys.KEY_EXP]['seed'] = seed
                runner.add_experiments(VtrExperiment, arch_inst, design, params)

        # Define blocks to extract
        extract_blocks = ['clb', 'fle', 'adder', 'lut5', 'lut6']

        # Run all experiments for this architecture
        # NOTE: filter_results must include block names for them to be returned!
        results = runner.run_all_threaded(
            filter_params=['impl'],
            filter_results=['status', 'fmax', 'cpd', 'twl'] + extract_blocks,
            result_kwargs=dict(
                extract_blocks_list=extract_blocks
            ),
            verbose=False,
            num_parallel_tasks=NUM_PARALLEL_TASKS,
            desc=f'{arch_name}-{compressor_type}',
        )

        # Process results
        for _impl_key, df in results.items():
            if df.empty:
                continue

            # Average across seeds
            mean_df = df.groupby(['impl']).mean().reset_index()

            for _, row in mean_df.iterrows():
                result_entry = {
                    'architecture': arch_name,
                    'compressor': compressor_type,
                    'multiplier': row['impl'],
                    'status': row.get('status', False),
                    'fle': row.get('fle', -1),
                    'clb': row.get('clb', -1),
                    'adder': row.get('adder', -1),
                    'lut5': row.get('lut5', -1),
                    'lut6': row.get('lut6', -1),
                    'fmax': row.get('fmax', -1),
                    'cpd': row.get('cpd', -1),
                    'twl': row.get('twl', -1),
                }
                all_results.append(result_entry)

    # Create DataFrame and save to CSV
    results_df = pd.DataFrame(all_results)

    # Sort by multiplier size and architecture
    results_df['mult_size'] = results_df['multiplier'].str.extract(r'mult_(\d+)x\d+').astype(int)
    results_df = results_df.sort_values(['mult_size', 'architecture', 'compressor'])
    results_df = results_df.drop(columns=['mult_size'])

    # Create output directory
    output_dir = path.join('results', 'multiplier_benchmark')
    os.makedirs(output_dir, exist_ok=True)

    # Generate timestamp for unique filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = path.join(output_dir, f'multiplier_results_{timestamp}.csv')

    # Save to CSV
    results_df.to_csv(csv_path, index=False)
    print(f"\n{'='*60}")
    print(f"Results saved to: {csv_path}")
    print('='*60)

    # Print summary table
    print("\nSummary (FLE count by architecture and compressor):")
    print("-" * 60)
    pivot_df = results_df.pivot_table(
        index='multiplier',
        columns=['architecture', 'compressor'],
        values='fle',
        aggfunc='first'
    )
    print(pivot_df.to_string())

    return csv_path


if __name__ == '__main__':
    run_multiplier_benchmarks()

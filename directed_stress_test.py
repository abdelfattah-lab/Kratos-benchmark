"""
Occasionally, packing will fail for a certain circuit and architecture due to unfortunate seed. 
Main script stops trying to pack in more SHA circuits when 1+ of the 3 experiments per batch 
fails, so sometimes script will terminate early. To find results in this case, 
directed_stress_test.py script works, taking in architecture, number of SHAs, and Kratos benchmark 
(as well as seed and possible retries to avoid unlucky seeds causing faulty results). 
Runs end-to-end stress tests with the same methodology as run_stress_test.py
"""

import argparse
import os
import pandas as pd
from datetime import datetime as dt
import sys # Import sys for exiting if all attempts fail

# Baseline and modified architectures
from impl.arch.stratix_10.fair.base import BaseArchFactory
from impl.arch.stratix_10.fair.lut_skip import LUTSkipArchFactory
from impl.arch.stratix_10.lut_skip_scratch3 import LUTSkip3ArchFactory


# Input sharing architectures
from impl.arch.stratix_10.sharing_1 import LUTSkipArchShare1
from impl.arch.stratix_10.sharing_2 import LUTSkipArchShare2
from impl.arch.stratix_10.sharing_3 import LUTSkipArchShare3
from impl.arch.stratix_10.sharing_4 import LUTSkipArchShare4

# Designs
# Conv-1D
from impl.design.conv_1d.fu import Conv1dFuDesign
from impl.design.conv_1d.pw import Conv1dPwDesign
# Conv-2D
from impl.design.conv_2d.fu import Conv2dFuDesign
from impl.design.conv_2d.rp import Conv2dRpDesign
from impl.design.conv_2d.pw import Conv2dPwDesign
# GEMM-T
from impl.design.gemmt.fu import GemmTFuDesign
from impl.design.gemmt.rp import GemmTRpDesign
# GEMM-S
from impl.design.gemms import GemmSDesign

# Plugins
from impl.plugin.shaxN import ShaxNPlugin

# Parameters
import runs.benchmarks.kratos_mini as mini
import runs.benchmarks.kratos as kratos

# Experiment
from impl.exp.vtr import VtrExperiment

# Runner and typing
from typing import Type
from structure.arch import ArchFactory
from structure.design import PluginDesign
from structure.plugin import Plugin

# Constants
import structure.consts.keys as keys

# utilities
from util.formatting import pretty

# Python libraries
import os.path as path
from copy import deepcopy

def add_vpr_seed(p, seed: int):
    exp = p[keys.KEY_EXP]
    args = list(exp.get('vpr_args', []))

    # remove any existing --seed <value>
    cleaned = []
    i = 0
    while i < len(args):
        if args[i] == '--seed':
            i += 2  # skip flag + value
            continue
        cleaned.append(args[i])
        i += 1

    cleaned += ['--seed', str(seed)]
    exp['vpr_args'] = cleaned
    return p


# Define base parameters
BASE_PARAMS = {
    keys.KEY_EXP: {
        'verilog_search_dir': path.join(path.dirname(path.realpath(__file__)), 'verilog'),
        'allow_skipping': True,
        'allow_skip_existing': True,
        'adder_cin_global': False,
        'soft_multiplier_adders': True,
        'route_chan_width': 400,
        'force_denser_packing': False,
        'target_ext_pin_util' : '0.9,0.9',
    },
    keys.KEY_ARCH: {
        # fixed architecture parameters for both baseline and explored
        'cin_mux_stride': 0,
        'enable_lut6': False,
    },
    keys.KEY_DESIGN: {
        'sparsity': 0,
        'data_width': 6,
    }
}

# Architecture mapping
ARCH_MAP = {
    'base_stratix': BaseArchFactory(),
    'base_dd5': LUTSkipArchFactory(),
    'fourshare': LUTSkipArchShare4(),
    'threeshare': LUTSkipArchShare3(),
    'twoshare': LUTSkipArchShare2(),
    'oneshare': LUTSkipArchShare1(),
    'exp' : LUTSkip3ArchFactory(),
}

# Design mapping (design_name -> (DesignClass, params_func))
DESIGN_MAP = {
    'Conv1dFu': (Conv1dFuDesign, mini.get_conv_1d_fu_params),
    'Conv1dPw': (Conv1dPwDesign, mini.get_conv_1d_pw_params),
    'Conv2dFu': (Conv2dFuDesign, mini.get_conv_2d_fu_params),
    'Conv2dRp': (Conv2dRpDesign, mini.get_conv_2d_rp_params),
    'Conv2dPw': (Conv2dPwDesign, mini.get_conv_2d_pw_params),
    'GemmTFu': (GemmTFuDesign, mini.get_gemmt_fu_params),
    'GemmTRp': (GemmTRpDesign, mini.get_gemmt_rp_params),
    'GemmS': (GemmSDesign, mini.get_gemms_params),
}

PLUGIN = ShaxNPlugin()
N_PARAM = 'sha_num'

# Base Stratix architecture for grid size determination (matches run_stress_test.py)
BASE_STRATIX_ARCH = ARCH_MAP['base_stratix']

def run_targeted_test(arch_name: str, design_name: str, sha_num: int, grid_size: tuple[int, int] = None, seed: int = 2345) -> dict:
    """
    Run a single targeted test with specified architecture, design, and SHA count.
    Includes logic for initial grid sizing based on BASE_STRATIX_ARCH.
    
    Args:
        arch_name: Architecture name (e.g., 'twoshare', 'base_stratix')
        design_name: Design name (e.g., 'Conv2dFu', 'GemmTFu')
        sha_num: Number of SHA instances to test
        grid_size: Optional (grid_w, grid_h) tuple. If None, runs with BASE_STRATIX_ARCH and 1 SHA to determine grid size (matching run_stress_test.py).
        seed: The VPR seed to use for this specific run.
    
    Returns:
        Dictionary of results from get_result(). Includes 'status' key.
        Raises ValueError if grid sizing fails.
    """
    # Get architecture
    if arch_name not in ARCH_MAP:
        raise ValueError(f"Unknown architecture: {arch_name}. Available: {list(ARCH_MAP.keys())}")
    arch = ARCH_MAP[arch_name]
    
    # Get design
    if design_name not in DESIGN_MAP:
        raise ValueError(f"Unknown design: {design_name}. Available: {list(DESIGN_MAP.keys())}")
    DesignClass, get_params_func = DESIGN_MAP[design_name]
    
    # Get base parameters
    base_params = get_params_func(BASE_PARAMS)
    
    # Determine grid size if not provided (using BASE_STRATIX_ARCH to match run_stress_test.py)
    # The sizing run itself also uses the current seed.
    current_grid_w, current_grid_h = 0, 0
    if grid_size is None:
        print(f"(!) Attempting initial sizing with seed {seed}...")
        sizing_params = deepcopy(base_params)
        sizing_params[keys.KEY_EXP]['root_dir'] = path.join(sizing_params[keys.KEY_EXP]['root_dir'], BASE_STRATIX_ARCH.__class__.__name__, f"sizing_seed_{seed}")
        sizing_params[keys.KEY_DESIGN][N_PARAM] = 1 # Always size with 1 SHA for baseline
        sizing_params = add_vpr_seed(sizing_params, seed)
        base_exp = VtrExperiment(BASE_STRATIX_ARCH, DesignClass(plugin=PLUGIN), sizing_params)
        
        try:
            base_exp.run()
            if base_exp.process:
                base_exp.process.wait()
            base_results = base_exp.get_result()
            current_grid_w, current_grid_h = base_results.get('gridx', 0), base_results.get('gridy', 0)
            if current_grid_w == 0 or current_grid_h == 0 or not base_results.get('status'):
                raise ValueError("Failed to determine grid size or sizing run failed.")
            print(f"(!) Sizing successful: {current_grid_w} x {current_grid_h}.")
            grid_size = (current_grid_w, current_grid_h) # Update grid_size for the main run
        except Exception as e:
            # If sizing fails, return a failed status or re-raise if you want it to halt immediately
            print(f"ERROR: Grid sizing failed for seed {seed}: {e}")
            return {'status': False, 'error': str(e), 'grid_size_used': None}
    else:
        current_grid_w, current_grid_h = grid_size
        print(f"(!) Using provided grid size {current_grid_w} x {current_grid_h}")
    
    # Prepare parameters for the actual test
    params = deepcopy(base_params)
    # Ensure a unique directory for each seed's run
    params[keys.KEY_EXP]['root_dir'] = path.join(params[keys.KEY_EXP]['root_dir'], arch.__class__.__name__, f"run_seed_{seed}")
    params[keys.KEY_ARCH]['fixed_size'] = (current_grid_w, current_grid_h) # Use the determined or provided grid size
    params[keys.KEY_DESIGN][N_PARAM] = sha_num
    params = add_vpr_seed(params, seed)
    
    # Run the experiment
    print(f"(!) Running {arch_name} with {design_name}, {sha_num} SHAs, seed {seed}...")
    exp = VtrExperiment(arch, DesignClass(plugin=PLUGIN), params)
    
    try:
        exp.run()
        if exp.process:
            exp.process.wait()
        
        # Get and return results
        results = exp.get_result()
        if not results.get('status'):
            print(f"Experiment for seed {seed} finished but reported failure status.")
        results['grid_size_used'] = (current_grid_w, current_grid_h)
        return results
    except Exception as e:
        print(f"ERROR: Experiment run for seed {seed} failed with exception: {e}")
        return {'status': False, 'error': str(e), 'grid_size_used': (current_grid_w, current_grid_h)}



def main():
    parser = argparse.ArgumentParser(
        description='Run a single targeted stress test with specified architecture, design, and SHA count.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python directed_stress_test.py twoshare Conv2dFu 10
  python directed_stress_test.py base_stratix GemmTFu 15 --grid-size 50 50
        """
    )
    
    parser.add_argument('architecture', 
                       choices=list(ARCH_MAP.keys()),
                       help='Architecture to test')
    parser.add_argument('design',
                       choices=list(DESIGN_MAP.keys()),
                       help='Design/benchmark to test')
    parser.add_argument('sha_num',
                       type=int,
                       help='Number of SHA instances')
    parser.add_argument('--grid-size', '--grid_size',
                       nargs=2,
                       type=int,
                       metavar=('W', 'H'),
                       help='Grid size (width height). If not provided, will determine automatically using 1 SHA.')
    parser.add_argument('--seed', type=int, default=2345,
                    help='VPR placer seed (passed as --seed). Default: 2345')
    parser.add_argument('--max-retries', type=int, default=3, # Total attempts will be 1 (initial) + max_retries
                    help='Maximum number of times to retry with incremented seed if a run fails. Default: 3 (total 4 attempts).')


    args = parser.parse_args()
    
    initial_seed = args.seed
    current_seed = initial_seed
    max_attempts = 1 + args.max_retries # Total attempts: initial + retries
    
    fixed_grid_size = None
    if args.grid_size:
        fixed_grid_size = tuple(args.grid_size)
    
    final_results = None
    seed_used_for_success = None

    for attempt_num in range(max_attempts):
        print(f"\n--- Attempt {attempt_num + 1}/{max_attempts} with seed {current_seed} ---")
        try:
            # Pass `fixed_grid_size` for all attempts. `run_targeted_test` will only determine it once
            # if `fixed_grid_size` is initially None, and then use that determined size for subsequent steps.
            # If a given grid_size was provided, it will use that for all attempts.
            results = run_targeted_test(
                args.architecture, 
                args.design, 
                args.sha_num, 
                grid_size=fixed_grid_size, # Pass fixed_grid_size here
                seed=current_seed
            )
            if fixed_grid_size is None and results and results.get('grid_size_used'):
                fixed_grid_size = tuple(results['grid_size_used'])
                print(f"(!) Caching grid size for retries: {fixed_grid_size[0]} x {fixed_grid_size[1]}")

            
            if results and results.get('status'):
                print(f"SUCCESS: Test for {args.architecture}/{args.design} with {args.sha_num} SHAs succeeded on seed {current_seed}!")
                final_results = results
                seed_used_for_success = current_seed
                break # Exit retry loop on success
            else:
                print(f"FAILURE: Test for {args.architecture}/{args.design} with {args.sha_num} SHAs failed on seed {current_seed}. Retrying...")
                if results and results.get('error'):
                    print(f"  Error details: {results['error']}")
        except Exception as e:
            print(f"CRITICAL FAILURE: An unexpected error occurred during attempt with seed {current_seed}: {e}. Retrying...")
        
        current_seed += 1 # Increment seed for the next attempt
    
    # --- Process final results (if any) ---
    if final_results:
        # Print results
        print("\n============= Final Results =============")
        print(f"Status: {final_results.get('status', 'unknown')}")
        print(f"Successful seed used: {seed_used_for_success}")
        
        print("\nKey metrics:")
        key_metrics = ['fmax', 'cpd', 'twl', 'gridx', 'gridy', 'clb', 'fle', 'lut5', 'adder']
        for metric in key_metrics:
            value = final_results.get(metric)
            if value is not None:
                print(f"  {metric:15s} = {value}")
        print("\nFull results:")
        pretty(final_results, 1)

        # Save results
        def make_results_dir(parent: str = "results") -> str:
            save_dir = path.join(parent, dt.now().strftime("%d%b%y-%H.%M.%S"))
            os.makedirs(save_dir, exist_ok=True)
            return save_dir

        def save_df(df, save_dir: str, name: str, suffix: str) -> None:
            df.to_csv(path.join(save_dir, f"{name}_{suffix}.csv"), index=False)

        df = pd.DataFrame([{
            "architecture": args.architecture,
            "design": args.design,
            "sha_num": args.sha_num,
            "seed": seed_used_for_success, # Use the successful seed
            **final_results,   # flatten the result dict into columns
        }])

        save_dir = make_results_dir("results")
        save_df(df, save_dir, f"{args.design}", f"{args.architecture}_raw")
        print(f"\nResults saved to {save_dir}")
    else:
        print(f"\n==========================================")
        print(f"All {max_attempts} attempts failed for {args.architecture}/{args.design} with {args.sha_num} SHAs. Giving up.")
        print(f"==========================================")
        sys.exit(1) # Exit with a non-zero code to indicate failure

if __name__ == '__main__':
    main()
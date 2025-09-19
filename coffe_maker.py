"""
This is a tool to generate a batch of COFFE input files for each permutation of architecture parameters.
"""

# Logging functions
def log(message: str) -> None:
    print(f"(!) {message}")
def log_error(message: str) -> None:
    print(f"[ERR] {message}")

import argparse
import os
import itertools
import pandas as pd
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('-m', '--arch_module', help="ArchFactory module to use. Currently supported: base, gen_exp", default='gen_exp')
parser.add_argument('-p', '--params_file', help="file containing newline separated parameters, intended for the ArchFactory. Each line should have <param>=<value_1>,<value_2>,... e.g., lut_size=3,4,5. You can also specify a range with a step, e.g., lut_size=2-6:2,9 = 2,4,6,9; 0.1-0.4:0.15 = 0.1,0.25,0.4. Note that float ranges will be rounded to 2 d.p.")
parser.add_argument('-o', '--output_dir', help="output directory to put new files in; created for you; defaults to 'coffe_maker_out'.", default='coffe_maker_out')
parser.add_argument('-r', '--record_filename', help=".csv record file name; defaults to 'record'.", default='record')
args = parser.parse_args()

params_file_path = args.params_file
if params_file_path is None or not os.path.exists(params_file_path):
    log_error("Please provide a valid parameter file with -p (or --params_file).")
    exit()

# get architecture
arch = None
if args.arch_module == 'base':
    from impl.arch.stratix_IV.base import BaseArchFactory
    arch = BaseArchFactory()
elif args.arch_module == 'gen_exp':
    from impl.arch.stratix_IV.gen_exp import GenExpArchFactory
    arch = GenExpArchFactory()
elif args.arch_module == 'gen_exp_fpop':
    from impl.arch.stratix_IV.gen_exp_fpop import GenExpFpopArchFactory
    arch = GenExpFpopArchFactory()
else:
    log_error(f"arch_module {args.arch_module} is not recognized.")
    exit()

def get_num(x: str) -> int | float:
    try:
        return int(x)
    except:
        try:
            return float(x)
        except:
            raise ValueError(f"Provided value {x} is neither an integer or a float.")

# parse parameter file
params_dict = {}
with open(params_file_path, 'r') as pf:
    for i, line in enumerate(pf.readlines()):
        def report_error(message):
            log_error(f"Error on line {i+1} of {params_file_path}: {message}")
            exit()

        line_split = line.strip().split('=')
        if len(line_split) != 2:
            report_error(f"not in recognizable format. (require <param>=<values>, got: {line})")

        param = line_split[0].strip()
        vals = line_split[1].strip().split(',')
        params_dict[param] = []

        for val in vals:
            val = val.strip()
            if '-' in val:
                # treat as range if possible
                step = 1
                if ':' in val:
                    val, step_str = val.split(':') 
                    step = get_num(step_str)

                val_split = val.split('-')
                if len(val_split) == 2:
                    l, r = get_num(val_split[0]), get_num(val_split[1])
                    
                    iterator = None
                    end = r + step
                    if isinstance(l, int) and isinstance(r, int) and isinstance(step, int):
                        iterator = range(l, end, step)
                    else:
                        iterator = [round(float(x), 2) for x in np.arange(l, end, step)]
                    [params_dict[param].append(x) for x in iterator]
                    continue
            try:
                # integer pass
                val = int(val)
            except:
                try:
                    # float pass
                    val = float(val)
                except:
                    pass
            
            params_dict[param].append(val)

log(f"Read the following parameters: {params_dict}")

# Generate all permutations
keys = params_dict.keys()
values = params_dict.values()

permutations = [dict(zip(keys, combination)) for combination in itertools.product(*values)]

# make directory and write
os.makedirs(args.output_dir, exist_ok=True)

# convert columns to record format
def convert_to_record(params):
    params = arch.verify_params(params)
    coffe_dict = arch.get_coffe_input_dict(**params)
    # translate metal layers to individual columns
    for i, (r, c) in enumerate(coffe_dict['metal']):
        coffe_dict[f'metal{i}'] = f'{r},{c}'
    # add metal layer count
    coffe_dict['metal_count'] = len(coffe_dict['metal'])
    # remove original metal key
    del coffe_dict['metal']
    # attach prefix to avoid clashing
    return params | { f'coffe_{k}': v for k, v in coffe_dict.items() }

# write record file
records = [convert_to_record(p) for p in permutations]
pd.DataFrame.from_records(records).to_csv(os.path.join(args.output_dir, f'{args.record_filename}.csv'))
log(f"Made record file with {len(permutations)} entr(ies).")
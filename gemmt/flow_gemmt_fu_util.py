# flow script V2.0
# uses design in tree mac for matrix multiplication, input are gisters instead of bram, available implementations: ['mm_reg_full']

from util import plot_result, gen_result_table, generate_flattened_bit, bark, reset_seed, check_and_fill_defaults
import os
import numpy as np
import re
from tabulate import tabulate

EXPERIMENT_ROOT_DIR = 'experiments/gemmt_fu'
EXPERIMENT_ROOT_DIR_VTR = 'experiments-vtr/gemmt_fu'
WRAPPER_DIR = 'wrapper/mm_reg_full'
MODULE_DIR = 'gemmt'
DEFAULT_WRAPPER_MODULE_NAME = 'mm_reg_full_wrapper'
REQUIRED_FIELDS = ['data_width', 'row_num', 'col_num', 'length']
DEFAULT_CLOCK_TIME = 1
# this python file's path
SEARCH_PATH = os.path.dirname(os.path.realpath(__file__))
DEFAULT_OUTPUT_DIR = 'outputs'
DEFAULT_STDOUT_FILE = 'std.out'
DEFAULT_STDERR_FILE = 'std.err'
DEFAULT_RESULT_DIR = 'results/gemmt_fu'
DEFAULT_PARALLEL_PROCESSORS = 4


def gen_exp_name(impl: str, data_width: int, row_num: int, col_num: int, length: int, **kwargs):
    if 'exp_name' in kwargs:
        return kwargs['exp_name']
    constant_weight = kwargs.get('constant_weight', True)
    sparsity = kwargs.get('sparsity', 0.0)
    return f'i.{impl}_d.{data_width}_r.{row_num}_c.{col_num}_l.{length}_c.{constant_weight}_s.{sparsity}'


def check_settings(kwargs):
    '''
    check if settings are valid
    and fill in default values, return the settings
    '''
    default = {'impl': 'mm_reg_full',
               'constant_weight': True,
               'sparsity': 0.0,
               'clock': 1,
               'module_dir': MODULE_DIR,
               'wrapper_module_name': DEFAULT_WRAPPER_MODULE_NAME}
    filled = check_and_fill_defaults(kwargs, REQUIRED_FIELDS, default)
    exp_name = gen_exp_name(**filled)
    filled['exp_name'] = exp_name
    filled['exp_dir'] = os.path.join(EXPERIMENT_ROOT_DIR, exp_name)
    filled['exp_dir_vtr'] = os.path.join(EXPERIMENT_ROOT_DIR_VTR, exp_name)
    filled['wrapper_file_name'] = filled.get('wrapper_file_name', os.path.join(WRAPPER_DIR, f'{exp_name}.v'))

    return filled


def gen_wrapper(impl, data_width, row_num, col_num, length, constant_weight, sparsity, module_dir, wrapper_module_name, **kwargs) -> str:
    '''
    Needed arguments:
    impl:str, implentation name, default: 'mm_bram_parallel', available: ['mm_bram_parallel']
    data_width:int, data width
    num_row:int, number of rows of result matrix
    num_col:int, number of columns of result matrix
    length:int, length of input matrix

    Optional arguments:
    constant_weight:bool, whether to use constant weight, default: True
    sparsity:float, sparsity of weight matrix, default: 0.0
    module_dir:str, directory of module, default: MODULE_DIR
    wrapper_module_name:str, name of wrapper module, default: DEFAULT_WRAPPER_MODULE_NAME

    Returns: str, wrapper module string
    '''

    template_inputx = 'input   logic  [DATA_WIDTH*LENGTH*COL_NUM-1:0]        weights ,'
    if constant_weight:
        inputx = ''
        reset_seed()
        arr_str = generate_flattened_bit(data_width, length*col_num, sparsity)
        constant_bits = f'localparam bit [DATA_WIDTH*LENGTH*COL_NUM-1:0] const_params = {arr_str};'
        x_in = 'const_params'
    else:
        inputx = template_inputx
        constant_bits = ''
        x_in = 'weights'

    template_top = f'''`include "{module_dir}/{impl}.v"

module {wrapper_module_name}
#(
    parameter DATA_WIDTH = {data_width},
    parameter ROW_NUM = {row_num},
    parameter COL_NUM = {col_num},
    parameter LENGTH = {length},
    // below are parameters not meant to be set manually
    parameter ROW_ADDR_WIDTH = $clog2(ROW_NUM),
    parameter COL_ADDR_WIDTH = $clog2(COL_NUM),
    parameter LENGTH_ADDR_WIDTH = $clog2(LENGTH)
)(
    input   logic                           clk,
    input   logic                           reset,

    {inputx}

    input   logic   [DATA_WIDTH*ROW_NUM*LENGTH-1:0]        mat_in,

    output  logic   [DATA_WIDTH*ROW_NUM*COL_NUM-1:0]        mat_out,

    // opaque
    input   logic    [7:0]                  opaque_in, 
    output  logic    [7:0]                  opaque_out 
);

    {constant_bits}

    {impl} #(DATA_WIDTH, ROW_NUM, COL_NUM, LENGTH) mm_reg_inst
    (
        .clk(clk),
        .reset(reset),
        .fil({x_in}),
        .mat(mat_in),
        .res(mat_out),
        .opaque_in(opaque_in),
        .opaque_out(opaque_out)
    );
    
endmodule
'''

    return template_top


def gen_sdc(**kwargs) -> str:
    '''
    Optional arguments:
    clock_time:int, clock time, default: DEFAULT_CLOCK_TIME
    '''
    clock = kwargs.get('clock', DEFAULT_CLOCK_TIME)
    template = f'create_clock -period {clock} [get_ports clk]'
    return template


def gen_tcl(wrapper_module_name, wrapper_file_name, **kwargs) -> str:
    '''
    Needed arguments:
    top_level_entity:str, top level entity name
    top_file:str, top level file name

    Optional arguments:
    search_path:str, search path, default: SEARCH_PATH
    output_dir:str, reports output directory, default: DEFAULT_OUTPUT_DIR
    parallel_processors_num:int, number of parallel processors, default: DEFAULT_PARALLEL_PROCESSORS

    Returns: str, tcl string
    '''

    search_path = kwargs.get('search_path', SEARCH_PATH)
    output_dir = kwargs.get('output_dir', DEFAULT_OUTPUT_DIR)
    parallel_processors_num = kwargs.get('parallel_processors_num', DEFAULT_PARALLEL_PROCESSORS)
    template = f'''# load packages
load_package flow

# new project
project_new -revision v1 -overwrite unrolled_mm_bram_parallel

# device
set_global_assignment -name FAMILY "Arria 10"
set_global_assignment -name DEVICE 10AX115H1F34I1SG

# misc
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY {output_dir}
set_global_assignment -name NUM_PARALLEL_PROCESSORS {parallel_processors_num}
set_global_assignment -name SDC_FILE flow.sdc

# seed
set_global_assignment -name SEED 114514

# files
set_global_assignment -name TOP_LEVEL_ENTITY {wrapper_module_name}
set_global_assignment -name SYSTEMVERILOG_FILE {wrapper_file_name}
set_global_assignment -name SEARCH_PATH {search_path}

# virtual pins
set_instance_assignment -name VIRTUAL_PIN ON -to clk
set_instance_assignment -name VIRTUAL_PIN ON -to reset

set_instance_assignment -name VIRTUAL_PIN ON -to weights[*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to mat_in[*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to mat_out[*][*][*]

set_instance_assignment -name VIRTUAL_PIN ON -to opaque_in[*]
set_instance_assignment -name VIRTUAL_PIN ON -to opaque_out[*]

# effort level
set_global_assignment -name OPTIMIZATION_MODE "HIGH PERFORMANCE EFFORT"

# run compilation
#execute_flow -compile
execute_flow -implement


# close project
project_close
'''

    return template


def gen_readme(impl: str, data_width: int, row_num: int, col_num: int, length: int,
               constant_weight: bool, sparsity: float, clock: float, extra_info: str = '', **kwargs) -> str:
    table = [
        ['implementation', impl],
        ['data width', data_width],
        ['row number', row_num],
        ['column number', col_num],
        ['length', length],
        ['constant input', str(constant_weight)],
        ['sparsity', sparsity],
        ['clock time', clock]
    ]
    table += [[k, v] for k, v in kwargs.items()]

    table_str = tabulate(table, tablefmt='rounded_grid')
    if extra_info == '' or extra_info is None:
        extra_info = 'Below is the parameter information for this flow:'
    return f"{extra_info}\n\n{table_str}"

# flow script V2.0
# uses design in systolic_ws for matrix multiplication, available implementations: ['systolic_ws']

from util import plot_result, gen_result_table, generate_random_matrix, bark, reset_seed, check_and_fill_defaults
import os
import numpy as np
import re
from tabulate import tabulate

EXPERIMENT_ROOT_DIR = 'experiments/gemms'
EXPERIMENT_ROOT_DIR_VTR = 'experiments-vtr/gemms'
WRAPPER_DIR = 'wrapper/systolic_ws'
MODULE_DIR = 'gemms'
DEFAULT_WRAPPER_MODULE_NAME = 'systolic_ws_wrapper'
REQUIRED_FIELDS = ['data_width', 'row_num', 'col_num', 'length']
DEFAULT_CLOCK_TIME = 1
# this python file's path
SEARCH_PATH = os.path.dirname(os.path.realpath(__file__))
DEFAULT_OUTPUT_DIR = 'outputs'
DEFAULT_STDOUT_FILE = 'std.out'
DEFAULT_STDERR_FILE = 'std.err'
DEFAULT_RESULT_DIR = 'results/gemms'
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
    default = {'impl': 'systolic_ws',
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
    Required arguments:
    impl:str, implentation name, default: 'systolic_ws', available: ['systolic_ws']
    data_width:int, data width
    num_row:int, number of rows of result matrix
    num_col:int, number of columns of result matrix
    length:int, length of input matrix
    constant_weight:bool, whether to use constant weight, default: True
    sparsity:float, sparsity of weight matrix, default: 0.0
    module_dir:str, directory of module, default: MODULE_DIR
    wrapper_module_name:str, name of wrapper module, default: DEFAULT_WRAPPER_MODULE_NAME

    Returns: str, wrapper module string
    '''

    template_inputx = 'input   logic   [DATA_WIDTH-1:0]        weights         [0:LENGTH-1][0:COL_NUM-1],'
    if constant_weight:
        inputx = ''
        reset_seed()
        arr_str = generate_random_matrix(row_num, length, data_width, sparsity)
        constant_bits = f'localparam bit [DATA_WIDTH-1:0] const_params [0:ROW_NUM-1][0:LENGTH-1] = {arr_str};'
        x_in = 'const_params'
    else:
        inputx = template_inputx
        constant_bits = ''
        x_in = 'x'

    template_top = f'''`include "{module_dir}/{impl}.v"
`include "vc/vc_sram.v"
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

    input   logic                           val_in,
    output  logic                           rdy_in,

    {inputx}

    input   logic   [DATA_WIDTH-1:0]        src_data_in     [0:LENGTH-1],
    input   logic   [ROW_ADDR_WIDTH-1:0]    src_wraddr      [0:LENGTH-1],
    input   logic                           src_wr_en       [0:LENGTH-1],

    input   logic  [ROW_ADDR_WIDTH-1:0]     result_rdaddr   [0:COL_NUM-1],
    output  logic  [DATA_WIDTH-1:0]         result_data_out [0:COL_NUM-1]
);


    {constant_bits}
    logic   [DATA_WIDTH-1:0]        src_data_out    [0:LENGTH-1];
    logic   [ROW_ADDR_WIDTH-1:0]    src_rdaddr      [0:LENGTH-1];

    logic   [DATA_WIDTH-1:0]        result_data_in  [0:COL_NUM-1];
    logic   [ROW_ADDR_WIDTH-1:0]    result_wraddr   [0:COL_NUM-1];
    logic                           result_wr_en    [0:COL_NUM-1];

    genvar i;
    generate
        for (i = 0; i < LENGTH; i = i + 1) begin
            vc_sram_1r1w #(DATA_WIDTH, ROW_NUM) src_sram_inst
            (
                .clk(clk),
                .data_in(src_data_in[i]),
                .data_out(src_data_out[i]),
                .rdaddress(src_rdaddr[i]),
                .wraddress(src_wraddr[i]),
                .wren(src_wr_en[i])
            );
        end

        for (i = 0; i < COL_NUM; i = i + 1) begin
            vc_sram_1r1w #(DATA_WIDTH, ROW_NUM) result_sram_inst
            (
                .clk(clk),
                .data_in(result_data_in[i]),
                .data_out(result_data_out[i]),
                .rdaddress(result_rdaddr[i]),
                .wraddress(result_wraddr[i]),
                .wren(result_wr_en[i])
            );
        end
    endgenerate

    {impl} #(DATA_WIDTH,ROW_NUM,COL_NUM,LENGTH) calc_inst
    (
        .clk(clk),
        .reset(reset),

        .val_in(val_in),
        .rdy_in(rdy_in),

        .weights({x_in}),

        .row_data_in(src_data_out),
        .row_rdaddr(src_rdaddr),

        .row_data_out(result_data_in),
        .row_wraddr(result_wraddr),
        .row_wr_en(result_wr_en)
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
    Required arguments:
    wrapper_module_name:str, top level entity name
    wrapper_file_name:str, top level file name

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
project_new -revision v1 -overwrite unrolled_systolic_ws

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


set_instance_assignment -name VIRTUAL_PIN ON -to val_in
set_instance_assignment -name VIRTUAL_PIN ON -to rdy_in
set_instance_assignment -name VIRTUAL_PIN ON -to weights[*][*][*]

set_instance_assignment -name VIRTUAL_PIN ON -to src_data_in[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to src_wraddr[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to src_wr_en[*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_rdaddr[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_data_out[*][*]


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

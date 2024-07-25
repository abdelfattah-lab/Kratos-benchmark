# flow script V2.0
# uses design in conv_reg for convolution, available implementations: ['conv_reg_full']

from util import plot_result, gen_result_table, generate_random_matrix_4d, bark, reset_seed, check_and_fill_defaults, gen_long_constant_bits
import os
import numpy as np
import re
from tabulate import tabulate

EXPERIMENT_ROOT_DIR = 'experiments/conv_2d_fu'
EXPERIMENT_ROOT_DIR_VTR = 'experiments-vtr/conv_2d_fu'
WRAPPER_DIR = 'wrapper/conv_reg_full'
MODULE_DIR = 'conv_2d'
DEFAULT_WRAPPER_MODULE_NAME = 'conv_reg_full_wrapper'
REQUIRED_FIELDS = ['data_width', 'img_w', 'img_h', 'img_d', 'fil_w', 'fil_h', 'res_d', 'stride_w', 'stride_h']
DEFAULT_CLOCK_TIME = 1
# this python file's path
SEARCH_PATH = os.path.dirname(os.path.realpath(__file__))
DEFAULT_OUTPUT_DIR = 'outputs'
DEFAULT_STDOUT_FILE = 'std.out'
DEFAULT_STDERR_FILE = 'std.err'
DEFAULT_RESULT_DIR = 'results/conv_2d_fu'
DEFAULT_PARALLEL_PROCESSORS = 4


def gen_exp_name(impl: str, data_width: int, img_w: int, img_h: int, img_d: int, fil_w: int, fil_h: int, res_d: int, stride_w: int, stride_h: int,
                 constant_weight: bool, sparsity: float, buffer_stages: int, separate_filters: bool, **kwargs):
    if 'exp_name' in kwargs:
        return kwargs['exp_name']
    return f'i.{impl}_d.{data_width}_w.{img_w}_h.{img_h}_d.{img_d}_fw.{fil_w}_fh.{fil_h}_rd.{res_d}_sw.{stride_w}_sh.{stride_h}_c.{constant_weight}_s.{sparsity}_bf.{buffer_stages}_sf.{separate_filters}'


def check_settings(kwargs):
    '''
    check if settings are valid
    and fill in default values, return the settings
    '''
    default = {'impl': 'conv_reg_full',
               #    'kernel_only': False,
               'separate_filters': False,
               'constant_weight': True,
               'sparsity': 0.0,
               'buffer_stages': 0,
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


def gen_wrapper(impl, data_width, img_w, img_h, img_d, fil_w, fil_h, res_d, stride_w, stride_h, constant_weight, sparsity, buffer_stages, separate_filters, module_dir, wrapper_module_name, **kwargs) -> str:
    template_inputx = 'input   logic    [DATA_WIDTH*FILTER_K*IMG_D*FILTER_H*FILTER_W-1:0]               fil,'
    if constant_weight:
        inputfil = ''
        reset_seed()
        if separate_filters:
            fil_k = res_d // img_d
        else:
            fil_k = res_d
        constant_bits = gen_long_constant_bits(fil_k * img_d * fil_h * fil_w * data_width, sparsity, 'FILTER_K*IMG_D*FILTER_H*FILTER_W*DATA_WIDTH', 'constfil')
        fil_in = 'constfil'
    else:
        inputfil = template_inputx
        constant_bits = ''
        fil_in = 'fil'

    if wrapper_module_name is None:
        wrapper_module_name = f'{impl}_wrapper'

    template = f'''`include "{module_dir}/{impl}.v"

module {wrapper_module_name}
#(
    parameter DATA_WIDTH = {data_width}, // data width
    parameter IMG_W = {img_w}, // image width
    parameter IMG_H = {img_h}, // image height
    parameter IMG_D = {img_d},  // image depth
    parameter FILTER_W = {fil_w}, // filter width
    parameter FILTER_H = {fil_h}, // filter height
    parameter RESULT_D = {res_d}, // filter numbers
    
    parameter STRIDE_W = {stride_w}, 
    parameter STRIDE_H = {stride_h}, 

    parameter buffer_stages = {buffer_stages}, // $clog2(FILTER_K / 8),
    // parameters below are not meant to be set manually
    // ==============================
    
    parameter RESULT_W = (IMG_W - FILTER_W) / STRIDE_W + 1,
    parameter RESULT_H = (IMG_H - FILTER_H) / STRIDE_H + 1,
    parameter FILTER_K = RESULT_D,

    // each BRAM stores one image channel, access addr = w + h * IMG_W
    parameter IMG_W_ADDR_WIDTH = $clog2(IMG_W),
    parameter IMG_H_ADDR_WIDTH = $clog2(IMG_H),
    parameter IMG_RAM_ADDR_WIDTH = $clog2(IMG_H),
    parameter IMG_D_ADDR_WIDTH = $clog2(IMG_D),
    
    // filters (weights) are provides from ports, and protocal is that weights should be kept same
    parameter FILTER_W_ADDR_WIDTH = $clog2(FILTER_W),
    parameter FILTER_H_ADDR_WIDTH = $clog2(FILTER_H),

    // each register stores one column of one result channel
    parameter RESULT_W_ADDR_WIDTH = $clog2(RESULT_W),
    parameter RESULT_H_ADDR_WIDTH = $clog2(RESULT_H),
    parameter RESULT_RAM_ADDR_WIDTH = $clog2(RESULT_W * RESULT_H)
)(
    // clock and reset
    input   logic                                           clk,
    input   logic                                           reset,
    // filters
    {inputfil}
    // image
    input   logic    [IMG_D*IMG_H*IMG_W*DATA_WIDTH-1:0]                     img_data_in,
    // results
    output  logic    [RESULT_D*RESULT_H*RESULT_W*DATA_WIDTH-1:0]            result_data_out,
    // opaque
    input   logic    [7:0]                                  opaque_in, 
    output  logic    [7:0]                                  opaque_out 
);

    // const fil
{constant_bits}

    {impl} #(DATA_WIDTH,IMG_W,IMG_H,IMG_D,FILTER_W,FILTER_H,RESULT_D,STRIDE_W,STRIDE_H,buffer_stages) conv_inst
    (
        .clk(clk),
        .reset(reset),

        .fil({fil_in}),
        .img_data_in(img_data_in),
        .result_data_out(result_data_out),
        .opaque_in(opaque_in),
        .opaque_out(opaque_out)
    );
endmodule
'''
    return template


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
project_new -revision v1 -overwrite unrolled_conv_reg_parallel

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


set_instance_assignment -name VIRTUAL_PIN ON -to fil[*][*][*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_data_in[*][*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_data_out[*][*][*][*]


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


def gen_readme(impl: str, data_width: int, img_w: int, img_h: int, img_d: int, fil_w: int, fil_h: int, res_d: int, stride_w: int, stride_h: int, buffer_stages: int, constant_weight: bool,
               sparsity: float, clock: float, extra_info: str = '', **kwargs) -> str:
    table = [
        ['implementation', impl],
        ['data width', data_width],
        ['img width', img_w],
        ['img height', img_h],
        ['img depth', img_d],
        ['filter width', fil_w],
        ['filter height', fil_h],
        ['result depth', res_d],
        ['stride width', stride_w],
        ['stride height', stride_h],
        ['buffer stages', buffer_stages],
        ['constant weight', constant_weight],
        ['sparsity', sparsity],
        ['clock', clock]
    ]
    table += [[k, v] for k, v in kwargs.items()]

    table_str = tabulate(table, tablefmt='rounded_grid')
    if extra_info == '' or extra_info is None:
        extra_info = 'Below is the parameter information for this flow:'
    return f"{extra_info}\n\n{table_str}"

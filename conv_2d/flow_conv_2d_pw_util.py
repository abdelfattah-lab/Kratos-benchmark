# flow script V2.0
# uses design in conv_bram_sr for convolution, available implementations: ['conv_bram_sr_fast']
# this uses data interleaving for better throughput
from util import gen_long_constant_bits, plot_result, gen_result_table, generate_flattened_bit, bark, reset_seed, check_and_fill_defaults
import os
import numpy as np
import re
from tabulate import tabulate

EXPERIMENT_ROOT_DIR = 'experiments/conv_2d_pw'
EXPERIMENT_ROOT_DIR_VTR = 'experiments-vtr/conv_2d_pw'
WRAPPER_DIR = 'wrapper/conv_bram_sr_fast'
MODULE_DIR = 'conv_2d'
DEFAULT_WRAPPER_MODULE_NAME = 'conv_bram_sr_fast_wrapper'
REQUIRED_FIELDS = ['data_width', 'img_w', 'img_h', 'img_d', 'fil_w', 'fil_h', 'res_d', 'stride_w', 'stride_h']
DEFAULT_CLOCK_TIME = 1
# this python file's path
SEARCH_PATH = os.path.dirname(os.path.realpath(__file__))
DEFAULT_OUTPUT_DIR = 'outputs'
DEFAULT_STDOUT_FILE = 'std.out'
DEFAULT_STDERR_FILE = 'std.err'
DEFAULT_RESULT_DIR = 'results/conv_2d_pw'
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
    default = {'impl': 'conv_bram_sr_fast',
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
    template_inputx = 'input   logic    [DATA_WIDTH*FILTER_K*IMG_D*FILTER_H*FILTER_W-1:0]               fil ,'
    if constant_weight:
        inputfil = ''
        reset_seed()
        if separate_filters:
            fil_k = res_d // img_d
        else:
            fil_k = res_d

        # divide the long contstant string into multiple small one so parser will work, maximum bits per const is 8192. (the actual limit of parmys is 16384)
        constant_bits = gen_long_constant_bits(fil_k * img_d * fil_h * fil_w * data_width, sparsity, 'FILTER_K*IMG_D*FILTER_H*FILTER_W*DATA_WIDTH', 'constfil')
        fil_in = 'constfil'
    else:
        inputfil = template_inputx
        constant_bits = ''
        fil_in = 'fil'

    if wrapper_module_name is None:
        wrapper_module_name = f'{impl}_wrapper'

    template = f'''`include "{module_dir}/{impl}.v"
`include "vc/vc_sram.v"
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
    parameter BUFFER_STAGES = {buffer_stages}, // number of pipeline stages in buffer

    // parameters below are not meant to be set manually
    // ==============================
    parameter RESULT_W = (IMG_W - FILTER_W) / STRIDE_W + 1,
    parameter RESULT_H = (IMG_H - FILTER_H) / STRIDE_H + 1,
    parameter FILTER_K = RESULT_D{'/ IMG_D' if separate_filters else ''},

    // each BRAM stores one image channel, access addr = w + h * IMG_W
    parameter IMG_W_ADDR_WIDTH = $clog2(IMG_W),
    parameter IMG_H_ADDR_WIDTH = $clog2(IMG_H),
    parameter IMG_RAM_ADDR_WIDTH = $clog2(IMG_W * IMG_H),
    parameter IMG_RAM_ADDR_WIDTH_PER_STRIPE = $clog2(IMG_W * IMG_H / FILTER_K),
    parameter IMG_D_ADDR_WIDTH = $clog2(IMG_D),
    
    // filters (weights) are provides from ports, and protocal is that weights should be kept same
    parameter FILTER_W_ADDR_WIDTH = $clog2(FILTER_W),
    parameter FILTER_H_ADDR_WIDTH = $clog2(FILTER_H),

    // each BRAM stores one result channel, access addr = w + h * RESULT_W
    parameter RESULT_W_ADDR_WIDTH = $clog2(RESULT_W),
    parameter RESULT_H_ADDR_WIDTH = $clog2(RESULT_H),
    parameter RESULT_RAM_ADDR_WIDTH = $clog2(RESULT_W * RESULT_H)
)
(
    // clock and reset
    input   logic                                           clk,
    input   logic                                           reset,
    // filters
    {inputfil}
    input   logic                                           val_in,
    output  logic                                           rdy_in,
    // images
    input   logic    [IMG_RAM_ADDR_WIDTH_PER_STRIPE*IMG_D*FILTER_W-1:0]    img_wraddress,
    input   logic    [DATA_WIDTH*IMG_D*FILTER_W-1:0]                       img_data_in  ,
    input   logic    [IMG_D*FILTER_W-1:0]                                  img_wren     ,

    // results
    input   logic    [RESULT_RAM_ADDR_WIDTH*RESULT_D-1:0]            result_rdaddress,
    output  logic    [DATA_WIDTH*RESULT_D-1:0]                       result_data_out  
);


    logic    [IMG_RAM_ADDR_WIDTH_PER_STRIPE*IMG_D*FILTER_W-1:0]        img_rdaddress  ;
    logic    [DATA_WIDTH*IMG_D*FILTER_W-1:0]                           img_data_out   ;

    logic    [RESULT_RAM_ADDR_WIDTH*RESULT_D-1:0]                result_wraddress;
    logic    [DATA_WIDTH*RESULT_D-1:0]                           result_data_in  ;
    logic    [RESULT_D-1:0]                                      result_wren     ;

{constant_bits} 

    genvar i;
    genvar j;
    generate
        for (i = 0; i < IMG_D; i = i + 1) begin
            for (j = 0; j < FILTER_W; j = j + 1) begin
                vc_sram_1r1w #(DATA_WIDTH, IMG_W * IMG_H / FILTER_K) sram_img
                (
                    .clk(clk),

                    .data_in(img_data_in[(i * FILTER_W + j + 1) * DATA_WIDTH - 1 : (i * FILTER_W + j) * DATA_WIDTH]),
                    .data_out(img_data_out[(i * FILTER_W + j + 1) * DATA_WIDTH - 1 : (i * FILTER_W + j) * DATA_WIDTH]),

                    .rdaddress(img_rdaddress[(i * FILTER_W + j + 1) * IMG_W_ADDR_WIDTH_PER_STRIPE - 1 : (i * FILTER_W + j) * IMG_W_ADDR_WIDTH_PER_STRIPE]),
                    .wraddress(img_wraddress[(i * FILTER_W + j + 1) * IMG_W_ADDR_WIDTH_PER_STRIPE - 1 : (i * FILTER_W + j) * IMG_W_ADDR_WIDTH_PER_STRIPE]),

                    .wren(img_wren[i * FILTER_W + j])
                );
            end
        end

        for (i = 0; i < RESULT_D; i = i + 1) begin
            vc_sram_1r1w #(DATA_WIDTH, RESULT_W * RESULT_H) sram_result
            (
                .clk(clk),

                .data_in(result_data_in[(i + 1) * DATA_WIDTH - 1 : i * DATA_WIDTH]),
                .data_out(result_data_out[(i + 1) * DATA_WIDTH - 1 : i * DATA_WIDTH]),

                .rdaddress(result_rdaddress[(i + 1) * RESULT_W_ADDR_WIDTH - 1 : i * RESULT_W_ADDR_WIDTH]),
                .wraddress(result_wraddress[(i + 1) * RESULT_W_ADDR_WIDTH - 1 : i * RESULT_W_ADDR_WIDTH]),

                .wren(result_wren[i])
            );
        end
    endgenerate


    {impl} #(DATA_WIDTH, IMG_W, IMG_H, IMG_D, FILTER_W, FILTER_H, RESULT_D, STRIDE_W, STRIDE_H, BUFFER_STAGES) 
    conv_inst
    (
        .clk(clk),
        .reset(reset),
        .fil({fil_in}),

        .val_in(val_in),
        .rdy_in(rdy_in),

        .img_rdaddress(img_rdaddress),
        .img_data_in(img_data_out),

        .result_wraddress(result_wraddress),
        .result_data_out(result_data_in),
        .result_wren(result_wren)
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

set_instance_assignment -name VIRTUAL_PIN ON -to fil[*][*][*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to val_in
set_instance_assignment -name VIRTUAL_PIN ON -to rdy_in

set_instance_assignment -name VIRTUAL_PIN ON -to img_rdaddress[*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_wraddress[*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_data_in[*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_data_out[*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_wren[*][*]



set_instance_assignment -name VIRTUAL_PIN ON -to result_rdaddress[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_wraddress[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_data_in[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_data_out[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_wren[*]


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

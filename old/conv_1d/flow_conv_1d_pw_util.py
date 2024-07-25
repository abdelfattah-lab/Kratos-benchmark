# flow script V2.0
# uses design in conv_bram_1d for 1D convolution, available implementations: ['conv_bram_1d']

from util import plot_result, gen_result_table, generate_flattened_bit, bark, reset_seed, check_and_fill_defaults, gen_long_constant_bits
import os
import numpy as np
import re
from tabulate import tabulate

EXPERIMENT_ROOT_DIR = 'experiments/conv_1d_pw'
EXPERIMENT_ROOT_DIR_VTR = 'experiments-vtr/conv_1d_pw'
WRAPPER_DIR = 'wrapper/conv_bram_1d'
MODULE_DIR = 'conv_1d'
DEFAULT_WRAPPER_MODULE_NAME = 'conv_bram_1d_wrapper'
REQUIRED_FIELDS = ['data_width', 'img_w', 'img_d', 'fil_w', 'res_d', 'stride_w']
DEFAULT_CLOCK_TIME = 1
# this python file's path
SEARCH_PATH = os.path.dirname(os.path.realpath(__file__))
DEFAULT_OUTPUT_DIR = 'outputs'
DEFAULT_STDOUT_FILE = 'std.out'
DEFAULT_STDERR_FILE = 'std.err'
DEFAULT_RESULT_DIR = 'results/conv_1d_pw'
DEFAULT_PARALLEL_PROCESSORS = 4


def gen_exp_name(impl: str, data_width: int, img_w: int, img_d: int, fil_w: int, res_d: int, stride_w: int, constant_weight: bool, sparsity: float, separate_filters: bool, **kwargs):
    if 'exp_name' in kwargs:
        return kwargs['exp_name']
    return f'i.{impl}_d.{data_width}_w.{img_w}_d.{img_d}_f.{fil_w}_r.{res_d}_s.{stride_w}_c.{constant_weight}_s.{sparsity}_sf.{separate_filters}'


def check_settings(kwargs):
    '''
    check if settings are valid
    and fill in default values, return the settings
    '''
    default = {'impl': 'conv_bram_1d',
               'separate_filters': False,
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


def gen_wrapper(impl, data_width, img_w, img_d, fil_w, res_d, stride_w, separate_filters, constant_weight, sparsity, module_dir, wrapper_module_name, **kwargs) -> str:
    '''
    Required arguments:
    impl:str, implentation name, default: 'conv_1d', available: ['conv_1d']
    data_width:int, data width
    img_w:int, image width
    img_d:int, image depth
    fil_w:int, filter width
    res_d:int, result depth
    stride_w:int, stride width
    separate_filters:bool, whether to do separate convolutions, default: False
    constant_weight:bool, whether the weight is constant
    sparsity:float, sparsity of the weight matrix

    Return: str, wrapper file content
    '''
    template_inputx = 'input   logic    [DATA_WIDTH-1:0]               fil                 [0:FILTER_K-1][0:IMG_D-1][0:FILTER_L-1],'
    if constant_weight:
        inputfil = ''
        if separate_filters:
            fil_k = res_d // img_d
        else:
            fil_k = res_d
        reset_seed()
        constant_bits = gen_long_constant_bits(res_d*img_d*fil_w*data_width, sparsity, 'DATA_WIDTH*FILTER_K*IMG_D*FILTER_L', 'constfil')
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
    parameter DATA_WIDTH = {data_width},
    parameter IMG_W = {img_w},
    parameter IMG_D = {img_d},
    // no IMG_H parameter because it is always 1
    parameter FILTER_L = {fil_w},
    parameter RESULT_D = {res_d},
    parameter STRIDE_W = {stride_w},

    // parameters below are not meant to be set manually
    // ==============================
    parameter RESULT_W = (IMG_W - FILTER_L) / STRIDE_W + 1,
    parameter FILTER_K = RESULT_D,

    parameter IMG_W_ADDR_WIDTH = $clog2(IMG_W),
    parameter IMG_RAM_ADDR_WIDTH = $clog2(IMG_W),

    parameter RESULT_W_ADDR_WIDTH = $clog2(RESULT_W),
    parameter RESULT_RAM_ADDR_WIDTH = $clog2(RESULT_W)
)(
    input   logic                                   clk,
    input   logic                                   reset,
    // filter
    {inputfil}
    input   logic                                   val_in,
    output  logic                                   rdy_in,
    
    // image
    input   logic   [DATA_WIDTH*IMG_D-1:0]               img_wrdata ,
    input   logic   [IMG_RAM_ADDR_WIDTH*IMG_D-1:0]       img_wraddr ,
    input   logic   [IMG_D-1:0]                          img_wren   ,

    // result
    input   logic   [RESULT_RAM_ADDR_WIDTH*RESULT_D-1:0]     result_rdaddr,
    output  logic   [DATA_WIDTH*RESULT_D-1:0]                result_rddata
);

    {constant_bits} 

    // inner wire
            logic   [IMG_RAM_ADDR_WIDTH*RESULT_D-1:0]        img_rdaddr    ;
            logic   [DATA_WIDTH*RESULT_D-1:0]                img_rddata    ;

            logic   [RESULT_RAM_ADDR_WIDTH*RESULT_D-1:0]     result_wraddr;
            logic   [DATA_WIDTH*RESULT_D-1:0]                result_wrdata;
            logic   [RESULT_D-1:0]                           result_wren  ;


    {impl} #(DATA_WIDTH,IMG_W,IMG_D,FILTER_L,RESULT_D,STRIDE_W) conv_1d_inst
    (
        .clk(clk),
        .reset(reset),
        .val_in(val_in),
        .rdy_in(rdy_in),
        .fil({fil_in}),

        .img_rdaddr(img_rdaddr),
        .img_rddata(img_rddata),

        .result_wraddr(result_wraddr),
        .result_wrdata(result_wrdata),
        .result_wren(result_wren)
    );

    // create sram for image and result

    genvar i;
    generate
        for(i = 0; i < IMG_D; i = i + 1) begin
            vc_sram_1r1w #(DATA_WIDTH, IMG_W) img_sram
            (
                .clk(clk),
                
                .data_out(img_rddata[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .rdaddress(img_rdaddr[(i+1)*IMG_RAM_ADDR_WIDTH-1:i*IMG_RAM_ADDR_WIDTH]),

                .data_in(img_wrdata[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .wraddress(img_wraddr[(i+1)*IMG_RAM_ADDR_WIDTH-1:i*IMG_RAM_ADDR_WIDTH]),
                .wren(img_wren[i:i])
            );
        end

        for(i = 0; i < RESULT_D; i = i + 1) begin
            vc_sram_1r1w #(DATA_WIDTH, RESULT_W) result_sram
            (
                .clk(clk),
                
                .data_out(result_rddata[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .rdaddress(result_rdaddr[(i+1)*RESULT_RAM_ADDR_WIDTH-1:i*RESULT_RAM_ADDR_WIDTH]),

                .data_in(result_wrdata[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .wraddress(result_wraddr[(i+1)*RESULT_RAM_ADDR_WIDTH-1:i*RESULT_RAM_ADDR_WIDTH]),
                .wren(result_wren[i:i])
            );
        end
    endgenerate



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


def gen_tcl(wrapper_module_name: str, wrapper_file_name: str, **kwargs) -> str:
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
project_new -revision v1 -overwrite unrolled_conv_bram_sr

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

set_instance_assignment -name VIRTUAL_PIN ON -to fil[*][*][*][*]


set_instance_assignment -name VIRTUAL_PIN ON -to img_rdaddr[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_rddata[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_wrdata[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_wraddr[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_wren[*]

set_instance_assignment -name VIRTUAL_PIN ON -to result_rdaddr[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_rddata[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_wrdata[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_wraddr[*][*]
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


def gen_readme(impl: str, data_width: int, img_w: int, img_d: int, fil_w: int, res_d: int, stride_w: int, constant_weight: bool,
               sparsity: float, clock: float, extra_info: str = '', **kwargs) -> str:
    table = [
        ['implementation', impl],
        ['data width', data_width],
        ['img width', img_w],
        ['img depth', img_d],
        ['filter width', fil_w],
        ['result depth', res_d],
        ['stride width', stride_w],
        ['constant input', constant_weight],
        ['sparsity', sparsity],
        ['clock', clock]
    ]
    table += [[k, v] for k, v in kwargs.items()]

    table_str = tabulate(table, tablefmt='rounded_grid')
    if extra_info == '' or extra_info is None:
        extra_info = 'Below is the parameter information for this flow:'
    return f"{extra_info}\n\n{table_str}"

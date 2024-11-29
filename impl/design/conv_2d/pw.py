from structure.design import PluginDesign
from structure.plugin import Plugin
from util.flow import reset_seed, gen_long_constant_bits
from structure.consts.shared_defaults import DEFAULTS_TCL, DEFAULTS_WRAPPER_CONV
from structure.consts.shared_requirements import REQUIRED_KEYS_CONV2D_STRIDE

from structure.consts.quartus import DEVICE_FAMILY, DEVICE_NAME, TURN_OFF_DSPS

import math

class Conv2dPwDesign(PluginDesign):
    """
    Conv-2D Pixel-wise design.
    """
    
    def __init__(self, impl: str = 'conv_bram_sr_fast', module_dir: str = 'conv_2d', wrapper_module_name: str = 'conv_bram_sr_fast_wrapper', plugin: Plugin|None = None):
        super().__init__(impl, module_dir, wrapper_module_name, plugin)

    def get_name(self, tree_base: int, data_width: int, img_w: int, img_h: int, img_d: int, fil_w: int, fil_h: int, res_d: int, stride_w: int, stride_h: int,
                    constant_weight: bool, sparsity: float, buffer_stages: int, separate_filters: bool, **kwargs):
        """
        Name generation 
        """
        plugin_name_insert = f"+{self.plugin.get_name(**kwargs)}" if not self.plugin is None else ""
        return f'i.{self.impl}{plugin_name_insert}_tb.{tree_base}_d.{data_width}_w.{img_w}_h.{img_h}_d.{img_d}_fw.{fil_w}_fh.{fil_h}_rd.{res_d}_sw.{stride_w}_sh.{stride_h}_c.{constant_weight}_s.{sparsity}_bf.{buffer_stages}_sf.{separate_filters}'

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Verification of parameters for Conv-2D Pixel-wise.
        """
        design_params = self.verify_required_keys(DEFAULTS_WRAPPER_CONV, REQUIRED_KEYS_CONV2D_STRIDE, params)

        if self.plugin is None:
            return design_params
        return self.plugin.check_params(design_params)

    def gen_tcl(self, wrapper_file_name: str, search_path: str, **kwargs) -> str:
        """
        Generate TCL file.

        Required arguments:
        wrapper_file_name:str, top level file name
        search_path:str, search path

        Optional arguments (defaults to DEFAULTS_TCL):
        output_dir:str, reports output directory
        parallel_processors_num:int, number of parallel processors
        execute_flow_type: 'compile' or 'implement' (prime only)
        """
        kwargs = self.autofill_defaults(DEFAULTS_TCL, kwargs)
        output_dir = kwargs['output_dir']
        parallel_processors_num = kwargs['parallel_processors_num']
        execute_flow_type = kwargs['execute_flow_type']
        template = f'''# load packages
load_package flow

# new project
project_new -revision v1 -overwrite unrolled_conv_bram_sr_fast

# device
set_global_assignment -name FAMILY "{DEVICE_FAMILY}"
set_global_assignment -name DEVICE {DEVICE_NAME}

# misc
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY {output_dir}
set_global_assignment -name NUM_PARALLEL_PROCESSORS {parallel_processors_num}
set_global_assignment -name SDC_FILE flow.sdc

# seed
set_global_assignment -name SEED 114514

# files
set_global_assignment -name TOP_LEVEL_ENTITY {self.wrapper_module_name}
set_global_assignment -name SYSTEMVERILOG_FILE {wrapper_file_name}
set_global_assignment -name SEARCH_PATH {search_path}

# virtual pins
set_instance_assignment -name VIRTUAL_PIN ON -to clk
set_instance_assignment -name VIRTUAL_PIN ON -to reset

set_instance_assignment -name VIRTUAL_PIN ON -to fil[*]
set_instance_assignment -name VIRTUAL_PIN ON -to val_in
set_instance_assignment -name VIRTUAL_PIN ON -to rdy_in

set_instance_assignment -name VIRTUAL_PIN ON -to img_wraddress[*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_data_in[*]
set_instance_assignment -name VIRTUAL_PIN ON -to img_wren[*]

set_instance_assignment -name VIRTUAL_PIN ON -to result_rdaddress[*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_data_out[*]


# effort level
set_global_assignment -name OPTIMIZATION_MODE "HIGH PERFORMANCE EFFORT"

# turn DSPs off
{TURN_OFF_DSPS}

# run compilation
execute_flow -{execute_flow_type}


# close project
project_close
'''

        return template
    
    def gen_wrapper(self, tree_base, data_width, img_w, img_h, img_d, fil_w, fil_h, res_d, stride_w, stride_h, constant_weight, sparsity, buffer_stages, separate_filters, **kwargs) -> str:
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

        has_plugin = self.plugin is not None
        plugin_includes = ""
        plugin_pins = ""
        plugin_module = ""

        if has_plugin:
            plugin_includes = self.plugin.get_includes(**kwargs)
            plugin_pins = self.plugin.get_pins(**kwargs)
            plugin_module = self.plugin.get_module('clk', **kwargs)

        template = f'''`include "{self.module_dir}/{self.impl}.v"
`include "vc/vc_sram.v"
{plugin_includes}

module {self.wrapper_module_name}
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
    
    parameter TREE_BASE = {tree_base},

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
    output  logic    [DATA_WIDTH*4*RESULT_D-1:0]                     result_data_out{',' if has_plugin else ''}

    {plugin_pins}
);
    localparam RES_WIDTH = DATA_WIDTH * 4;

    logic    [IMG_RAM_ADDR_WIDTH_PER_STRIPE*IMG_D*FILTER_W-1:0]        img_rdaddress  ;
    logic    [DATA_WIDTH*IMG_D*FILTER_W-1:0]                           img_data_out   ;

    logic    [RESULT_RAM_ADDR_WIDTH*RESULT_D-1:0]                result_wraddress;
    logic    [RES_WIDTH*RESULT_D-1:0]                            result_data_in  ;
    logic    [RESULT_D-1:0]                                      result_wren     ;

{constant_bits} 

    genvar i;
    genvar j;
    generate
        for (i = 0; i < IMG_D; i = i + 1) begin : img_d_block
            for (j = 0; j < FILTER_W; j = j + 1) begin : filter_w_block
                vc_sram_1r1w #(DATA_WIDTH, IMG_W * IMG_H / FILTER_K) sram_img
                (
                    .clk(clk),

                    .data_in(img_data_in[(i * FILTER_W + j + 1) * DATA_WIDTH - 1 : (i * FILTER_W + j) * DATA_WIDTH]),
                    .data_out(img_data_out[(i * FILTER_W + j + 1) * DATA_WIDTH - 1 : (i * FILTER_W + j) * DATA_WIDTH]),

                    .rdaddress(img_rdaddress[(i * FILTER_W + j + 1) * IMG_RAM_ADDR_WIDTH_PER_STRIPE - 1 : (i * FILTER_W + j) * IMG_RAM_ADDR_WIDTH_PER_STRIPE]),
                    .wraddress(img_wraddress[(i * FILTER_W + j + 1) * IMG_RAM_ADDR_WIDTH_PER_STRIPE - 1 : (i * FILTER_W + j) * IMG_RAM_ADDR_WIDTH_PER_STRIPE]),

                    .wren(img_wren[i * FILTER_W + j])
                );
            end
        end

        for (i = 0; i < RESULT_D; i = i + 1) begin : result_d_block
            vc_sram_1r1w #(RES_WIDTH, RESULT_W * RESULT_H) sram_result
            (
                .clk(clk),

                .data_in(result_data_in[(i + 1) * RES_WIDTH - 1 : i * RES_WIDTH]),
                .data_out(result_data_out[(i + 1) * RES_WIDTH - 1 : i * RES_WIDTH]),

                .rdaddress(result_rdaddress[(i + 1) * RESULT_W_ADDR_WIDTH - 1 : i * RESULT_W_ADDR_WIDTH]),
                .wraddress(result_wraddress[(i + 1) * RESULT_W_ADDR_WIDTH - 1 : i * RESULT_W_ADDR_WIDTH]),

                .wren(result_wren[i])
            );
        end
    endgenerate


    {self.impl} #(DATA_WIDTH, IMG_W, IMG_H, IMG_D, FILTER_W, FILTER_H, RESULT_D, STRIDE_W, STRIDE_H, BUFFER_STAGES, TREE_BASE) 
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

    {plugin_module}

endmodule
'''
        return template
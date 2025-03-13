from structure.design import PluginDesign
from structure.plugin import Plugin
from util.flow import reset_seed, gen_long_constant_bits
from util.bit_gen import gen_verilog_random_hex_constant
from structure.consts.shared_defaults import DEFAULTS_TCL, DEFAULTS_WRAPPER_CONV
from structure.consts.shared_requirements import REQUIRED_KEYS_CONV2D_STRIDE

from structure.consts.quartus import DEVICE_FAMILY, DEVICE_NAME, TURN_OFF_DSPS

import math

class Conv2dFuDesign(PluginDesign):
    """
    Conv-2D Fully Unrolled design.
    """

    def __init__(self, impl: str = 'conv_reg_full', module_dir: str = 'conv_2d', wrapper_module_name: str = 'conv_reg_full_wrapper', plugin: Plugin|None = None):
        super().__init__(impl, module_dir, wrapper_module_name, plugin)

    def get_name(self, tree_base: int, data_width: int, img_w: int, img_h: int, img_d: int, fil_w: int, fil_h: int, res_d: int, stride_w: int, stride_h: int,
                    constant_weight: bool, sparsity: float, buffer_stages: int, separate_filters: bool, **kwargs):
        """
        Name generation 
        """
        plugin_name_insert = f"+{self.plugin.get_name(**kwargs)}" if not self.plugin is None else ""
        return f'i.{self.impl}{plugin_name_insert}_tb.{tree_base}_d.{data_width}_w.{img_w}_h.{img_h}_d.{img_d}_fw.{fil_w}_fh.{fil_h}_rd.{res_d}_sw.{stride_w}_sh.{stride_h}_c.{constant_weight}_s.{sparsity}_bf.{buffer_stages}_sf.{separate_filters}'

    def get_formal_name(self) -> str:
        return "conv2d-FU"

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Verification of parameters for Conv-2D Fully Unrolled.
        """
        defaults = DEFAULTS_WRAPPER_CONV.copy()
        # remove unused keys
        del defaults['kernel_only']
        
        design_params = self.verify_required_keys(defaults, REQUIRED_KEYS_CONV2D_STRIDE, params)

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
project_new -revision v1 -overwrite unrolled_conv_reg_full

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
set_instance_assignment -name VIRTUAL_PIN ON -to img_data_in[*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_data_out[*]

set_instance_assignment -name VIRTUAL_PIN ON -to opaque_in[*]
set_instance_assignment -name VIRTUAL_PIN ON -to opaque_out[*]


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

        has_plugin = self.plugin is not None
        plugin_includes = ""
        plugin_pins = ""
        plugin_module = ""

        if has_plugin:
            plugin_includes = self.plugin.get_includes(**kwargs)
            plugin_pins = self.plugin.get_pins(**kwargs)
            plugin_module = self.plugin.get_module('clk', **kwargs)

        template = f'''`include "{self.module_dir}/{self.impl}.v"
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

    parameter buffer_stages = {buffer_stages}, // $clog2(FILTER_K / 8),

    parameter TREE_BASE = {tree_base},

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
    output  logic    [RESULT_D*RESULT_H*RESULT_W*DATA_WIDTH*4-1:0]          result_data_out,
    // opaque
    input   logic    [7:0]                                  opaque_in, 
    output  logic    [7:0]                                  opaque_out{',' if has_plugin else ''}

    {plugin_pins}
);

    // const fil
{constant_bits}

    {self.impl} #(DATA_WIDTH,IMG_W,IMG_H,IMG_D,FILTER_W,FILTER_H,RESULT_D,STRIDE_W,STRIDE_H,buffer_stages,TREE_BASE) conv_inst
    (
        .clk(clk),
        .reset(reset),

        .fil({fil_in}),
        .img_data_in(img_data_in),
        .result_data_out(result_data_out),
        .opaque_in(opaque_in),
        .opaque_out(opaque_out)
    );

    {plugin_module}
endmodule
'''
        return template
    
    def _get_data_sizes(self, data_width, img_w, img_h, img_d, fil_w, fil_h, res_d, stride_w, stride_h):
        data_in_size = data_width * img_d * img_w * img_h
        data_out_size = data_width * 4 * res_d * (int((img_w - fil_w) / stride_w) + 1) * (int((img_h - fil_h) / stride_h) + 1)

        return data_in_size, data_out_size

    def gen_tb_params(self, data_width, img_w, img_h, img_d, fil_w, fil_h, res_d, stride_w, stride_h, **kwargs):
        data_in_size, data_out_size = self._get_data_sizes(data_width, img_w, img_h, img_d, fil_w, fil_h, res_d, stride_w, stride_h)

        cycles = 1 + math.ceil(math.log2(fil_w * fil_h * img_d)) + 1
        return dict(
            cycles=dict(
                reset=cycles * 3,
                hold=cycles,
            ),
            pins=dict(
                clk='clk',
                input=[
                    ('img_data_in', data_in_size),
                ],
                output=[
                    ('result_data_out', data_out_size),
                ],
            )
        )        
    
    def gen_test_case(self, data_width, img_w, img_h, img_d, fil_w, fil_h, res_d, stride_w, stride_h, **kwargs):
        data_in_size, _ = self._get_data_sizes(data_width, img_w, img_h, img_d, fil_w, fil_h, res_d, stride_w, stride_h)
        return f"img_data_in = {gen_verilog_random_hex_constant(data_in_size)};"
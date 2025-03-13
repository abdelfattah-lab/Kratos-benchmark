from structure.design import PluginDesign
from structure.plugin import Plugin
from util.flow import reset_seed, generate_flattened_bit
from util.bit_gen import gen_verilog_random_hex_constant
from structure.consts.shared_defaults import DEFAULTS_TCL, DEFAULTS_WRAPPER
from structure.consts.shared_requirements import REQUIRED_KEYS_GEMM

from structure.consts.quartus import DEVICE_FAMILY, DEVICE_NAME, TURN_OFF_DSPS

import math

class GemmTFuDesign(PluginDesign):
    """
    GEMMT Fully Unrolled design.
    """

    def __init__(self, impl: str = 'mm_reg_full', module_dir: str = 'gemmt', wrapper_module_name: str = 'mm_reg_full_wrapper', plugin: Plugin|None = None):
        super().__init__(impl, module_dir, wrapper_module_name, plugin)

    def get_name(self, tree_base:int, data_width: int, row_num: int, col_num: int, length: int, constant_weight: bool = True, sparsity: float = 0.0, **kwargs):
        """
        Name generation 
        """
        plugin_name_insert = f"+{self.plugin.get_name(**kwargs)}" if not self.plugin is None else ""
        return f'i.{self.impl}{plugin_name_insert}_tb.{tree_base}_d.{data_width}_r.{row_num}_c.{col_num}_l.{length}_c.{constant_weight}_s.{sparsity}'

    def get_formal_name(self) -> str:
        return "gemmt-FU"

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Verification of parameters for GEMMT Fully Unrolled.
        """
        design_params = self.verify_required_keys(DEFAULTS_WRAPPER, REQUIRED_KEYS_GEMM, params)

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
project_new -revision v1 -overwrite unrolled_mm_reg_full

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

set_instance_assignment -name VIRTUAL_PIN ON -to weights[*]
set_instance_assignment -name VIRTUAL_PIN ON -to mat_in[*]
set_instance_assignment -name VIRTUAL_PIN ON -to mat_out[*]

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
    
    def gen_wrapper(self, tree_base, data_width, row_num, col_num, length, constant_weight, sparsity, **kwargs) -> str:
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
    parameter DATA_WIDTH = {data_width},
    parameter ROW_NUM = {row_num},
    parameter COL_NUM = {col_num},
    parameter LENGTH = {length},
    parameter TREE_BASE = {tree_base},
    // below are parameters not meant to be set manually
    parameter ROW_ADDR_WIDTH = $clog2(ROW_NUM),
    parameter COL_ADDR_WIDTH = $clog2(COL_NUM),
    parameter LENGTH_ADDR_WIDTH = $clog2(LENGTH)
)(
    input   logic                           clk,
    input   logic                           reset,

    {inputx}

    input   logic   [DATA_WIDTH*ROW_NUM*LENGTH-1:0]        mat_in,

    output  logic   [DATA_WIDTH*4*ROW_NUM*COL_NUM-1:0]        mat_out,

    // opaque
    input   logic    [7:0]                  opaque_in, 
    output  logic    [7:0]                  opaque_out{',' if has_plugin else ''}

    {plugin_pins}
);

    {constant_bits}

    {self.impl} #(DATA_WIDTH, ROW_NUM, COL_NUM, LENGTH, TREE_BASE) mm_reg_inst
    (
        .clk(clk),
        .reset(reset),
        .fil({x_in}),
        .mat(mat_in),
        .res(mat_out),
        .opaque_in(opaque_in),
        .opaque_out(opaque_out)
    );
    
    {plugin_module}
endmodule
'''

        return template
    
    def _get_mat_sizes(self, data_width, row_num, col_num, length):
        mat_in_size = data_width * row_num * length
        mat_out_size = data_width * 4 * row_num * col_num

        return mat_in_size, mat_out_size
    
    def gen_tb_params(self, data_width, row_num, col_num, length, **kwargs):
        mat_in_size, mat_out_size = self._get_mat_sizes(data_width, row_num, col_num, length)

        cycles = 1 + math.ceil(math.log2(length)) + 1
        return dict(
            cycles=dict(
                reset=cycles * 3,
                hold=cycles,
            ),
            pins=dict(
                clk='clk',
                input=[
                    ('mat_in', mat_in_size),
                ],
                output=[
                    ('mat_out', mat_out_size),
                ],
            )
        )
    
    def gen_test_case(self, data_width, row_num, col_num, length, **kwargs):
        mat_in_size, _ = self._get_mat_sizes(data_width, row_num, col_num, length)
        return f"mat_in = {gen_verilog_random_hex_constant(mat_in_size)};"
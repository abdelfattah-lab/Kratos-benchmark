from structure.design import PluginDesign
from structure.plugin import Plugin
from util.flow import reset_seed, generate_random_matrix
from structure.consts.shared_defaults import DEFAULTS_TCL, DEFAULTS_WRAPPER
from structure.consts.shared_requirements import REQUIRED_KEYS_GEMM

from structure.consts.quartus import DEVICE_FAMILY, DEVICE_NAME, TURN_OFF_DSPS

class GemmSDesign(PluginDesign):
    """
    GEMMS design.
    """
    
    def __init__(self, impl: str = 'systolic_ws', module_dir: str = 'gemms', wrapper_module_name: str = 'systolic_ws_wrapper', plugin: Plugin|None = None):
        super().__init__(impl, module_dir, wrapper_module_name, plugin)

    def get_name(self, data_width: int, row_num: int, col_num: int, length: int, constant_weight: bool = True, sparsity: float = 0.0, **kwargs):
        """
        Name generation 
        """
        plugin_name_insert = f"+{self.plugin.get_name(**kwargs)}" if not self.plugin is None else ""
        return f'i.{self.impl}{plugin_name_insert}_d.{data_width}_r.{row_num}_c.{col_num}_l.{length}_c.{constant_weight}_s.{sparsity}'

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Verification of parameters for GEMMS.
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
project_new -revision v1 -overwrite unrolled_systolic_ws

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

# turn DSPs off
{TURN_OFF_DSPS}

# run compilation
execute_flow -{execute_flow_type}


# close project
project_close
'''

        return template
    
    def gen_wrapper(self, data_width, row_num, col_num, length, constant_weight, sparsity, **kwargs) -> str:
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
    output  logic  [DATA_WIDTH*4-1:0]       result_data_out [0:COL_NUM-1]{',' if has_plugin else ''}

    {plugin_pins}
);
    localparam RES_WIDTH = DATA_WIDTH * 4;

    {constant_bits}
    logic   [DATA_WIDTH-1:0]        src_data_out    [0:LENGTH-1];
    logic   [ROW_ADDR_WIDTH-1:0]    src_rdaddr      [0:LENGTH-1];

    logic   [RES_WIDTH-1:0]         result_data_in  [0:COL_NUM-1];
    logic   [ROW_ADDR_WIDTH-1:0]    result_wraddr   [0:COL_NUM-1];
    logic                           result_wr_en    [0:COL_NUM-1];

    genvar i;
    generate
        for (i = 0; i < LENGTH; i = i + 1) begin : length_block
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

        for (i = 0; i < COL_NUM; i = i + 1) begin : col_num_block
            vc_sram_1r1w #(RES_WIDTH, ROW_NUM) result_sram_inst
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

    {self.impl} #(DATA_WIDTH,ROW_NUM,COL_NUM,LENGTH) calc_inst
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

    {plugin_module}
endmodule
'''

        return template
from structure.design import StandardizedSdcDesign
from util import reset_seed, generate_flattened_bit
from structure.consts.shared_defaults import DEFAULTS_TCL, DEFAULTS_WRAPPER
from structure.consts.shared_requirements import REQUIRED_KEYS_GEMM

class GemmTRpDesign(StandardizedSdcDesign):
    """
    GEMMT Row-Parallel design.
    """

    def __init__(self, impl: str = 'mm_bram', module_dir: str = 'gemmt_rp', wrapper_module_name: str = 'mm_bram_wrapper'):
        super().__init__(impl, module_dir, wrapper_module_name)

    def get_name(self, data_width: int, row_num: int, col_num: int, length: int, constant_weight: bool = True, sparsity: float = 0.0, **kwargs):
        """
        Name generation 
        """
        return f'i.{self.impl}_d.{data_width}_r.{row_num}_c.{col_num}_l.{length}_c.{constant_weight}_s.{sparsity}'

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Verification of parameters for GEMMT Row-Parallel.
        """
        return self.verify_required_keys(DEFAULTS_WRAPPER, REQUIRED_KEYS_GEMM, params)

    def gen_tcl(self, wrapper_file_name: str, search_path: str, **kwargs) -> str:
        """
        Generate TCL file.

        Required arguments:
        wrapper_file_name:str, top level file name
        search_path:str, search path

        Optional arguments (defaults to DEFAULTS_TCL):
        output_dir:str, reports output directory
        parallel_processors_num:int, number of parallel processors
        """
        kwargs = self.autofill_defaults(DEFAULTS_TCL, kwargs)
        output_dir = kwargs['output_dir']
        parallel_processors_num = kwargs['parallel_processors_num']
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
set_global_assignment -name TOP_LEVEL_ENTITY {self.wrapper_module_name}
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
    
    def gen_wrapper(self, data_width, row_num, col_num, length, constant_weight, sparsity, **kwargs) -> str:
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

        template = f'''`include "{self.module_dir}/{self.impl}.v"

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

    {inputx}

    input   logic   [DATA_WIDTH*ROW_NUM*LENGTH-1:0]        mat_in,

    output  logic   [DATA_WIDTH*ROW_NUM*COL_NUM-1:0]        mat_out,

    // opaque
    input   logic    [7:0]                  opaque_in, 
    output  logic    [7:0]                  opaque_out 
);

    {constant_bits}

    {self.impl} #(DATA_WIDTH, ROW_NUM, COL_NUM, LENGTH) mm_reg_inst
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

        return template
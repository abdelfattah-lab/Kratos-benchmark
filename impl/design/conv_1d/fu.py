from structure.design import StandardizedSdcDesign
from util import reset_seed, gen_long_constant_bits
from structure.consts.shared_defaults import DEFAULTS_TCL, DEFAULTS_WRAPPER_CONV
from structure.consts.shared_requirements import REQUIRED_KEYS_CONV1D_STRIDE

class Conv1dFuDesign(StandardizedSdcDesign):
    """
    Conv-1D Fully Unrolled design.
    """
    def get_name(self, impl: str, data_width: int, img_w: int, img_d: int, fil_w: int, res_d: int, stride_w: int, constant_weight: bool, sparsity: float, separate_filters: bool, **kwargs):
        """
        Name generation
        """
        return f'i.{impl}_d.{data_width}_w.{img_w}_d.{img_d}_f.{fil_w}_r.{res_d}_s.{stride_w}_c.{constant_weight}_s.{sparsity}_sf.{separate_filters}'

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Verification of parameters for Conv-1D Fully Unrolled.
        """
        defaults = DEFAULTS_WRAPPER_CONV.copy()
        #remove unused keys
        del defaults['kernel_only']
        del defaults['buffer_stages']

        return self.verify_required_keys(defaults, REQUIRED_KEYS_CONV1D_STRIDE, params)

    def gen_tcl(self, wrapper_module_name: str, wrapper_file_name: str, search_path: str, **kwargs) -> str:
        """
        Generate TCL file.

        Required arguments:
        wrapper_module_name:str, top level entity name
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


set_instance_assignment -name VIRTUAL_PIN ON -to fil[*][*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to lines_in[*][*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to lines_out[*][*][*]


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
    
    def gen_wrapper(self, impl, data_width, img_w, img_d, fil_w, res_d, stride_w, constant_weight, sparsity, buffer_stages, module_dir, wrapper_module_name, **kwargs) -> str:
        template_inputx = 'input   logic   [DATA_WIDTH*FILTER_K*IMG_D*FILTER_L-1:0]   weight,'
        if constant_weight:
            inputfil = ''
            reset_seed()
            fil_k = res_d
            constant_bits = gen_long_constant_bits(fil_k*img_d*fil_w*data_width, sparsity, 'DATA_WIDTH*FILTER_K*IMG_D*FILTER_L', 'constfil')

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
    input   logic                               clk,
    input   logic                               reset,

    // input   logic   [DATA_WIDTH-1:0]            weight      [0:FILTER_K-1][0:IMG_D-1][0:FILTER_L-1],
    {inputfil}
    input   logic   [DATA_WIDTH*IMG_D*IMG_W-1:0]            lines_in,

    output  logic   [DATA_WIDTH*RESULT_D*RESULT_W-1:0]      lines_out,

    input   logic   [7:0]                       opaque_in,
    output  logic   [7:0]                       opaque_out
);

    {constant_bits}

    conv_reg_1d_parallel #(DATA_WIDTH,IMG_W, IMG_D, FILTER_L, RESULT_D, STRIDE_W) conv_reg_inst
    (
        .clk(clk),
        .reset(reset),
        .weight({fil_in}),
        .lines_in(lines_in),
        .lines_out(lines_out),
        .opaque_in(opaque_in),
        .opaque_out(opaque_out)
    );


endmodule
'''
        return template
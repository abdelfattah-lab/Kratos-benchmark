from structure.design import StandardizedSdcDesign
from util import reset_seed, gen_long_constant_bits
from structure.consts.shared_defaults import DEFAULTS_TCL, DEFAULTS_WRAPPER_CONV
from structure.consts.shared_requirements import REQUIRED_KEYS_CONV2D_STRIDE

class Conv1dPwDesign(StandardizedSdcDesign):
    """
    Conv-1D Pixel-Wise design.
    """

    def __init__(self, impl: str = 'conv_bram_1d', module_dir: str = 'conv_1d', wrapper_module_name: str = 'conv_bram_1d_wrapper'):
        super().__init__(impl, module_dir, wrapper_module_name)

    def get_name(self, data_width: int, img_w: int, img_d: int, fil_w: int, res_d: int, stride_w: int,
                    constant_weight: bool, sparsity: float, buffer_stages: int, **kwargs):
        """
        Name generation 
        """
        return f'i.{self.impl}_d.{data_width}_w.{img_w}_d.{img_d}_fw.{fil_w}_rd.{res_d}_sw.{stride_w}_c.{constant_weight}_s.{sparsity}_bf.{buffer_stages}'

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Verification of parameters for Conv-1D Pixel-Wise.
        """
        defaults = DEFAULTS_WRAPPER_CONV.copy()
        #remove unused keys
        del defaults['kernel_only']
        del defaults['separate_filters']

        return self.verify_required_keys(defaults, REQUIRED_KEYS_CONV2D_STRIDE, params)
    
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
set_global_assignment -name TOP_LEVEL_ENTITY {self.wrapper_module_name}
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
    
    def gen_wrapper(self, data_width, img_w, img_d, fil_w, res_d, stride_w, separate_filters, constant_weight, sparsity, **kwargs) -> str:
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

        template = f'''`include "{self.module_dir}/{self.impl}.v"
`include "vc/vc_sram.v"
module {self.wrapper_module_name}
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


    {self.impl} #(DATA_WIDTH,IMG_W,IMG_D,FILTER_L,RESULT_D,STRIDE_W) conv_1d_inst
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
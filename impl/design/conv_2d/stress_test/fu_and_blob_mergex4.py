from structure.design import StandardizedSdcDesign
from util.flow import reset_seed, gen_long_constant_bits
from structure.consts.shared_defaults import DEFAULTS_TCL, DEFAULTS_WRAPPER_CONV
from structure.consts.shared_requirements import REQUIRED_KEYS_CONV2D_STRIDE

from structure.consts.quartus import DEVICE_FAMILY, DEVICE_NAME, TURN_OFF_DSPS

class Conv2dFuAndBlobMergex4Design(StandardizedSdcDesign):
    """
    Conv-2D Fully Unrolled design, with x4 instances of blob_merge benchmark (from https://docs.verilogtorouting.org/en/latest/vtr/benchmarks/) alongside.
    """

    def __init__(self, impl: str = 'conv_reg_full', module_dir: str = 'conv_2d', wrapper_module_name: str = 'conv_reg_full_and_blob_mergex4_wrapper'):
        super().__init__(impl, module_dir, wrapper_module_name)

    def get_name(self, tree_base: int, data_width: int, img_w: int, img_h: int, img_d: int, fil_w: int, fil_h: int, res_d: int, stride_w: int, stride_h: int,
                    constant_weight: bool, sparsity: float, buffer_stages: int, separate_filters: bool, **kwargs):
        """
        Name generation 
        """
        return f'i.{self.impl}+bmx4_tb.{tree_base}_d.{data_width}_w.{img_w}_h.{img_h}_d.{img_d}_fw.{fil_w}_fh.{fil_h}_rd.{res_d}_sw.{stride_w}_sh.{stride_h}_c.{constant_weight}_s.{sparsity}_bf.{buffer_stages}_sf.{separate_filters}'

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Verification of parameters for Conv-2D Fully Unrolled.
        """
        defaults = DEFAULTS_WRAPPER_CONV.copy()
        # remove unused keys
        del defaults['kernel_only']
        
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

        template = f'''`include "{self.module_dir}/{self.impl}.v"
`include "vtr_full_benchmarks/blob_merge.v"

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
    //common clock
    input logic clk,

    // Start: --- conv2d-FU I/O ---
    // reset
    input   logic                                           reset_conv2d,
    // filters
    {inputfil}
    // image
    input   logic    [IMG_D*IMG_H*IMG_W*DATA_WIDTH-1:0]                     img_data_in,
    // results
    output  logic    [RESULT_D*RESULT_H*RESULT_W*DATA_WIDTH*4-1:0]          result_data_out,
    // opaque
    input   logic    [7:0]                                  opaque_in, 
    output  logic    [7:0]                                  opaque_out,
    // End: --- conv2d-FU I/O ---

    // Start: --- blob_merge I/O ---
    input iReset_inst1,				//module reset signal
    input iReadFifoEmpty_inst1,		//fifo empty signal from input fifo
    input [127:0]iReadFifoData_inst1,	//data bus from input fifo [32b y-w., 32b x-w., 32 pixel-w.,10b length, 11b Y, 11b X]
    input iWriteFifoFull_inst1,		//fifo full signal from output fifo
    
    output  oReadFifoRequest_inst1,	//read request to input fifo
    output  [75:0]oWriteBlobData_inst1, //data bus to output fifo [10b index, 11b bb y, 11b bb x, 11b com y, 11b com x, 11b len y, 11b len x]
    output  oWriteRequest_inst1,		 //write request to output fifo
    output [10:0] oAvgSizeXaxis_inst1, //average size of X axis for detected BLOBs
    output [10:0] oAvgSizeYaxis_inst1,  //average size of Y axis for detected BLOBs

    input iReset_inst2,				//module reset signal
    input iReadFifoEmpty_inst2,		//fifo empty signal from input fifo
    input [127:0]iReadFifoData_inst2,	//data bus from input fifo [32b y-w., 32b x-w., 32 pixel-w.,10b length, 11b Y, 11b X]
    input iWriteFifoFull_inst2,		//fifo full signal from output fifo
    
    output  oReadFifoRequest_inst2,	//read request to input fifo
    output  [75:0]oWriteBlobData_inst2, //data bus to output fifo [10b index, 11b bb y, 11b bb x, 11b com y, 11b com x, 11b len y, 11b len x]
    output  oWriteRequest_inst2,		 //write request to output fifo
    output [10:0] oAvgSizeXaxis_inst2, //average size of X axis for detected BLOBs
    output [10:0] oAvgSizeYaxis_inst2,  //average size of Y axis for detected BLOBs
    
    input iReset_inst3,				//module reset signal
    input iReadFifoEmpty_inst3,		//fifo empty signal from input fifo
    input [127:0]iReadFifoData_inst3,	//data bus from input fifo [32b y-w., 32b x-w., 32 pixel-w.,10b length, 11b Y, 11b X]
    input iWriteFifoFull_inst3,		//fifo full signal from output fifo
    
    output  oReadFifoRequest_inst3,	//read request to input fifo
    output  [75:0]oWriteBlobData_inst3, //data bus to output fifo [10b index, 11b bb y, 11b bb x, 11b com y, 11b com x, 11b len y, 11b len x]
    output  oWriteRequest_inst3,		 //write request to output fifo
    output [10:0] oAvgSizeXaxis_inst3, //average size of X axis for detected BLOBs
    output [10:0] oAvgSizeYaxis_inst3,  //average size of Y axis for detected BLOBs
    
    input iReset_inst4,				//module reset signal
    input iReadFifoEmpty_inst4,		//fifo empty signal from input fifo
    input [127:0]iReadFifoData_inst4,	//data bus from input fifo [32b y-w., 32b x-w., 32 pixel-w.,10b length, 11b Y, 11b X]
    input iWriteFifoFull_inst4,		//fifo full signal from output fifo
    
    output  oReadFifoRequest_inst4,	//read request to input fifo
    output  [75:0]oWriteBlobData_inst4, //data bus to output fifo [10b index, 11b bb y, 11b bb x, 11b com y, 11b com x, 11b len y, 11b len x]
    output  oWriteRequest_inst4,		 //write request to output fifo
    output [10:0] oAvgSizeXaxis_inst4, //average size of X axis for detected BLOBs
    output [10:0] oAvgSizeYaxis_inst4  //average size of Y axis for detected BLOBs
    // End: --- blob_merge I/O ---
);

    // const fil
{constant_bits}

    {self.impl} #(DATA_WIDTH,IMG_W,IMG_H,IMG_D,FILTER_W,FILTER_H,RESULT_D,STRIDE_W,STRIDE_H,buffer_stages,TREE_BASE) conv_inst
    (
        .clk(clk),
        .reset(reset_conv2d),

        .fil({fil_in}),
        .img_data_in(img_data_in),
        .result_data_out(result_data_out),
        .opaque_in(opaque_in),
        .opaque_out(opaque_out)
    );
    
    RLE_BlobMerging blob_merge_inst1 
    (
        .clk(clk),
        .iReset(iReset_inst1),
        .iReadFifoEmpty(iReadFifoEmpty_inst1),
        .iReadFifoData(iReadFifoData_inst1),
        .iWriteFifoFull(iWriteFifoFull_inst1),		
        .oReadFifoRequest(oReadFifoRequest_inst1),
        .oWriteBlobData(oWriteBlobData_inst1), 
        .oWriteRequest(oWriteRequest_inst1),		
        .oAvgSizeXaxis(oAvgSizeXaxis_inst1), 
        .oAvgSizeYaxis(oAvgSizeYaxis_inst1)
    );

    RLE_BlobMerging blob_merge_inst2 
    (
        .clk(clk),
        .iReset(iReset_inst2),
        .iReadFifoEmpty(iReadFifoEmpty_inst2),
        .iReadFifoData(iReadFifoData_inst2),
        .iWriteFifoFull(iWriteFifoFull_inst2),		
        .oReadFifoRequest(oReadFifoRequest_inst2),
        .oWriteBlobData(oWriteBlobData_inst2), 
        .oWriteRequest(oWriteRequest_inst2),		
        .oAvgSizeXaxis(oAvgSizeXaxis_inst2), 
        .oAvgSizeYaxis(oAvgSizeYaxis_inst2)
    );

    RLE_BlobMerging blob_merge_inst3 
    (
        .clk(clk),
        .iReset(iReset_inst3),
        .iReadFifoEmpty(iReadFifoEmpty_inst3),
        .iReadFifoData(iReadFifoData_inst3),
        .iWriteFifoFull(iWriteFifoFull_inst3),		
        .oReadFifoRequest(oReadFifoRequest_inst3),
        .oWriteBlobData(oWriteBlobData_inst3), 
        .oWriteRequest(oWriteRequest_inst3),		
        .oAvgSizeXaxis(oAvgSizeXaxis_inst3), 
        .oAvgSizeYaxis(oAvgSizeYaxis_inst3)
    );

    RLE_BlobMerging blob_merge_inst4 
    (
        .clk(clk),
        .iReset(iReset_inst4),
        .iReadFifoEmpty(iReadFifoEmpty_inst4),
        .iReadFifoData(iReadFifoData_inst4),
        .iWriteFifoFull(iWriteFifoFull_inst4),		
        .oReadFifoRequest(oReadFifoRequest_inst4),
        .oWriteBlobData(oWriteBlobData_inst4), 
        .oWriteRequest(oWriteRequest_inst4),		
        .oAvgSizeXaxis(oAvgSizeXaxis_inst4), 
        .oAvgSizeYaxis(oAvgSizeYaxis_inst4)
    );
endmodule
'''
        return template
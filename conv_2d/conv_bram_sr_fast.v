`ifndef __CONV_BRAM_SR_FAST_V__
`define __CONV_BRAM_SR_FAST_V__

`include "conv_bram_sr/conv_bram_sr_fast_ctrl.v"
`include "conv_bram_sr/conv_bram_sr_fast_dpath.v"
module conv_bram_sr_fast
#(
    parameter DATA_WIDTH = 8, // data width
    parameter IMG_W = 8, // image width
    parameter IMG_H = 8, // image height
    parameter IMG_D = 4,  // image depth
    parameter FILTER_W = 3, // filter width
    parameter FILTER_H = 3, // filter height
    parameter RESULT_D = 8, // filter numbers
    
    parameter STRIDE_W = 1, 
    parameter STRIDE_H = 1,

    parameter buffer_stages = 5, // $clog2(FILTER_K / 8),

    // parameters below are not meant to be set manually
    // ==============================
    parameter RESULT_W = (IMG_W - FILTER_W) / STRIDE_W + 1,
    parameter RESULT_H = (IMG_H - FILTER_H) / STRIDE_H + 1,
    parameter FILTER_K = RESULT_D,

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
    // input   logic    [DATA_WIDTH-1:0]                       fil                 [0:FILTER_K-1][0:IMG_D-1][0:FILTER_H-1][0:FILTER_W-1],
    input   logic    [DATA_WIDTH*FILTER_K*IMG_D*FILTER_H*FILTER_W-1:0]                       fil,
    input   logic                                           val_in,
    output  logic                                           rdy_in,
    // images
    output  logic    [IMG_RAM_ADDR_WIDTH_PER_STRIPE*IMG_D*FILTER_W-1:0]    img_rdaddress,
    input   logic    [DATA_WIDTH*IMG_D*FILTER_W-1:0]                       img_data_in,
    // results
    output  logic    [RESULT_RAM_ADDR_WIDTH*RESULT_D-1:0]            result_wraddress,
    output  logic    [DATA_WIDTH*RESULT_D-1:0]                       result_data_out ,
    output  logic    [RESULT_D-1:0]                                  result_wren     
);

    localparam FILTER_L = FILTER_W;
    localparam FILTER_L_ADDR_WIDTH = FILTER_W_ADDR_WIDTH;


    logic    [IMG_RAM_ADDR_WIDTH_PER_STRIPE*FILTER_L-1:0]    img_rdaddr;

    logic                                   dpath_wren;
    logic                                   dpath_sum_en;
    logic    [FILTER_L_ADDR_WIDTH-1:0]      dpath_rotation_offset;
    logic    [RESULT_RAM_ADDR_WIDTH-1:0]    dpath_result_wraddr;

    logic    [FILTER_K-1:0]                  last_val ;

    genvar i,j;
    // assign input address
    for (i = 0; i < IMG_D; i = i + 1) begin

            assign img_rdaddress[(i+1)*FILTER_L*IMG_RAM_ADDR_WIDTH_PER_STRIPE-1:i*FILTER_L*IMG_RAM_ADDR_WIDTH_PER_STRIPE] = img_rdaddr;
 
    end

    conv_bram_sr_fast_ctrl #(DATA_WIDTH,IMG_W,IMG_H,IMG_D,FILTER_L,FILTER_K,STRIDE_W,STRIDE_H) conv_bram_sr_fast_ctrl_inst (
        .clk(clk),
        .reset(reset),

        .val_in(val_in),
        .rdy_in(rdy_in),

        .img_rdaddr(img_rdaddr),
        .dpath_wren(dpath_wren),
        .dpath_sum_en(dpath_sum_en),

        .dpath_rotation_offset(dpath_rotation_offset),
        .dpath_result_wraddr(dpath_result_wraddr),
        .last_val(last_val[0])
    );

    genvar k;
    generate
        for (k = 0; k < FILTER_K; k = k + 1) begin
        conv_bram_sr_fast_dpath #(DATA_WIDTH,IMG_W,IMG_H,IMG_D,FILTER_L,FILTER_K,STRIDE_W,STRIDE_H) conv_bram_sr_fast_dpath_inst (
            .clk(clk),
            .reset(reset),

            .dpath_wren(dpath_wren),
            .dpath_sum_en(dpath_sum_en),
            .dpath_rotation_offset(dpath_rotation_offset),

            .dpath_result_wraddr(dpath_result_wraddr),

            .last_val(last_val[k]),

            .fil(fil[(k+1)*DATA_WIDTH*IMG_D*FILTER_L*FILTER_L-1:k*DATA_WIDTH*IMG_D*FILTER_L*FILTER_L]),

            .img_data_in(img_data_in),

            .result_data_out(result_data_out[(k+1) * DATA_WIDTH - 1:k * DATA_WIDTH]),
            .result_wraddress(result_wraddress[(k+1) * RESULT_RAM_ADDR_WIDTH - 1:k * RESULT_RAM_ADDR_WIDTH]),
            .result_wren(result_wren[k:k])
        );
        end
    endgenerate

endmodule

`endif
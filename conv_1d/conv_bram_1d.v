`ifndef __CONV_1D_V__
`define __CONV_1D_V__

`include "conv_1d/conv_bram_1d_dpath.v"
`include "conv_1d/conv_bram_1d_ctrl.v"
module conv_bram_1d
#(
    parameter DATA_WIDTH = 8,
    parameter IMG_W = 32,
    parameter IMG_D = 4,
    // no IMG_H parameter because it is always 1
    parameter FILTER_L = 3,
    parameter RESULT_D = 4,
    parameter STRIDE_W = 1,

    // parameters below are not meant to be set manually
    // ==============================
    parameter RESULT_W = (IMG_W - FILTER_L) / STRIDE_W + 1,
    parameter FILTER_K = RESULT_D,

    parameter IMG_W_ADDR_WIDTH = $clog2(IMG_W),
    parameter IMG_RAM_ADDR_WIDTH = $clog2(IMG_W),

    parameter RESULT_W_ADDR_WIDTH = $clog2(RESULT_W),
    parameter RESULT_RAM_ADDR_WIDTH = $clog2(RESULT_W)
)(
    input   logic                                               clk,
    input   logic                                               reset,
    // filter
    input   logic   [DATA_WIDTH*FILTER_K*IMG_D*FILTER_L-1:0]    fil,
    input   logic                                               val_in,
    output  logic                                               rdy_in,
    // image
    output  logic   [IMG_RAM_ADDR_WIDTH*IMG_D-1:0]              img_rdaddr,
    input   logic   [DATA_WIDTH*IMG_D-1:0]                      img_rddata,
    // result
    output  logic   [RESULT_RAM_ADDR_WIDTH*RESULT_D-1:0]        result_wraddr,
    output  logic   [DATA_WIDTH*RESULT_D-1:0]                   result_wrdata,
    output  logic   [RESULT_D-1:0]                              result_wren
);

    logic                                   dpath_sr_wren;
    logic   [RESULT_RAM_ADDR_WIDTH-1:0]     dpath_result_wraddr;
    logic                                   dpath_result_wren;
    logic   [FILTER_K-1:0]                  last_val;

    logic   [IMG_RAM_ADDR_WIDTH-1:0]        img_rdaddr_dup;

    conv_bram_1d_ctrl #(DATA_WIDTH,IMG_W,IMG_D,FILTER_L,RESULT_D, STRIDE_W) conv_1d_ctrl_inst
    (
        .clk(clk),
        .reset(reset),
        .val_in(val_in),
        .rdy_in(rdy_in),
        .img_rdaddr(img_rdaddr_dup),
        .dpath_sr_wren(dpath_sr_wren),
        .dpath_result_wraddr(dpath_result_wraddr),
        .dpath_result_wren(dpath_result_wren),
        .last_val(last_val[0:0])
    );

    genvar i;
    generate
        for(i = 0; i < IMG_D; i = i + 1) begin
            assign img_rdaddr[(i+1)*IMG_RAM_ADDR_WIDTH-1:i*IMG_RAM_ADDR_WIDTH] = img_rdaddr_dup;
        end
        for(i = 0; i < FILTER_K; i = i + 1) begin
            conv_bram_1d_dpath #(DATA_WIDTH,IMG_W,IMG_D,FILTER_L,RESULT_D, STRIDE_W) conv_1d_dpath_inst
            (
                .clk(clk),
                .reset(reset),
                .fil(fil[(i+1)*DATA_WIDTH*IMG_D*FILTER_L-1:i*DATA_WIDTH*IMG_D*FILTER_L]),
                .img_rddata(img_rddata),

                .dpath_sr_wren(dpath_sr_wren),
                .dpath_result_wraddr(dpath_result_wraddr),
                .dpath_result_wren(dpath_result_wren),
                .last_val(last_val[i:i]),

                .result_wraddr(result_wraddr[(i+1)*RESULT_RAM_ADDR_WIDTH-1:i*RESULT_RAM_ADDR_WIDTH]),
                .result_wrdata(result_wrdata[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .result_wren(result_wren[i:i])
            );
        end
    endgenerate


endmodule

`endif
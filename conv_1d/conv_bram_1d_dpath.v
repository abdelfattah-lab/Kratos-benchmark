`ifndef __CONV_1D_DPATH_V__
`define __CONV_1D_DPATH_V__

`include "tree_mac/multiply_core_evo.v"
`include "vc/vc_shiftregisters.v"
module conv_bram_1d_dpath
#(
    parameter DATA_WIDTH = 8,
    parameter IMG_W = 32,
    parameter IMG_D = 8,
    // no IMG_H parameter because it is always 1
    parameter FILTER_L = 3,
    parameter RESULT_D = 8,
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
    input   logic                                   clk,
    input   logic                                   reset,
    // weights
    input   logic   [DATA_WIDTH*IMG_D*FILTER_L-1:0]        fil,
    // image
    input   logic   [DATA_WIDTH*IMG_D-1:0]                img_rddata,
    // control
    input   logic                                   dpath_sr_wren,
    input   logic   [RESULT_RAM_ADDR_WIDTH-1:0]     dpath_result_wraddr,
    input   logic                                   dpath_result_wren,
    output  logic                                   last_val,
    // result
    output  logic   [RESULT_RAM_ADDR_WIDTH-1:0]     result_wraddr,
    output  logic   [DATA_WIDTH-1:0]                result_wrdata,
    output  logic                                   result_wren
);

    logic   [DATA_WIDTH*IMG_D*FILTER_L-1:0] window_data_flattened;
    logic   [IMG_D-1:0] en_dup;

    genvar i, j, k;
    generate
        // assign duplicated enable signal
        for(i = 0; i < IMG_D; i = i + 1) begin
            assign en_dup[i:i] = dpath_sr_wren;
        end
    endgenerate


    vc_shiftregisters_2d_ar #(DATA_WIDTH, IMG_D, FILTER_L) window_data_sr
    (
        .clk(clk),
        .reset(reset),
        .data_in(img_rddata),
        .en(en_dup),
        .val_in(1),
        .data_out(window_data_flattened),
        .val_out()
    );

    multiply_core_evo #(DATA_WIDTH, IMG_D * FILTER_L) multiply_core_inst
    (
        .clk(clk),
        .reset(reset),
        .row(window_data_flattened),
        .col(fil),
        .sum_out(result_wrdata)
    );

    multiply_core_evo_chain #(RESULT_RAM_ADDR_WIDTH, IMG_D * FILTER_L) addr_chain_inst
    (
        .clk(clk),
        .reset(reset),
        .in(dpath_result_wraddr),
        .out(result_wraddr)
    );

    multiply_core_evo_chain #(1, IMG_D * FILTER_L) val_chain_inst
    (
        .clk(clk),
        .reset(reset),
        .in(dpath_result_wren),
        .out(result_wren)
    );

    assign last_val = result_wren && (result_wraddr == RESULT_W - 1);

endmodule

`endif
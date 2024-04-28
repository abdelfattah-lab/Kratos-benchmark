`ifndef __CONV_BRAM_SR_FAST_DPATH_V__
`define __CONV_BRAM_SR_FAST_DPATH_V__


`include "vc/vc_shiftregisters.v"
`include "vc/vc_mac.v"
`include "vc/vc_rotation_mux.v"
`include "tree_mac/multiply_core_evo.v"
module conv_bram_sr_fast_dpath
#(
    parameter DATA_WIDTH = 12, // data width
    parameter IMG_W = 16, // image width
    parameter IMG_H = 16, // image height
    parameter IMG_D = 32,  // image depth
    parameter FILTER_L = 3, // filter length, we assume the filter is square
    parameter FILTER_K = 8, // filter numbers
    
    parameter STRIDE_W = 1, // stride alone width
    parameter STRIDE_H = 1, // stride alone height

    // parameters below are not meant to be set manually
    // ==============================
    parameter RESULT_W = (IMG_W - FILTER_L) / STRIDE_W + 1,
    parameter RESULT_H = (IMG_H - FILTER_L) / STRIDE_H + 1,
    parameter RESULT_D = FILTER_K,

    // each BRAM stores one image channel, access addr = w + h * IMG_W
    parameter IMG_W_ADDR_WIDTH = $clog2(IMG_W),
    parameter IMG_H_ADDR_WIDTH = $clog2(IMG_H),
    parameter IMG_RAM_ADDR_WIDTH = $clog2(IMG_W * IMG_H),
    parameter IMG_RAM_ADDR_WIDTH_PER_STRIPE = $clog2(IMG_W * IMG_H / FILTER_K),
    parameter IMG_D_ADDR_WIDTH = $clog2(IMG_D),
    
    // this is used to tell data kernel which register to fill in data.
    parameter FILTER_L_ADDR_WIDTH = $clog2(FILTER_L),
    parameter FILTER_RAM_ADDR_WIDTH = $clog2(FILTER_L * FILTER_L),

    // each BRAM stores one result channel, access addr = w + h * RESULT_W
    parameter RESULT_W_ADDR_WIDTH = $clog2(RESULT_W),
    parameter RESULT_H_ADDR_WIDTH = $clog2(RESULT_H),
    parameter RESULT_RAM_ADDR_WIDTH = $clog2(RESULT_W * RESULT_H)
)(
    // clock and reset
    input   logic                                   clk,
    input   logic                                   reset,


    // from control

    input   logic                                   dpath_wren,
    input   logic                                   dpath_sum_en,
    input   logic    [FILTER_L_ADDR_WIDTH-1:0]      dpath_rotation_offset,

    input   logic    [RESULT_RAM_ADDR_WIDTH-1:0]    dpath_result_wraddr,

    output  logic                                   last_val,

    //weight
    // input   logic    [DATA_WIDTH-1:0]               weights             [0:IMG_D-1][0:FILTER_L-1][0:FILTER_L-1],
    input   logic    [DATA_WIDTH*IMG_D*FILTER_L*FILTER_L-1:0]       fil,
    // from source image
    input   logic    [DATA_WIDTH*IMG_D*FILTER_L-1:0]   img_data_in ,

    // to result image
    output  logic    [DATA_WIDTH-1:0]               result_data_out,
    output  logic    [RESULT_RAM_ADDR_WIDTH-1:0]    result_wraddress,
    output  logic                                   result_wren
);
    
    genvar i, j, k;

    logic [FILTER_L-1:0] dpath_wren_dup;
    generate
        for (i = 0; i < FILTER_L; i = i + 1) begin
            assign dpath_wren_dup[i] = dpath_wren;
        end
    endgenerate



    logic [DATA_WIDTH*IMG_D*FILTER_L*FILTER_L-1:0] sr_data_out_flattened;

    generate
        for (i = 0; i < IMG_D; i = i + 1) begin
            logic    [DATA_WIDTH*FILTER_L-1:0]               img_data_regularized;
            logic    [DATA_WIDTH*FILTER_L*FILTER_L-1:0]       sr_data_out;
            vc_rotation_mux_back_comb #(DATA_WIDTH, FILTER_L) data_in_rotation_mux
            (
                .data_in(img_data_in[(i+1)*DATA_WIDTH*FILTER_L-1:i*DATA_WIDTH*FILTER_L]),
                .data_out(img_data_regularized),
                .addr_in(dpath_rotation_offset)
            );
            vc_shiftregisters_2d_ar #(DATA_WIDTH, FILTER_L, FILTER_L) sr_2d
            (
                .clk(clk),
                .reset(reset),

                .data_in(img_data_regularized),
                .en(dpath_wren_dup),
                .val_in(),

                .data_out(sr_data_out),
                .val_out()
            );
            
            assign sr_data_out_flattened[(i+1)*DATA_WIDTH*FILTER_L*FILTER_L-1:i*DATA_WIDTH*FILTER_L*FILTER_L] = sr_data_out;

        end
    endgenerate


    multiply_core_evo_withaddr #(DATA_WIDTH, FILTER_L*FILTER_L*IMG_D, RESULT_RAM_ADDR_WIDTH, 1) mul
    (
        .clk(clk),
        .reset(reset),

        .row(sr_data_out_flattened),
        .col(fil),

        .addr_i_in(dpath_result_wraddr),
        .addr_k_in(),
        .val_in(dpath_wren),

        .sum_out(result_data_out),
        .addr_i_out(result_wraddress),
        .addr_k_out(),
        .val_out(result_wren)
    );

    assign last_val = result_wren && (result_wraddress == RESULT_W * RESULT_H - 1);
endmodule
`endif
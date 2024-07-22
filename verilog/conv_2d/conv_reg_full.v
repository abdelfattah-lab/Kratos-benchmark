`ifndef __CONV_REG_FULL_V__
`define __CONV_REG_FULL_V__

`include "tree_mac/multiply_core_evo.v"
module conv_reg_full
#(
    parameter DATA_WIDTH = 8, // data width
    parameter IMG_W = 8, // image width
    parameter IMG_H = 8, // image height
    parameter IMG_D = 2,  // image depth
    parameter FILTER_W = 3, // filter width
    parameter FILTER_H = 3, // filter height
    parameter RESULT_D = 4, // filter numbers
    
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
    // clock and reset
    input   logic                                                           clk,
    input   logic                                                           reset,
    // filters
    input   logic    [FILTER_K*IMG_D*FILTER_H*FILTER_W*DATA_WIDTH-1:0]      fil,
    // image
    input   logic    [IMG_D*IMG_H*IMG_W*DATA_WIDTH-1:0]                     img_data_in,
    // results
    output  logic    [RESULT_D*RESULT_H*RESULT_W*DATA_WIDTH-1:0]            result_data_out,
    // opaque
    input   logic    [7:0]                                                  opaque_in, 
    output  logic    [7:0]                                                  opaque_out 
);

    localparam data_length_per_filter = FILTER_W * FILTER_H * IMG_D;


    genvar resd, resh, resw, i, j, k, l;
    // fully pipelined, generate multiply cores for each result
    generate
        for (resd = 0; resd < RESULT_D; resd = resd + 1) begin
            for (resh = 0; resh < RESULT_H; resh = resh + 1) begin
                for (resw = 0; resw < RESULT_W; resw = resw + 1) begin
                    // instantiate a multiply core
                    logic  [DATA_WIDTH-1:0]   input_data_flattened [0:data_length_per_filter-1];
                    logic  [DATA_WIDTH-1:0]   filter_data_flattened [0:data_length_per_filter-1];
                    multiply_core_evo_withaddr #(DATA_WIDTH, data_length_per_filter, 1,1) multiply_cores
                    (
                        .clk(clk),
                        .reset(reset),

                        .row(input_data_flattened),
                        .col(filter_data_flattened),

                        .addr_i_in(),
                        .addr_k_in(),
                        .val_in(),

                        .sum_out(result_data_out[(resd * RESULT_H * RESULT_W + resh * RESULT_W + resw) * DATA_WIDTH +: DATA_WIDTH]),
                        .addr_i_out(),
                        .addr_k_out(),
                        .val_out()
                    );
                    // connecting flattened wire
                    for(i = 0; i < IMG_D; i = i + 1) begin
                        for(j = 0; j < FILTER_H; j = j + 1) begin
                            for(k = 0; k < FILTER_W; k = k + 1) begin
                                assign input_data_flattened[i * FILTER_H * FILTER_W + j * FILTER_W + k] = img_data_in[(i * IMG_H * IMG_W + (resh * STRIDE_H + j) * IMG_W + resw * STRIDE_W + k) * DATA_WIDTH +: DATA_WIDTH];
                                assign filter_data_flattened[i * FILTER_H * FILTER_W + j * FILTER_W + k] = fil[(resd * IMG_D * FILTER_H * FILTER_W + i * FILTER_H * FILTER_W + j * FILTER_W + k) * DATA_WIDTH +: DATA_WIDTH];
                            end
                        end
                    end
                end
            end
        end
    endgenerate


    // use one multiply core for transfering opqaue field
    multiply_core_evo_withaddr #(1, data_length_per_filter, 8, 1) opqaue_cycle_match
    (
        .clk(clk),
        .reset(reset),

        .row(),
        .col(),

        .addr_i_in(opaque_in),
        .addr_k_in(),
        .val_in(),

        .sum_out(),
        .addr_i_out(opaque_out),
        .addr_k_out(),
        .val_out()
    );
    
endmodule

`endif
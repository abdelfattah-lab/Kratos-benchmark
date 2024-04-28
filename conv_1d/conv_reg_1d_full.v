`ifndef __CONV_REG_1D_PARALLEL_V__
`define __CONV_REG_1D_PARALLEL_V__


`include "tree_mac/multiply_core_evo.v"
module conv_reg_1d_parallel
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
    input   logic                               clk,
    input   logic                               reset,

    input   logic   [DATA_WIDTH*FILTER_K*IMG_D*FILTER_L-1:0]   weight,

    input   logic   [DATA_WIDTH*IMG_D*IMG_W-1:0]            lines_in,

    output  logic   [DATA_WIDTH*RESULT_D*RESULT_W-1:0]      lines_out,

    input   logic   [7:0]                       opaque_in,
    output  logic   [7:0]                       opaque_out
);

    localparam mul_length = FILTER_L * IMG_D;

    genvar i, j, k, l;
    generate
        // create multiply core
        for (i = 0; i < RESULT_D; i = i + 1) begin
            for (j = 0; j < RESULT_W; j = j + 1) begin
                logic  [DATA_WIDTH*mul_length-1:0]    weight_flattened;
                logic  [DATA_WIDTH*mul_length-1:0]    input_flattened;
                // connect the flattened wire
                for (k = 0; k < IMG_D; k = k + 1) begin
                    for (l = 0; l < FILTER_L; l = l + 1) begin 
                        assign weight_flattened[(i * k * FILTER_L + l + 1) * DATA_WIDTH-1:(k * FILTER_L + l) * DATA_WIDTH] = weight[(i * IMG_D * FILTER_L + k * FILTER_L + l +1) * DATA_WIDTH-1:(i * IMG_D * FILTER_L + k * FILTER_L + l) * DATA_WIDTH];
                        assign input_flattened[(k * FILTER_L + l + 1) * DATA_WIDTH-1:(k * FILTER_L + l) * DATA_WIDTH] = lines_in[(k * IMG_W + j * STRIDE_W + l + 1) * DATA_WIDTH-1:(k * IMG_W + j * STRIDE_W + l) * DATA_WIDTH];
                    end
                end
                
                multiply_core_evo #(DATA_WIDTH, mul_length) mulcore_inst
                (
                    .clk(clk),
                    .reset(reset),
                    .row(input_flattened),
                    .col(weight_flattened),
                    .sum_out(lines_out[(i*RESULT_W + j + 1) * DATA_WIDTH - 1 : (i*RESULT_W + j) * DATA_WIDTH])
                );
            end
        end
    endgenerate
    
    // use one multiply core for transfering opqaue field
    multiply_core_evo_chain #(8, mul_length) opqaue_cycle_match
    (
        .clk(clk),
        .reset(reset),
        .in(opaque_in),
        .out(opaque_out)
    );
endmodule

`endif
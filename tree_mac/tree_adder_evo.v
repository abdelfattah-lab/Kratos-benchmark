`ifndef __TREE_ADDER_EVO_V__
`define __TREE_ADDER_EVO_V__

`include "vc/vc_tools.v"
// requirement for the multiply core:
// at the val cycle, it takes all data in and starts calculation.
// every cycle, it should be ready (fully pipelined).
// takes at least 1 cycles to get the result.
// addr i and k acts like the opaque field of memory request.

module tree_adder_evo
#(
    parameter DATA_WIDTH = 8,
    parameter DATA_LENGTH = 16,
    // default address volume is fine.
    parameter ADDRESS_WIDTH_I = 8, 
    parameter ADDRESS_WIDTH_K = 8
)
(
    input   logic                           clk,
    input   logic                           reset,

    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]  nums,

    input   logic   [ADDRESS_WIDTH_I-1:0]   addr_i_in,
    input   logic   [ADDRESS_WIDTH_K-1:0]   addr_k_in,
    input   logic                           val_in,

    output  logic   [DATA_WIDTH-1:0]        sum_out,
    output  logic   [ADDRESS_WIDTH_I-1:0]   addr_i_out,
    output  logic   [ADDRESS_WIDTH_K-1:0]   addr_k_out,
    output  logic                           val_out
);

    localparam LEAST2POWLEN = 2 ** $clog2(DATA_LENGTH);
    localparam TOTAL_LENGTH = 2 * LEAST2POWLEN - 1;
    logic   [DATA_WIDTH-1:0]        inner_result [0:2 * LEAST2POWLEN-2];

    assign sum_out = inner_result[2 * LEAST2POWLEN - 2];

    genvar i;
    genvar k;
    genvar j;
    generate
        for (i = 0; i < DATA_LENGTH; i = i + 1) begin
            // register for storing input data
            vc_reg #(DATA_WIDTH) input_reg (
                .d(nums[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .q(inner_result[i]),
                .clk(clk)
            );
        end

        for (i = DATA_LENGTH; i < LEAST2POWLEN; i = i + 1) begin
            assign inner_result[i] = 0;
        end

        for (k = LEAST2POWLEN; k > 1; k = k / 2) begin
            for (j = 0; j < k; j = j + 2) begin
                logic  [DATA_WIDTH-1:0]    temp_a;
                assign temp_a = inner_result[2 * LEAST2POWLEN - 2 * k + j] + inner_result[2 * LEAST2POWLEN - 2 * k + j + 1];
                logic  [DATA_WIDTH-1:0]    temp_sum;
                assign inner_result[2 * LEAST2POWLEN - k + j / 2] = temp_sum;
                vc_reg #(DATA_WIDTH) add_reg (
                    .d(temp_a),
                    .q(temp_sum),
                    .clk(clk)
                );
            end
        end
    endgenerate


    // address and valid chain

    localparam EXTRA_ALIGN_STAGE = 1;
    localparam TOTAL_STAGES = $clog2(DATA_LENGTH)+EXTRA_ALIGN_STAGE;

    logic   [ADDRESS_WIDTH_I*(TOTAL_STAGES+1)-1:0]   addr_i_chain;
    logic   [ADDRESS_WIDTH_K*(TOTAL_STAGES+1)-1:0]   addr_k_chain;
    logic   [TOTAL_STAGES:0]                   val_chain;

    assign addr_i_chain[ADDRESS_WIDTH_I-1:0]    = addr_i_in;
    assign addr_k_chain[ADDRESS_WIDTH_K-1:0]    = addr_k_in;
    assign val_chain[0:0]                       = val_in;

    assign addr_i_out   = addr_i_chain[(TOTAL_STAGES+1)*ADDRESS_WIDTH_I-1:TOTAL_STAGES*ADDRESS_WIDTH_I];
    assign addr_k_out   = addr_k_chain[(TOTAL_STAGES+1)*ADDRESS_WIDTH_K-1:TOTAL_STAGES*ADDRESS_WIDTH_K];
    assign val_out      = val_chain[TOTAL_STAGES];

    generate
        for (i = 0; i < $clog2(DATA_LENGTH)+EXTRA_ALIGN_STAGE; i = i + 1) begin
            vc_reg #(ADDRESS_WIDTH_I) addr_i_reg (
                .d(addr_i_chain[(i+1)*ADDRESS_WIDTH_I-1:i*ADDRESS_WIDTH_I]),
                .q(addr_i_chain[(i+2)*ADDRESS_WIDTH_I-1:(i+1)*ADDRESS_WIDTH_I]),
                .clk(clk)
            );

            vc_reg #(ADDRESS_WIDTH_K) addr_k_reg (
                .d(addr_k_chain[(i+1)*ADDRESS_WIDTH_K-1:i*ADDRESS_WIDTH_K]),
                .q(addr_k_chain[(i+2)*ADDRESS_WIDTH_K-1:(i+1)*ADDRESS_WIDTH_K]),
                .clk(clk)
            );

            vc_ResetReg #(1,0) val_reg (
                .d(val_chain[i:i]),
                .q(val_chain[i+1:i+1]),
                .clk(clk),
                .reset(reset)
            );
        end
    endgenerate

endmodule

`endif
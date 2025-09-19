`ifndef __MULTIPLY_CORE_EVO_V__
`define __MULTIPLY_CORE_EVO_V__
`include "calc/log.v"
`include "vc/vc_tools.v"
`include "vc/vc_cycle_buffer.v"

module multiply_core_evo_withaddr
#(
    parameter DATA_WIDTH = 8,
    parameter DATA_LENGTH = 64,
    parameter ADDRESS_WIDTH_I = 8, 
    parameter ADDRESS_WIDTH_K = 8,
    parameter TREE_BASE = 2
)
(
    input   logic                           clk,
    input   logic                           reset,

    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]        row ,
    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]        col ,
    output  logic   [DATA_WIDTH*4-1:0]        sum_out,

    input   logic   [ADDRESS_WIDTH_I-1:0]   addr_i_in,
    input   logic   [ADDRESS_WIDTH_K-1:0]   addr_k_in,
    input   logic                           val_in,

    output  logic   [ADDRESS_WIDTH_I-1:0]   addr_i_out,
    output  logic   [ADDRESS_WIDTH_K-1:0]   addr_k_out,
    output  logic                           val_out
);
    multiply_core_evo #(DATA_WIDTH, DATA_LENGTH, TREE_BASE) mac_tree
    (
        .clk(clk),
        .reset(reset),
        .row(row),
        .col(col),
        .sum_out(sum_out)
    );

    // address and valid chain

    multiply_core_evo_chain #(ADDRESS_WIDTH_I, DATA_LENGTH, TREE_BASE) addr_i_chain
    (
        .clk(clk),
        .reset(reset),

        .in(addr_i_in),
        .out(addr_i_out)
    );

    multiply_core_evo_chain #(ADDRESS_WIDTH_K, DATA_LENGTH, TREE_BASE) addr_k_chain
    (
        .clk(clk),
        .reset(reset),

        .in(addr_k_in),
        .out(addr_k_out)
    );

    multiply_core_evo_chain #(1, DATA_LENGTH, TREE_BASE) val_chain
    (
        .clk(clk),
        .reset(reset),

        .in(val_in),
        .out(val_out)
    );
endmodule

// treating all numbers as unsigned. TODO: add signed support?
module multiply_core_evo
#(
    parameter int DATA_WIDTH = 8,
    parameter int DATA_LENGTH = 64,
    parameter int TREE_BASE = 2
)
(
    input   logic                           clk,
    input   logic                           reset,

    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]        row ,
    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]        col ,


    output  logic   [DATA_WIDTH*4-1:0]        sum_out
);
    localparam int MUL_WIDTH = DATA_WIDTH * 2;
    localparam int SUM_WIDTH = DATA_WIDTH * 4;
    localparam int LEVELS = clog_base(DATA_LENGTH, TREE_BASE);
    localparam int LEASTPOWLEN = TREE_BASE ** LEVELS;
    localparam int TREE_DIV = TREE_BASE - 1;
    localparam int LASTI = (TREE_BASE * LEASTPOWLEN - 1) / TREE_DIV - 1;

    logic   [SUM_WIDTH-1:0]        inner_result [0:LASTI];

    assign sum_out = inner_result[LASTI];
    // logic   [DATA_WIDTH-1:0]        row_buf [0:DATA_LENGTH-1];
    // logic   [DATA_WIDTH-1:0]        col_buf [0:DATA_LENGTH-1];
    genvar i;
    genvar k;
    genvar j;
    generate
        // generate multiplier for each element from row and col, and store the result in result[0:DATA_LENGTH-1]
        for (i = 0; i < DATA_LENGTH; i = i + 1) begin : mul_block
            // buffer one cycle for input row and col
            logic [DATA_WIDTH-1:0]        row_buf_temp;
            logic [DATA_WIDTH-1:0]        col_buf_temp;
            logic [DATA_WIDTH-1:0]        row_input_temp;
            logic [DATA_WIDTH-1:0]        col_input_temp;

            assign row_input_temp = row[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH];
            assign col_input_temp = col[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH];

            // assign row_buf[i] = row_buf_temp;
            // assign col_buf[i] = col_buf_temp;

            vc_reg #(DATA_WIDTH) row_buf_reg (
                .d(row_input_temp),
                .q(row_buf_temp),
                .clk(clk)
            );

            vc_reg #(DATA_WIDTH) col_buf_reg (
                .d(col_input_temp),
                .q(col_buf_temp),
                .clk(clk)
            );

            // multiply row and col to temp
            logic   [MUL_WIDTH-1:0]    temp_mul;
            logic   [MUL_WIDTH-1:0]    temp_res;
            assign temp_mul = row_buf_temp * col_buf_temp;
            assign inner_result[i] = temp_res;
            
            vc_reg #(MUL_WIDTH) mul_reg (
                .d(temp_mul),
                .q(temp_res),
                .clk(clk)
            );
        end
        
        // complete the rest of the inner_result with 0
        for (i = DATA_LENGTH; i < LEASTPOWLEN; i = i + 1) begin : zero_pad_block
            assign inner_result[i] = 0;
        end

        // tree structure adder
        for (k = LEVELS; k > 0; k = k - 1) begin : adder_tree_level_block
            for (j = 0; j < TREE_BASE ** (k - 1); j = j + 1) begin : adder_tree_row_block
                logic  [SUM_WIDTH-1:0]    partial_sum [0:TREE_DIV];
                logic  [SUM_WIDTH-1:0]    temp_sum;
                logic  [SUM_WIDTH-1:0]    temp_res;
                
                assign partial_sum[0] = inner_result[int'(TREE_BASE * (TREE_BASE ** LEVELS - TREE_BASE ** k) / (TREE_BASE - 1)) + j * TREE_BASE];
                for (i = 1; i < TREE_BASE; i=i+1) begin : adder_tree_partial_sum_block
                    assign partial_sum[i] = partial_sum[i-1] + inner_result[int'(TREE_BASE * (TREE_BASE ** LEVELS - TREE_BASE ** k) / (TREE_BASE - 1)) + j * TREE_BASE + i];
                end

                assign temp_sum = partial_sum[TREE_BASE-1];
                assign inner_result[int'((TREE_BASE * LEASTPOWLEN - TREE_BASE ** k) / TREE_DIV) + j] = temp_res;

                vc_reg #(SUM_WIDTH) add_reg (
                    .d(temp_sum),
                    .q(temp_res),
                    .clk(clk)
                );
            end
        end
    endgenerate
endmodule

module multiply_core_evo_chain
#(
    parameter INFO_WIDTH = 8,
    parameter DATA_LENGTH = 64,
    parameter TREE_BASE = 2
)(
    input   logic                           clk,
    input   logic                           reset,

    input   logic   [INFO_WIDTH-1:0]        in,
    output  logic   [INFO_WIDTH-1:0]        out
);

    localparam extra_align_stage = 2;
    localparam total_stages = clog_base(DATA_LENGTH, TREE_BASE) + extra_align_stage;

    vc_cycle_buffer #(INFO_WIDTH, total_stages) cycle_buffer_inst 
    (
        .clk(clk),
        .d(in),
        .q(out)
    );

endmodule

`endif
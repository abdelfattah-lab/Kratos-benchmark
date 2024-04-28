`ifndef __MULTIPLY_CORE_EVO_V__
`define __MULTIPLY_CORE_EVO_V__
`include "vc/vc_tools.v"
`include "vc/vc_cycle_buffer.v"

module multiply_core_evo_withaddr
#(
    parameter DATA_WIDTH = 8,
    parameter DATA_LENGTH = 64,
    parameter ADDRESS_WIDTH_I = 8, 
    parameter ADDRESS_WIDTH_K = 8
)
(
    input   logic                           clk,
    input   logic                           reset,

    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]        row ,
    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]        col ,
    output  logic   [DATA_WIDTH-1:0]        sum_out,

    input   logic   [ADDRESS_WIDTH_I-1:0]   addr_i_in,
    input   logic   [ADDRESS_WIDTH_K-1:0]   addr_k_in,
    input   logic                           val_in,

    output  logic   [ADDRESS_WIDTH_I-1:0]   addr_i_out,
    output  logic   [ADDRESS_WIDTH_K-1:0]   addr_k_out,
    output  logic                           val_out
);

    localparam LEAST2POWLEN = 2 ** $clog2(DATA_LENGTH);

    logic   [DATA_WIDTH-1:0]        inner_result [0:2 * LEAST2POWLEN-2];

    
    assign sum_out = inner_result[2 * LEAST2POWLEN - 2];
    // logic   [DATA_WIDTH-1:0]        row_buf [0:DATA_LENGTH-1];
    // logic   [DATA_WIDTH-1:0]        col_buf [0:DATA_LENGTH-1];
    genvar i;
    genvar k;
    genvar j;
    generate
        // generate multiplier for each element from row and col, and store the result in result[0:DATA_LENGTH-1]
        for (i = 0; i < DATA_LENGTH; i = i + 1) begin
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
            logic   [DATA_WIDTH-1:0]    temp_mul;
            logic   [DATA_WIDTH-1:0]    temp_res;
            assign temp_mul = row_buf_temp * col_buf_temp;
            assign inner_result[i] = temp_res;
            
            vc_reg #(DATA_WIDTH) mul_reg (
                .d(temp_mul),
                .q(temp_res),
                .clk(clk)
            );
        end
        
        // complete the rest of the inner_result with 0
        for (i = DATA_LENGTH; i < LEAST2POWLEN; i = i + 1) begin
            assign inner_result[i] = 0;
        end

        // tree structure adder
        for (k = LEAST2POWLEN; k > 1; k = k / 2) begin
            for (j = 0; j < k; j = j + 2) begin

                logic  [DATA_WIDTH-1:0]    temp_sum;
                logic  [DATA_WIDTH-1:0]    temp_res;
                assign temp_sum = inner_result[2 * LEAST2POWLEN - 2 * k + j] + inner_result[2 * LEAST2POWLEN - 2 * k + j + 1];
                assign inner_result[2 * LEAST2POWLEN - k + j / 2] = temp_res;
                
                vc_reg #(DATA_WIDTH) add_reg (
                    .d(temp_sum),
                    .q(temp_res),
                    .clk(clk)
                );
            end
        end
    endgenerate


    // address and valid chain

    multiply_core_evo_chain #(ADDRESS_WIDTH_I, DATA_LENGTH) addr_i_chain
    (
        .clk(clk),
        .reset(reset),

        .in(addr_i_in),
        .out(addr_i_out)
    );

    multiply_core_evo_chain #(ADDRESS_WIDTH_K, DATA_LENGTH) addr_k_chain
    (
        .clk(clk),
        .reset(reset),

        .in(addr_k_in),
        .out(addr_k_out)
    );

    multiply_core_evo_chain #(1, DATA_LENGTH) val_chain
    (
        .clk(clk),
        .reset(reset),

        .in(val_in),
        .out(val_out)
    );
endmodule


module multiply_core_evo
#(
    parameter DATA_WIDTH = 8,
    parameter DATA_LENGTH = 64
)
(
    input   logic                           clk,
    input   logic                           reset,

    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]        row ,
    input   logic   [DATA_WIDTH*DATA_LENGTH-1:0]        col ,


    output  logic   [DATA_WIDTH-1:0]        sum_out
);

    localparam LEAST2POWLEN = 2 ** $clog2(DATA_LENGTH);

    logic   [DATA_WIDTH-1:0]        inner_result [0:2 * LEAST2POWLEN-2];

    
    assign sum_out = inner_result[2 * LEAST2POWLEN - 2];
    // logic   [DATA_WIDTH-1:0]        row_buf [0:DATA_LENGTH-1];
    // logic   [DATA_WIDTH-1:0]        col_buf [0:DATA_LENGTH-1];
    genvar i;
    genvar k;
    genvar j;
    generate
        // generate multiplier for each element from row and col, and store the result in result[0:DATA_LENGTH-1]
        for (i = 0; i < DATA_LENGTH; i = i + 1) begin
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
            logic   [DATA_WIDTH-1:0]    temp_mul;
            logic   [DATA_WIDTH-1:0]    temp_res;
            assign temp_mul = row_buf_temp * col_buf_temp;
            assign inner_result[i] = temp_res;
            
            vc_reg #(DATA_WIDTH) mul_reg (
                .d(temp_mul),
                .q(temp_res),
                .clk(clk)
            );
        end
        
        // complete the rest of the inner_result with 0
        for (i = DATA_LENGTH; i < LEAST2POWLEN; i = i + 1) begin
            assign inner_result[i] = 0;
        end

        // tree structure adder
        for (k = LEAST2POWLEN; k > 1; k = k / 2) begin
            for (j = 0; j < k; j = j + 2) begin

                logic  [DATA_WIDTH-1:0]    temp_sum;
                logic  [DATA_WIDTH-1:0]    temp_res;
                assign temp_sum = inner_result[2 * LEAST2POWLEN - 2 * k + j] + inner_result[2 * LEAST2POWLEN - 2 * k + j + 1];
                assign inner_result[2 * LEAST2POWLEN - k + j / 2] = temp_res;
                
                vc_reg #(DATA_WIDTH) add_reg (
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
    parameter DATA_LENGTH = 64
)(
    input   logic                           clk,
    input   logic                           reset,

    input   logic   [INFO_WIDTH-1:0]        in,
    output  logic   [INFO_WIDTH-1:0]        out
);

    localparam extra_align_stage = 2;
    localparam total_stages = $clog2(DATA_LENGTH) + extra_align_stage;

    vc_cycle_buffer #(INFO_WIDTH, total_stages) cycle_buffer_inst 
    (
        .clk(clk),
        .d(in),
        .q(out)
    );

endmodule
`endif
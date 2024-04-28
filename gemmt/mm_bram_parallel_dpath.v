`ifndef __MM_BRAM_PARALLEL_DPATH_V__
`define __MM_BRAM_PARALLEL_DPATH_V__
`include "tree_mac/multiply_core_evo.v"
module mm_bram_parallel_dpath
#(
    parameter DATA_WIDTH = 8,
    parameter ROW_NUM = 32,
    parameter COL_NUM = 32,
    parameter LENGTH = 32,
    // below are parameters not meant to be set manually
    parameter ROW_ADDR_WIDTH = $clog2(ROW_NUM),
    parameter COL_ADDR_WIDTH = $clog2(COL_NUM),
    parameter LENGTH_ADDR_WIDTH = $clog2(LENGTH)
)(
    input   logic                           clk,
    input   logic                           reset,

    // from source sram
    input   logic   [DATA_WIDTH*LENGTH-1:0]        row_data_in ,
    
    // from ctrl
    input   logic                           dpath_sum_en,
    input   logic   [ROW_ADDR_WIDTH-1:0]    dpath_result_wraddr,

    output  logic                           last_val,
    // weights
    input   logic   [DATA_WIDTH*LENGTH*COL_NUM-1:0]        weights,

    // to result sram
    output  logic   [DATA_WIDTH*COL_NUM-1:0]        row_data_out,
    output  logic   [ROW_ADDR_WIDTH*COL_NUM-1:0]    row_wraddr,
    output  logic   [COL_NUM-1:0]                   row_wr_en 
);

    genvar i,j,k;

    logic    [DATA_WIDTH*LENGTH-1:0]      weights_t_flattened [0:COL_NUM-1];



    generate
        // transpose the weights so it can be indexed by column
        for(i = 0;i < LENGTH; i = i +1) begin
            for(j = 0;j < COL_NUM; j = j +1) begin
                assign weights_t_flattened[j][(i+1)*DATA_WIDTH-1:i*DATA_WIDTH] = weights[(i*COL_NUM+j+1)*DATA_WIDTH-1:(i*COL_NUM+j)*DATA_WIDTH];
            end
        end


        // create multiply cores
        for (i =0; i < COL_NUM; i = i + 1) begin
            multiply_core_evo_withaddr #(DATA_WIDTH, LENGTH , ROW_ADDR_WIDTH, 1) mul_core_inst
            (
                .clk(clk),
                .reset(reset),
                .row(row_data_in),
                .col(weights_t_flattened[i]),

                .addr_i_in(dpath_result_wraddr),
                .addr_k_in(),
                .val_in(dpath_sum_en),

                .sum_out(row_data_out[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .addr_i_out(row_wraddr[(i+1)*ROW_ADDR_WIDTH-1:i*ROW_ADDR_WIDTH]),
                .addr_k_out(),
                .val_out(row_wr_en[i])
            );
        end
    endgenerate



endmodule

`endif
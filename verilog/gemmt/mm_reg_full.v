`ifndef __MM_REG_FULL_V__
`define __MM_REG_FULL_V__

`include "tree_mac/multiply_core_evo.v"

module mm_reg_full
#(
    parameter DATA_WIDTH = 8,
    parameter ROW_NUM = 8,
    parameter COL_NUM = 8,
    parameter LENGTH = 8
)(
    input clk,
    input reset,

    input   logic   [DATA_WIDTH*ROW_NUM*LENGTH-1:0]        mat,
    input   logic   [DATA_WIDTH*LENGTH*COL_NUM-1:0]        fil,

    output  logic   [DATA_WIDTH*ROW_NUM*COL_NUM-1:0]        res,

    input   logic   [7:0]                  opaque_in,
    output  logic   [7:0]                  opaque_out
);


    genvar i, j, k;


    generate
        for (i = 0; i < ROW_NUM; i = i + 1) begin
            for (j = 0; j < COL_NUM; j = j + 1) begin
                logic [DATA_WIDTH*LENGTH-1:0] row_temp;
                logic [DATA_WIDTH*LENGTH-1:0] col_temp;           
                for (k = 0; k < LENGTH; k = k + 1) begin
                    assign row_temp[(k+1)*DATA_WIDTH-1:k*DATA_WIDTH] = mat[(i*LENGTH+k+1)*DATA_WIDTH-1:(i*LENGTH+k)*DATA_WIDTH];
                    assign col_temp[(k+1)*DATA_WIDTH-1:k*DATA_WIDTH] = fil[(k*COL_NUM+j+1)*DATA_WIDTH-1:(k*COL_NUM+j)*DATA_WIDTH];
                end
                logic [DATA_WIDTH-1:0] res_temp;
                multiply_core_evo #(DATA_WIDTH, LENGTH) cc_inst
                (
                    .clk(clk),
                    .reset(reset),

                    .row(row_temp),
                    .col(col_temp),

                    .sum_out(res_temp)
                );
                assign res[(i*COL_NUM+j+1)*DATA_WIDTH-1:(i*COL_NUM+j)*DATA_WIDTH] = res_temp;
            end
        end
    endgenerate

    multiply_core_evo_chain #(8, LENGTH) cc_inst
    (
        .clk(clk),
        .reset(reset),

        .in(opaque_in),
        .out(opaque_out)
    );

endmodule

`endif
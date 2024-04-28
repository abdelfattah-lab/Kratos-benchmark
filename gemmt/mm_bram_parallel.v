`ifndef __MM_BRAM_PARALLEL_V__
`define __MM_BRAM_PARALLEL_V__

`include "gemmt/mm_bram_parallel_ctrl.v"
`include "gemmt/mm_bram_parallel_dpath.v"
module mm_bram_parallel
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

    input   logic                           val_in,
    output  logic                           rdy_in,
    // weights
    input   logic   [DATA_WIDTH*LENGTH*COL_NUM-1:0]        weights,
    // from source sram
    output  logic  [ROW_ADDR_WIDTH*LENGTH-1:0]     row_rdaddr,
    input   logic  [DATA_WIDTH*LENGTH-1:0]         row_data_in,
    // to result sram
    output  logic   [DATA_WIDTH*COL_NUM-1:0]        row_data_out,
    output  logic   [ROW_ADDR_WIDTH*COL_NUM-1:0]    row_wraddr,
    output  logic   [COL_NUM-1:0]                   row_wr_en    
);



    logic   [ROW_ADDR_WIDTH-1:0]    rdaddr;

    logic                           dpath_sum_en;
    logic   [ROW_ADDR_WIDTH-1:0]    dpath_result_wraddr;
    logic                           last_val;


    // duplicate row_rd_addr
    genvar i;
    generate
        for (i = 0; i < LENGTH; i = i + 1) begin
            assign row_rdaddr[(i+1)*ROW_ADDR_WIDTH-1:i*ROW_ADDR_WIDTH] = rdaddr;
        end
    endgenerate
    mm_bram_parallel_ctrl #(DATA_WIDTH,ROW_NUM,COL_NUM,LENGTH) mm_bram_parallel_ctrl_inst
    (
        .clk(clk),
        .reset(reset),

        .val_in(val_in),
        .rdy_in(rdy_in),

        .rdaddr(rdaddr),
        .dpath_sum_en(dpath_sum_en),
        .dpath_result_wraddr(dpath_result_wraddr),

        .last_val(last_val)
    );
    mm_bram_parallel_dpath #(DATA_WIDTH,ROW_NUM,COL_NUM,LENGTH) mm_bram_parallel_dpath_inst
    (
        .clk(clk),
        .reset(reset),

        .row_data_in(row_data_in),

        .dpath_sum_en(dpath_sum_en),
        .dpath_result_wraddr(dpath_result_wraddr),

        .last_val(last_val),

        .weights(weights),

        .row_data_out(row_data_out),
        .row_wraddr(row_wraddr),
        .row_wr_en(row_wr_en)
    );
endmodule

`endif
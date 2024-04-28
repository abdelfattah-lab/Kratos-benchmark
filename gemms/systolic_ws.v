// this is the implementation of weight stationary systolic array for matrix multiplication.
// include the control path and data path.
`ifndef __SYSTOLIC_WS_V__
`define __SYSTOLIC_WS_V__

`include "gemms/systolic_ws_dpath.v"
`include "gemms/systolic_ws_ctrl.v"
// since this is weight stationary, the LENGTH and COL_NUM in parameter refers to the row and column size of weight matrix.
// input and output are streams
module systolic_ws
#(
    parameter DATA_WIDTH = 8,
    parameter ROW_NUM = 8,
    parameter COL_NUM = 8,
    parameter LENGTH = 8,
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
    input   logic   [DATA_WIDTH-1:0]        weights         [0:LENGTH-1][0:COL_NUM-1],
    // from source sram
    output  logic   [ROW_ADDR_WIDTH-1:0]    row_rdaddr      [0:LENGTH-1],
    input   logic   [DATA_WIDTH-1:0]        row_data_in     [0:LENGTH-1],
    // to result sram
    output  logic   [DATA_WIDTH-1:0]        row_data_out    [0:COL_NUM-1],
    output  logic   [ROW_ADDR_WIDTH-1:0]    row_wraddr      [0:COL_NUM-1],
    output  logic                           row_wr_en       [0:COL_NUM-1]
);

    systolic_ws_dpath #(DATA_WIDTH,ROW_NUM,COL_NUM,LENGTH) systolic_ws_dpath_inst
    (
        .clk(clk),
        .reset(reset),

        .weights(weights),

        .row_data_in(row_data_in),
        .row_data_out(row_data_out)

    );

    systolic_ws_ctrl #(DATA_WIDTH,ROW_NUM,COL_NUM,LENGTH) systolic_ws_ctrl_inst
    (
        .clk(clk),
        .reset(reset),

        .val_in(val_in),
        .rdy_in(rdy_in),
        .row_rdaddr(row_rdaddr),
        .row_wraddr(row_wraddr),
        .row_wr_en(row_wr_en)
    );

endmodule

`endif
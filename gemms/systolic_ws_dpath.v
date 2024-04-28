`ifndef __SYSTOLIC_WS_DPATH_V__
`define __SYSTOLIC_WS_DPATH_V__

`include "gemms/systolic_ws_pe.v"
module systolic_ws_dpath
#(
    parameter DATA_WIDTH = 32,
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

    // input   logic                           val_in,
    // output  logic                           rdy_in,
    // weights
    input   logic   [DATA_WIDTH-1:0]        weights         [0:LENGTH-1][0:COL_NUM-1],
    // from source sram
    // output  logic   [ROW_ADDR_WIDTH-1:0]    row_rdaddr      [0:LENGTH-1],
    input   logic   [DATA_WIDTH-1:0]        row_data_in     [0:LENGTH-1],
    // to result sram
    output  logic   [DATA_WIDTH-1:0]        row_data_out    [0:COL_NUM-1]
    // output  logic   [ROW_ADDR_WIDTH-1:0]    row_wraddr      [0:COL_NUM-1],
    // output  logic                           row_wr_en       [0:COL_NUM-1]
);

    logic   [DATA_WIDTH-1:0]    norths  [0:COL_NUM-1];

    genvar i;
    generate
        for (i = 0; i < COL_NUM; i = i + 1) begin
            assign norths[i] = 0;
        end
    endgenerate

    systolic_ws_pe_array #(DATA_WIDTH,LENGTH,COL_NUM) systolic_ws_pe_array_inst
    (
        .clk(clk),
        .reset(reset),

        .norths(norths),
        .wests(row_data_in),

        .weights(weights),

        .souths(row_data_out),
        .easts()
    );


endmodule

`endif
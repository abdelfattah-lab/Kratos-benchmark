`ifndef __VC_SHIFTREGISTERS_V__
`define __VC_SHIFTREGISTERS_V__

`include "vc/vc_tools.v"

// shift registers 1 dimension, read all ports
module vc_shiftregisters_1d_ar
#(
    parameter DATA_WIDTH = 32, // data width
    parameter NUM_ELEMENTS = 8 // number of elements
)
(
    // clock and reset
    input   logic                                   clk,
    input   logic                                   reset,
    // data in
    input   logic    [DATA_WIDTH-1:0]               data_in,
    input   logic                                   en,
    input   logic                                   val_in,
    // data out
    output  logic    [DATA_WIDTH*NUM_ELEMENTS-1:0]  data_out,
    output  logic    [NUM_ELEMENTS-1:0]             val_out
);

    logic   [DATA_WIDTH*(NUM_ELEMENTS+1)-1:0]   data_stream;
    logic   [NUM_ELEMENTS:0]                    val_stream;

    assign data_stream[DATA_WIDTH-1:0] = data_in;
    assign val_stream[0:0] = val_in;
    genvar i;
    generate
        for(i = 0; i < NUM_ELEMENTS; i = i + 1) begin
            vc_EnReg #(DATA_WIDTH) data_regs
            (
                .clk(clk),
                .en(en),
                .d(data_stream[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .q(data_stream[(i+2)*DATA_WIDTH-1:(i+1)*DATA_WIDTH])
            );

            vc_ResetEnReg #(1) val_regs
            (
                .clk(clk),
                .reset(reset),
                .en(en),
                .d(val_stream[i:i]),
                .q(val_stream[i+1:i+1])
            );
            
            assign data_out[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH] = data_stream[(i+2)*DATA_WIDTH-1:(i+1)*DATA_WIDTH];
            assign val_out[i] = val_stream[i+1];
        end
    endgenerate


endmodule


module vc_shiftregisters_2d_ar
#(
    parameter DATA_WIDTH = 8, 
    parameter HEIGHT = 8,
    parameter WIDTH = 8
)(
    input   logic                                   clk,
    input   logic                                   reset,

    input   logic   [DATA_WIDTH*HEIGHT-1:0]         data_in,
    input   logic   [HEIGHT-1:0]                    en,
    input   logic   [HEIGHT-1:0]                    val_in,

    output  logic   [DATA_WIDTH*HEIGHT*WIDTH-1:0]   data_out,
    output  logic   [HEIGHT*WIDTH-1:0]              val_out
);


    genvar i;

    generate
        for(i = 0; i < HEIGHT; i = i + 1) begin
            vc_shiftregisters_1d_ar #(DATA_WIDTH, WIDTH) data_regs
            (
                .clk(clk),
                .reset(reset),
                .data_in(data_in[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH]),
                .en(en[i]),
                .val_in(val_in[i]),
                .data_out(data_out[(i+1)*DATA_WIDTH*WIDTH-1:i*DATA_WIDTH*WIDTH]),
                .val_out(val_out[(i+1)*WIDTH-1:i*WIDTH])
            );
        end
    endgenerate

endmodule


`endif
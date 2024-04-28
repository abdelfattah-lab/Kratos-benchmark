`ifndef __VC_CYCLE_BUFFER_V__
`define __VC_CYCLE_BUFFER_V__
`include "vc/vc_tools.v"
module vc_cycle_buffer
#(
    parameter DATA_WIDTH = 12, // data width
    parameter NUM_CYCLES = 1
)(
    input  logic   [DATA_WIDTH-1:0]    d,
    output logic   [DATA_WIDTH-1:0]    q,
    input  logic                       clk
);

    logic [DATA_WIDTH-1:0] buffer [0:NUM_CYCLES];

    assign buffer[0] = d;
    assign q = buffer[NUM_CYCLES];
    genvar i;
    generate
        for (i = 0; i < NUM_CYCLES; i = i + 1) begin
            vc_reg #(DATA_WIDTH) regs (
                .d(buffer[i]),
                .q(buffer[i+1]),
                .clk(clk)
            );
        end
    endgenerate

endmodule

`endif
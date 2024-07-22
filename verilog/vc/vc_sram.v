`ifndef __VC_SRAM_V__
`define __VC_SRAM_V__

module vc_sram_1r1w
#(
    parameter DATA_WIDTH = 12, // data width
    parameter NUM_WORDS = 16, // number of words

    // parameters below are not meant to be set manually
    // ==============================
    parameter ADDR_WIDTH = $clog2(NUM_WORDS)
)
(
    input   logic                                   clk,

    input   logic    [DATA_WIDTH-1:0]               data_in,
    output  logic    [DATA_WIDTH-1:0]               data_out,

    input   logic    [ADDR_WIDTH-1:0]               rdaddress,
    input   logic    [ADDR_WIDTH-1:0]               wraddress,

    input   logic                                   wren
);

    logic [DATA_WIDTH-1:0] mem [0:NUM_WORDS-1];

    always_ff @(posedge clk) begin
        if (wren) begin
            mem[wraddress] <= data_in;
        end
        data_out <= mem[rdaddress];
    end

endmodule


`endif
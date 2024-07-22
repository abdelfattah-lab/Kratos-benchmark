`ifndef __VC_COUNTER_ADDER_V__
`define __VC_COUNTER_ADDER_V__
// in this design, it has a counter, which can be add by a fixed numer per cycle when enabled, also it outputs a divided number and remainings
module vc_counter_adder
#(
    parameter DATA_WIDTH = 8,
    parameter reset_value = 0,
    parameter addend = 1,
    parameter divisor = 3
)(
    input   logic clk,
    input   logic reset,
    input   logic en,
    output  logic [DATA_WIDTH-1:0] counter,
    output  logic [DATA_WIDTH-1:0] quotient,
    output  logic [DATA_WIDTH-1:0] remainder
);

    // logic [DATA_WIDTH-1:0] quotient_temp;
    // logic [DATA_WIDTH-1:0] remainder_temp;

    always_ff @(posedge clk) begin
        if (reset) begin
            counter <= reset_value;
        end else if (en) begin
            counter <= counter + addend;
        end

        // quotient <= quotient_temp;
        // remainder <= remainder_temp;
    end



    always_comb begin
        quotient = counter / divisor;
        remainder = counter % divisor;
    end

    // always_comb begin
    //     quotient_temp = counter / divisor;
    //     remainder_temp = counter % divisor;
    // end

endmodule

`endif
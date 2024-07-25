`ifndef __VC_TOOLS_V__
`define __VC_TOOLS_V__
module vc_reg
#(
    parameter DATA_WIDTH = 32
)
(
    input   logic   [DATA_WIDTH-1:0]    d,
    output  logic   [DATA_WIDTH-1:0]    q,
    input   logic                       clk
);
    
    always_ff @(posedge clk ) begin
        q <= d;
    end
endmodule

module vc_ResetReg
#(
    parameter DATA_WIDTH = 32,
    parameter reset_value = 0
)
(
    input   logic   [DATA_WIDTH-1:0]    d,
    output  logic   [DATA_WIDTH-1:0]    q,
    input   logic                       clk,
    input   logic                       reset
);
    
    always_ff @(posedge clk) begin
        if (reset) begin
            q <= reset_value;
        end else begin
            q <= d;
        end
    end
endmodule

module vc_ResetEnReg
#(
    parameter DATA_WIDTH = 32,
    parameter reset_value = 0
)
(
    input   logic   [DATA_WIDTH-1:0]    d,
    output  logic   [DATA_WIDTH-1:0]    q,
    input   logic                       clk,
    input   logic                       reset,
    input   logic                       en
);
    
    always_ff @(posedge clk) begin
        if (reset) begin
            q <= reset_value;
            // $display("reset %d", reset_value);
        end else if (en) begin
            q <= d;
            // $display("d %d", d);
        end
    end

endmodule

module vc_EnReg
#(
    parameter DATA_WIDTH = 32
)
(
    input   logic   [DATA_WIDTH-1:0]    d,
    output  logic   [DATA_WIDTH-1:0]    q,
    input   logic                       clk,
    input   logic                       en
);
    
    always_ff @(posedge clk) begin
        if (en) begin
            q <= d;
        end
    end

endmodule

module multiplier_reg
#(
    parameter DATA_WIDTH = 32,
    parameter OUTPUT_WIDTH = 32
)
(
    input   logic                       clk,
    input   logic   [DATA_WIDTH-1:0]    x,
    input   logic   [DATA_WIDTH-1:0]    y,
    output  logic   [OUTPUT_WIDTH-1:0]  c
);
    
    always_ff @(posedge clk) begin
        c <= x * y;
    end

endmodule

module adder_reg
#(
    parameter DATA_WIDTH = 32,
    parameter OUTPUT_WIDTH = 32
)
(
    input   logic                       clk,
    input   logic   [DATA_WIDTH-1:0]    x,
    input   logic   [DATA_WIDTH-1:0]    y,
    output  logic   [OUTPUT_WIDTH-1:0]  c
);
    
    always_ff @(posedge clk) begin
        c <= x + y;
        // c <= 2;
    end

endmodule

`endif
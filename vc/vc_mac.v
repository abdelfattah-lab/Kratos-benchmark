`ifndef __VC_MAC_V__
`define __VC_MAC_V__

`include "vc/vc_cycle_buffer.v"
// multiply and accumulate, with reset function
module vc_mac
#(
    parameter DATA_WIDTH = 32
)(
    input   logic                       clk,
    input   logic                       reset,

    input   logic   [DATA_WIDTH-1:0]    a,
    input   logic   [DATA_WIDTH-1:0]    b,
    input   logic                       en,

    output  logic   [DATA_WIDTH-1:0]    q
);



    // always_ff @(posedge clk) begin
    //     if (reset) begin
    //         q <= 0;
    //     end else if (en) begin
    //         q <= q + a * b;
    //     end
    // end

    logic  [DATA_WIDTH-1:0]  a_temp;
    logic  [DATA_WIDTH-1:0]  b_temp;
    logic                    en_temp;


    // reset is instant, but multiply and accumulate take one cycle latency. throughput is 1
    always_ff @(posedge clk) begin
        if (reset) begin
            a_temp <= 0;
            b_temp <= 0;
            en_temp <= 0;
            q <= 0;
        end else begin
            a_temp <= a;
            b_temp <= b;
            en_temp <= en;
            if (en_temp) begin
                q <= q + a_temp * b_temp;
            end else begin
                q <= q;
            end
        end
    end


endmodule

module vc_mac_pipe
#(
    parameter DATA_WIDTH = 32
)(
    input   logic                       clk,
    input   logic                       reset,

    input   logic   [DATA_WIDTH-1:0]    a,
    input   logic   [DATA_WIDTH-1:0]    b,
    input   logic                       en,

    output  logic   [DATA_WIDTH-1:0]    q
);



    // always_ff @(posedge clk) begin
    //     if (reset) begin
    //         q <= 0;
    //     end else if (en) begin
    //         q <= q + a * b;
    //     end
    // end

    logic  [DATA_WIDTH-1:0]  a_temp;
    logic  [DATA_WIDTH-1:0]  b_temp;
    logic                    en_temp;
    logic                    reset_temp;

    // reset multiply and accumulate take one cycle latency. throughput is 1
    always_ff @(posedge clk) begin
        a_temp <= a;
        b_temp <= b;
        en_temp <= en;
        reset_temp <= reset;
        if (reset_temp) begin
            q <= 0;
        end else begin
            if (en_temp) begin
                q <= q + a_temp * b_temp;
            end else begin
                q <= q;
            end
        end
    end


endmodule

module vc_mac_pipe_buffer
#(
    parameter DATA_WIDTH = 32,
    parameter BUFFER_STAGE = 0
)(
    input   logic                       clk,
    input   logic                       reset,

    input   logic   [DATA_WIDTH-1:0]    a,
    input   logic   [DATA_WIDTH-1:0]    b,
    input   logic                       en,

    output  logic   [DATA_WIDTH-1:0]    q
);

    logic  [DATA_WIDTH-1:0]  a_buffer_out;
    logic  [DATA_WIDTH-1:0]  b_buffer_out;
    logic                    en_buffer_out;
    logic                    reset_buffer_out;

    // reset multiply and accumulate take one cycle latency. throughput is 1
    vc_cycle_buffer #(DATA_WIDTH, BUFFER_STAGE) a_buffer (
        .d(a),
        .q(a_buffer_out),
        .clk(clk)
    );

    vc_cycle_buffer #(DATA_WIDTH, BUFFER_STAGE) b_buffer (
        .d(b),
        .q(b_buffer_out),
        .clk(clk)
    );

    vc_cycle_buffer #(1, BUFFER_STAGE) en_buffer (
        .d(en),
        .q(en_buffer_out),
        .clk(clk)
    );

    vc_cycle_buffer #(1, BUFFER_STAGE) reset_buffer (
        .d(reset),
        .q(reset_buffer_out),
        .clk(clk)
    );

    vc_mac_pipe #(DATA_WIDTH) mac_pipe (
        .clk(clk),
        .reset(reset_buffer_out),

        .a(a_buffer_out),
        .b(b_buffer_out),
        .en(en_buffer_out),

        .q(q)
    );


endmodule

`endif
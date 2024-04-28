`ifndef __CONV_1D_CTRL_V__
`define __CONV_1D_CTRL_V__

`include "vc/vc_cycle_buffer.v"
module conv_bram_1d_ctrl
#(
    parameter DATA_WIDTH = 8,
    parameter IMG_W = 32,
    parameter IMG_D = 4,
    // no IMG_H parameter because it is always 1
    parameter FILTER_L = 3,
    parameter RESULT_D = 8,
    parameter STRIDE_W = 1,

    // parameters below are not meant to be set manually
    // ==============================
    parameter RESULT_W = (IMG_W - FILTER_L) / STRIDE_W + 1,
    parameter FILTER_K = RESULT_D,

    parameter IMG_W_ADDR_WIDTH = $clog2(IMG_W),
    parameter IMG_RAM_ADDR_WIDTH = $clog2(IMG_W),

    parameter RESULT_W_ADDR_WIDTH = $clog2(RESULT_W),
    parameter RESULT_RAM_ADDR_WIDTH = $clog2(RESULT_W)
)(
    input   logic                                   clk,
    input   logic                                   reset,
    // filter
    input   logic                                   val_in,
    output  logic                                   rdy_in,
    // image
    output  logic   [IMG_RAM_ADDR_WIDTH-1:0]        img_rdaddr,
    // dpath result
    output  logic                                   dpath_sr_wren,

    output  logic   [RESULT_RAM_ADDR_WIDTH-1:0]     dpath_result_wraddr,
    output  logic                                   dpath_result_wren,

    input   logic                                   last_val
);

    typedef enum logic [$clog2(5)-1:0] {
        STATE_IDLE, // waiting for start
        STATE_FILL, // fill shift register with initial value 
        STATE_SLIDE, // slide and fill it
        STATE_WAIT // wait for final finish
    } state_t;
    
    state_t     state, state_next;

    // address signals for inner control and calculation
    logic   [IMG_RAM_ADDR_WIDTH-1:0]    rdaddr, rdaddr_next;
    logic   [RESULT_RAM_ADDR_WIDTH-1:0] result_wraddr, result_wraddr_next;
    logic                               result_wren;

    logic   [2:0]   stride_w_counter, stride_w_counter_next;

    assign img_rdaddr = rdaddr_next;

    // because from source write to shift register need one cycle, so the result write address and write enable are delayed by one cycle
    vc_cycle_buffer #(RESULT_RAM_ADDR_WIDTH + 1,1) result_cycle_buffer(
        .d({result_wraddr      , result_wren      }),
        .q({dpath_result_wraddr, dpath_result_wren}),
        .clk(clk)
    );





    always_comb begin
        // default state transition
        state_next = state;
        rdaddr_next = rdaddr;
        result_wraddr_next = result_wraddr;
        stride_w_counter_next = stride_w_counter;
        // direct output
        dpath_sr_wren = 0;
        rdy_in = 0;

        result_wren = 0;
        case (state)
            STATE_IDLE: begin
                rdy_in = 1;
                if (val_in) begin
                    state_next = STATE_FILL;
                    rdaddr_next = 0;
                    result_wraddr_next = 0;
                end
            end
            STATE_FILL: begin
                // write to shift register
                dpath_sr_wren = 1;
                // move to next read address
                rdaddr_next = rdaddr + 1;
                // if go to the end of filter length, go to slide state
                if (rdaddr == FILTER_L - 1) begin
                    state_next = STATE_SLIDE;
                    stride_w_counter_next = 0;
                    // reset read address
                end
            end
            STATE_SLIDE: begin
                dpath_sr_wren = 1;
                rdaddr_next = rdaddr + 1;
                if (stride_w_counter == STRIDE_W - 1) begin
                    stride_w_counter_next = 0;
                    result_wraddr_next = result_wraddr + 1;
                    result_wren = 1;
                end else begin
                    stride_w_counter_next = stride_w_counter + 1;
                end
                
                if (rdaddr == IMG_W - 1) begin
                    state_next = STATE_WAIT;
                end
            end
            STATE_WAIT: begin
                if (last_val) begin
                    state_next = STATE_IDLE;
                end
            end
            default: begin
                state_next = STATE_IDLE;
            end
        endcase
    end

    always_ff @(posedge clk) begin
        if (reset) begin
            state <= STATE_IDLE;
            rdaddr <= 0;
            result_wraddr <= 0;
            stride_w_counter <= 0;
        end else begin
            state <= state_next;
            rdaddr <= rdaddr_next;
            result_wraddr <= result_wraddr_next;
            stride_w_counter <= stride_w_counter_next;
        end
    end

endmodule

`endif
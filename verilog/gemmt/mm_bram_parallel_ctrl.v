`ifndef __MM_BRAM_PARALLEL_CTRL_V__
`define __MM_BRAM_PARALLEL_CTRL_V__

`include "vc/vc_cycle_buffer.v"
module mm_bram_parallel_ctrl
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
    // clock reset and trigger
    input   logic                           clk,
    input   logic                           reset,
    input   logic                           val_in,
    output  logic                           rdy_in,

    // to sram
    output  logic   [ROW_ADDR_WIDTH-1:0]    rdaddr, // aka row read address
    // to dpath
    output  logic                           dpath_sum_en,
    output  logic   [ROW_ADDR_WIDTH-1:0]    dpath_result_wraddr,

    input   logic                           last_val
);

    typedef enum logic [$clog2(5)-1:0] {
        STATE_IDLE, // waiting for start
        STATE_SLIDE, // slide and calculate result
        STATE_WAIT // wait for final finish
    } state_t;

    state_t state, state_next;

    logic   [ROW_ADDR_WIDTH-1:0]    row_count,row_count_next;
    
    // request for next cycle, give the result of this cycle
    assign dpath_result_wraddr = row_count;
    assign rdaddr = row_count;

    always_comb begin
        state_next = state;
        row_count_next = row_count;
        dpath_sum_en = 0;
        rdy_in = 0;
        case (state) 
            STATE_IDLE: begin
                rdy_in = 1;
                if (val_in) begin
                    state_next = STATE_SLIDE;
                    row_count_next = 0;
                end
            end
            STATE_SLIDE: begin
                dpath_sum_en = 1;
                if (row_count == ROW_NUM-1) begin
                    state_next = STATE_WAIT;
                end else begin
                    row_count_next = row_count + 1;
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
            row_count <= 0;
        end else begin
            state <= state_next;
            row_count <= row_count_next;
        end
    end

endmodule

`endif
// this is the control path for weight stationary systolic array for matrix multiplication.
`ifndef __SYSTOLIC_WS_CTRL_V__
`define __SYSTOLIC_WS_CTRL_V__

module systolic_ws_ctrl
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

    input   logic                           val_in,
    output  logic                           rdy_in,
    // weights
    // input   logic   [DATA_WIDTH-1:0]        weights         [0:LENGTH-1][0:COL_NUM-1],
    // from source sram
    output  logic   [ROW_ADDR_WIDTH-1:0]    row_rdaddr      [0:LENGTH-1],
    // input   logic   [DATA_WIDTH-1:0]        row_data_in     [0:LENGTH-1],
    // to result sram
    // output  logic   [DATA_WIDTH-1:0]        row_data_out    [0:COL_NUM-1],
    output  logic   [ROW_ADDR_WIDTH-1:0]    row_wraddr      [0:COL_NUM-1],
    output  logic                           row_wr_en       [0:COL_NUM-1]
);

    typedef enum logic [$clog2(5)-1:0] {
        STATE_IDLE, // waiting for start
        STATE_SLIDE_LEN, // slide and trigger each read in length
        STATE_BUFFER, // one cycle latency see design doc
        STATE_SLIDE_COL, // slide and trigger each write in column
        STATE_WAIT // wait for final finish
    } state_t;

    state_t state, state_next;

    logic   [LENGTH_ADDR_WIDTH-1:0]     len_count, len_count_next;
    logic   [COL_ADDR_WIDTH-1:0]        col_count, col_count_next;

    logic   [ROW_ADDR_WIDTH-1:0]        row_count, row_count_next; // for wait to finish, NOT USED NOW


    logic                               len_counter_go;
    logic                               col_counter_go;


    genvar i, j;
    // generate counter for input and output address
    generate
        for(i = 0; i < LENGTH; i = i + 1) begin
            auto_counter #(ROW_NUM) len_input_counter
            (
                .clk(clk),
                .reset(reset),

                .go(len_counter_go && (len_count == i)),
                .num(row_rdaddr[i]),
                .val() // read does not need val
            );
        end

        for(i = 0; i < COL_NUM; i = i + 1) begin
            auto_counter #(ROW_NUM) col_output_counter
            (
                .clk(clk),
                .reset(reset),

                .go(col_counter_go && (col_count == i)),
                .num(row_wraddr[i]),
                .val(row_wr_en[i])
            );
        end
    endgenerate

    // state transition
    always_comb begin
        state_next = state;
        len_count_next = len_count;
        col_count_next = col_count;
        row_count_next = row_count;
        // default value
        len_counter_go = 0;
        col_counter_go = 0;
        rdy_in = 0;
        case (state)
            STATE_IDLE: begin
                rdy_in = 1;
                if (val_in) begin
                    state_next = STATE_SLIDE_LEN;
                    len_count_next = 0;
                    col_count_next = 0;
                    row_count_next = 0;
                end
            end
            STATE_SLIDE_LEN: begin
                len_counter_go = 1;
                if (len_count == LENGTH-1) begin
                    state_next = STATE_BUFFER;
                end else begin
                    len_count_next = len_count + 1;
                end
            end
            STATE_BUFFER: begin
                state_next = STATE_SLIDE_COL;
            end
            STATE_SLIDE_COL: begin
                col_counter_go = 1;
                if (col_count == COL_NUM-1) begin
                    state_next = STATE_WAIT;
                end else begin
                    col_count_next = col_count + 1;
                end
            end
            STATE_WAIT: begin
                if (row_wr_en[COL_NUM-1] && (row_wraddr[COL_NUM-1] == ROW_NUM-1)) begin
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
            len_count <= 0;
            col_count <= 0;
            row_count <= 0;
        end else begin
            state <= state_next;
            len_count <= len_count_next;
            col_count <= col_count_next;
            row_count <= row_count_next;
        end
    end

endmodule

// counter. When trigger with go, it counts from 0 to NUM_ELEMENTS-1, then stop.
// output num is the counter value, val is 1 when counting.
// the next cycle of go is 0 and then increasing.
module auto_counter
#(
    parameter NUM_ELEMENTS = 8,
    // below are parameters not meant to be set manually
    parameter ADDR_WIDTH = $clog2(NUM_ELEMENTS)
)(
    input   logic                           clk,
    input   logic                           reset,

    input   logic                           go,
    output  logic   [ADDR_WIDTH-1:0]        num,
    output  logic                           val
);

// rewrite with state machine so it should be more clear
// looks heavy.

    typedef enum logic [$clog2(5)-1:0] {
        STATE_IDLE, // waiting for start
        STATE_COUNT // slide and calculate result
    } state_t;

    state_t state, state_next;

    logic  [ADDR_WIDTH-1:0]    num_next;


    always_comb begin
        state_next = state;
        num_next = num;
        val = 0;
        case (state) 
            STATE_IDLE: begin
                if (go) begin
                    state_next = STATE_COUNT;
                    num_next = 0;
                end
            end
            STATE_COUNT: begin
                val = 1;
                if (num == NUM_ELEMENTS-1) begin
                    state_next = STATE_IDLE;
                end else begin
                    num_next = num + 1;
                end
            end
        endcase
    end

    always_ff @(posedge clk) begin
        if (reset) begin
            state <= STATE_IDLE;
            num <= 0;
        end else begin
            state <= state_next;
            num <= num_next;
        end
    end

endmodule




`endif
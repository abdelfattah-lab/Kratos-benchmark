`ifndef __CONV_BRAM_SR_FAST_CTRL_V__
`define __CONV_BRAM_SR_FAST_CTRL_V__

`include "vc/vc_counter_adder.v"
`include "vc/vc_rotation_mux.v"
`include "vc/vc_cycle_buffer.v"
// a few extra notice for this specific design. Because the BRAM need one cycle to read, previously we use xxx_next to calculate the address and send to BRAM
// so it lookaheads the next address and match the result with current cycle. But for this one, the striped storage is not well suitable for this design, so all
// address are calculated in current cycle. And therefore, all "val-like" signals and others (to dpath) are buffered one cycle. (different from other design)
module conv_bram_sr_fast_ctrl
#(
    parameter DATA_WIDTH = 12, // data width
    parameter IMG_W = 16, // image width
    parameter IMG_H = 16, // image height
    parameter IMG_D = 4,  // image depth
    parameter FILTER_L = 3, // filter length, we assume the filter is square
    parameter FILTER_K = 8, // filter numbers
    
    parameter STRIDE_W = 1, // stride alone width
    parameter STRIDE_H = 1, // stride alone height

    // parameters below are not meant to be set manually
    // ==============================
    parameter RESULT_W = (IMG_W - FILTER_L) / STRIDE_W + 1,
    parameter RESULT_H = (IMG_H - FILTER_L) / STRIDE_H + 1,
    parameter RESULT_D = FILTER_K,

    // each BRAM stores one image channel, access addr = w + h * IMG_W
    parameter IMG_W_ADDR_WIDTH = $clog2(IMG_W),
    parameter IMG_H_ADDR_WIDTH = $clog2(IMG_H),
    parameter IMG_RAM_ADDR_WIDTH = $clog2(IMG_W * IMG_H),
    parameter IMG_RAM_ADDR_WIDTH_PER_STRIPE = $clog2(IMG_W * IMG_H / FILTER_K),
    parameter IMG_D_ADDR_WIDTH = $clog2(IMG_D),
    
    // this is used to tell data kernel which register to fill in data.
    parameter FILTER_L_ADDR_WIDTH = $clog2(FILTER_L),
    parameter FILTER_RAM_ADDR_WIDTH = $clog2(FILTER_L * FILTER_L),

    // each BRAM stores one result channel, access addr = w + h * RESULT_W
    parameter RESULT_W_ADDR_WIDTH = $clog2(RESULT_W),
    parameter RESULT_H_ADDR_WIDTH = $clog2(RESULT_H),
    parameter RESULT_RAM_ADDR_WIDTH = $clog2(RESULT_W * RESULT_H)
)(
    // clock and reset
    input   logic                                           clk,
    input   logic                                           reset,

    // trigger
    input   logic                                           val_in,
    output  logic                                           rdy_in,
    // images
    output  logic    [IMG_RAM_ADDR_WIDTH_PER_STRIPE*FILTER_L-1:0]    img_rdaddr,
    // filters
    // output  logic    [FILTER_L_ADDR_WIDTH-1:0]             dpath_h_addr, // should NOT use, as each cycle it can ready one whole column
    output  logic                                           dpath_wren,
    output  logic                                           dpath_sum_en,
    // see design doc for details. offset as ports are all fixed.
    output  logic    [FILTER_L_ADDR_WIDTH-1:0]              dpath_rotation_offset,
    // results
    output  logic    [RESULT_RAM_ADDR_WIDTH-1:0]            dpath_result_wraddr,
    // output  logic                                           dpath_result_wren, // this is deprecated as when sum is calculated, it is always ready to write.
    // end signal
    input   logic                                           last_val
);

    typedef enum logic [$clog2(5)-1:0] {
        STATE_IDLE, // waiting for start
        STATE_FILL, // fill shift register with initial value 
        STATE_SLIDE, // slide and fill it
        STATE_CHECK, // state where a row is finished, and determine if all finished and go to end, or continue to next row @xilai implemented at 2023.07.31, we need to test if move this to SLIDE state will improve performance.
        STATE_WAIT // wait for final finish
    } state_t;

    state_t     state, state_next;

    logic   [RESULT_W_ADDR_WIDTH-1:0]   result_w_addr, result_w_addr_next;
    logic   [RESULT_H_ADDR_WIDTH-1:0]   result_h_addr, result_h_addr_next;

    // pointer to current filter value position
    logic   [FILTER_L_ADDR_WIDTH-1:0]   filter_w_addr, filter_w_addr_next;

    // ================================================================================================================================
    // logic for storing and calculating address
    logic                          reset_h_counter;
    logic                          step_h_counter;
    logic [IMG_H_ADDR_WIDTH-1:0]   img_h_addr_real [0:FILTER_L-1]; // real h coordinate
    logic [IMG_H_ADDR_WIDTH-1:0]   img_h_addr_striped [0:FILTER_L-1]; // striped h coordinate (divided by filter length)
    logic [IMG_H_ADDR_WIDTH-1:0]   img_h_addr_offset [0:FILTER_L-1]; // remainders (divided by filter length)
    genvar i,j,k;

    // the virtual address of each line, but need to rotated to a mux. see design doc '6a8cad38-cbb6-48b1-8336-90ac9f6d4991'
    logic    [IMG_RAM_ADDR_WIDTH_PER_STRIPE*FILTER_L-1:0]    img_rdaddr_track;
    // create line address for storing img_rdaddr related signals
    generate
        for(i = 0;i < FILTER_L; i = i + 1) begin
            // each row need a counter to hold individual address
            vc_counter_adder #(IMG_H_ADDR_WIDTH, i, STRIDE_H, FILTER_L) cat
            (
                .clk(clk),
                .reset(reset_h_counter),
                .en(step_h_counter),
                .counter(img_h_addr_real[i]),
                .quotient(img_h_addr_striped[i]),
                .remainder(img_h_addr_offset[i])
            );
            assign img_rdaddr_track[(i+1)*IMG_RAM_ADDR_WIDTH_PER_STRIPE-1:i*IMG_RAM_ADDR_WIDTH_PER_STRIPE] = img_h_addr_striped[i] * IMG_W + result_w_addr * STRIDE_W + filter_w_addr;
        end
    endgenerate

    // ================================================================================================================================
    // below is a extra counter_adder to calculate the current row h % FILTER_L, (essentially same as img_h_addr_offset[0])
    // but for clarity, we use a extra counter_adder to calculate it, and this can be optimized by quartus.

    logic    [FILTER_L_ADDR_WIDTH-1:0] mem_rotation_offset;

    vc_counter_adder #(FILTER_L_ADDR_WIDTH, 0, STRIDE_H, FILTER_L) rotation_amount_counter
    (
        .clk(clk),
        .reset(reset_h_counter),
        .en(step_h_counter),
        .counter(),
        .quotient(),
        .remainder(mem_rotation_offset)
    );
    
    vc_rotation_mux_forward_comb #(IMG_RAM_ADDR_WIDTH_PER_STRIPE, FILTER_L) address_rotation_mux
    (
        .data_in(img_rdaddr_track),
        .addr_in(mem_rotation_offset),
        .data_out(img_rdaddr)
    );

    // ================================================================================================================================
    // buffer all signal to dpath for one cycle as memory request need one cycle to back.

    logic                                           dpath_wren_pb;
    logic                                           dpath_sum_en_pb;
    // logic    [FILTER_L_ADDR_WIDTH-1:0]              dpath_rotation_offset_pb, // this is actually mem_rotation_offset, no need to double declare
    logic    [RESULT_RAM_ADDR_WIDTH-1:0]            dpath_result_wraddr_pb;


    vc_cycle_buffer #(1,1)                      dpath_wren_buffer           (.d(dpath_wren_pb),           .q(dpath_wren),             .clk(clk)); // one cycle delay for sram read
    vc_cycle_buffer #(1,1)                      dpath_rotation_offset_buffer(.d(mem_rotation_offset),     .q(dpath_rotation_offset),  .clk(clk)); // one cycle delay for sram read
    vc_cycle_buffer #(1,2)                      dpath_sum_en_buffer         (.d(dpath_sum_en_pb),         .q(dpath_sum_en),           .clk(clk)); // two cycle delay for sram read and write to register
    vc_cycle_buffer #(RESULT_RAM_ADDR_WIDTH,2)  dpath_result_wraddr_buffer  (.d(dpath_result_wraddr_pb),  .q(dpath_result_wraddr),    .clk(clk)); // two cycle delay for sram read and write to register
    // why the sum_en and wraddress need 2 cycles instead of one? because I remove the SUM state for higher through put, and therefore the sum_en signal is determinted in the slide state,
    // but it took one cycle for memory request to come back and one cycle for register to write. So it need two cycle delay.


    assign dpath_result_wraddr_pb = result_h_addr * RESULT_W + result_w_addr;
    // ================================================================================================================================
    // logic to determine state transition and other control signals

    always_comb begin
        // state and signal transition
        state_next = state;
        result_w_addr_next = result_w_addr;
        result_h_addr_next = result_h_addr;
        filter_w_addr_next = filter_w_addr;
        // address register
        reset_h_counter = 0;
        step_h_counter = 0;
        // direct dpath signals
        dpath_wren_pb = 0;
        dpath_sum_en_pb = 0;

        rdy_in = 0;


        case (state)
            STATE_IDLE: begin
                rdy_in = 1;
                if (val_in) begin
                    state_next = STATE_FILL;
                    result_w_addr_next = 0;
                    result_h_addr_next = 0;
                    reset_h_counter = 1;
                    filter_w_addr_next = 0;
                end
            end
            STATE_FILL: begin
                // allow write to dpath
                dpath_wren_pb = 1;
                filter_w_addr_next = filter_w_addr + 1;
                if (filter_w_addr == FILTER_L - STRIDE_W - 1) begin
                    state_next = STATE_SLIDE;
                    filter_w_addr_next = FILTER_L - STRIDE_W;
                end
            end
            STATE_SLIDE: begin
                dpath_wren_pb = 1;
                filter_w_addr_next = filter_w_addr + 1;
                if (filter_w_addr == FILTER_L - 1) begin
                    // new design, no SUM state, save one cycle per result.
                    filter_w_addr_next = FILTER_L - STRIDE_W;
                    dpath_sum_en_pb = 1;
                    result_w_addr_next = result_w_addr + 1;
                    if (result_w_addr == RESULT_W - 1) begin
                        state_next = STATE_CHECK;
                    end
                end
            end
            STATE_CHECK: begin
                state_next = STATE_FILL;
                result_w_addr_next = 0;
                result_h_addr_next = result_h_addr + 1;
                step_h_counter = 1;
                filter_w_addr_next = 0;
                if (result_h_addr == RESULT_H - 1) begin
                    state_next = STATE_WAIT;
                end
            end
            STATE_WAIT: begin
                if (last_val) begin
                    state_next = STATE_IDLE;
                end
            end
            default: begin
                state_next = state;
            end
        endcase
    end

    
    

    // update states and other registers
    always_ff @(posedge clk) begin
        if (reset) begin
            state <= STATE_IDLE;
            result_w_addr <= 0;
            result_h_addr <= 0;
            filter_w_addr <= 0;
        end else begin
            state <= state_next;
            result_w_addr <= result_w_addr_next;
            result_h_addr <= result_h_addr_next;
            filter_w_addr <= filter_w_addr_next;
        end
    end

endmodule

`endif
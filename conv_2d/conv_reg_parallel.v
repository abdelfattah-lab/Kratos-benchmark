// convolution implementation with parallel architecture, throughput is 1 row per clock cycle
// summary for implementation:
// input is one image row per cycle per channel, (img_w * imd_d / cycle) using shift register to store every input pixel
// using reduction tree
`ifndef __CONV_REG_PARALLEL_V__
`define __CONV_REG_PARALLEL_V__

// this design include both control path and data path, because data path is very simple, just large reduction tree
`include "vc/vc_shiftregisters.v"
`include "tree_mac/multiply_core_evo.v"
`include "vc/vc_cycle_buffer.v"
module conv_reg_parallel
#(
    parameter DATA_WIDTH = 8, // data width
    parameter IMG_W = 8, // image width
    parameter IMG_H = 8, // image height
    parameter IMG_D = 2,  // image depth
    parameter FILTER_W = 3, // filter width
    parameter FILTER_H = 3, // filter height
    parameter RESULT_D = 4, // filter numbers
    


    parameter buffer_stages = 5, // $clog2(FILTER_K / 8),
    parameter use_bram = 0, // use bram or not, if use bram, then assume read data has 1 cycle latency, if use reg, then assume read data has 0 cycle latency
    // parameters below are not meant to be set manually
    // ==============================
    
    parameter STRIDE_W = 1,  // TODO: support non 1 stride
    parameter STRIDE_H = 1,  // TODO: support non 1 stride

    parameter RESULT_W = (IMG_W - FILTER_W) / STRIDE_W + 1,
    parameter RESULT_H = (IMG_H - FILTER_H) / STRIDE_H + 1,
    parameter FILTER_K = RESULT_D,

    // each BRAM stores one image channel, access addr = w + h * IMG_W
    parameter IMG_W_ADDR_WIDTH = $clog2(IMG_W),
    parameter IMG_H_ADDR_WIDTH = $clog2(IMG_H),
    parameter IMG_RAM_ADDR_WIDTH = $clog2(IMG_H),
    parameter IMG_D_ADDR_WIDTH = $clog2(IMG_D),
    
    // filters (weights) are provides from ports, and protocal is that weights should be kept same
    parameter FILTER_W_ADDR_WIDTH = $clog2(FILTER_W),
    parameter FILTER_H_ADDR_WIDTH = $clog2(FILTER_H),

    // each register stores one column of one result channel
    parameter RESULT_W_ADDR_WIDTH = $clog2(RESULT_W),
    parameter RESULT_H_ADDR_WIDTH = $clog2(RESULT_H),
    parameter RESULT_RAM_ADDR_WIDTH = $clog2(RESULT_W * RESULT_H)
)(
    // clock and reset
    input   logic                                                       clk,
    input   logic                                                       reset,
    // filters
    input   logic    [FILTER_K*IMG_D*FILTER_H*FILTER_W*DATA_WIDTH-1:0]  fil,
    input   logic                                                       val_in,
    output  logic                                                       rdy_in,
    // images
    output  logic    [IMG_D*IMG_W*IMG_RAM_ADDR_WIDTH-1:0]               img_rdaddress,
    input   logic    [IMG_D*IMG_W*DATA_WIDTH-1:0]                       img_data_in,
    // results
    output  logic    [RESULT_D*RESULT_W*RESULT_H_ADDR_WIDTH-1:0]        result_wraddress,
    output  logic    [RESULT_D*RESULT_W*DATA_WIDTH-1:0]                 result_data_out,
    output  logic    [RESULT_D*RESULT_W-1:0]                            result_wren
);

    typedef enum logic [$clog2(5)-1:0] {
        STATE_IDLE, // waiting for start
        STATE_FILL, // fill shift register with initial value 
        STATE_SLIDE, // slide and fill it
        STATE_WAIT // wait for final finish
    } state_t;

    state_t state, state_next;

    logic   [IMG_H_ADDR_WIDTH-1:0]          img_h_rdaddr, img_h_rdaddr_next;
    logic   [RESULT_H_ADDR_WIDTH-1:0]       result_h_wraddr, result_h_wraddr_next, result_h_wraddr_delayed; // regitser to hold value of result_h_wraddr
    // below not used because stride is 1, so it is always full, and indicating that result addr should move to next
    // logic   [FILTER_H-1:0]                  filter_h_slide_counter, filter_h_slide_counter_next; // register to hold sliding progress of each filter


    logic                                   result_val_ctrl, result_val_ctrl_delayed;
    logic   [DATA_WIDTH-1:0]                img_data_sr_out [0:IMG_D-1][0:IMG_W-1][0:FILTER_H-1];
    genvar i, j, k;
    genvar p, q, r;

    // cycle latence 1 is because the data read is instance, and then takes one cycle to write to the shift register.
    // if read from bram i.e. use_bram = 1, then cycle latence is 2
    vc_cycle_buffer #(RESULT_H_ADDR_WIDTH + 1, 1) result_wraddress_buffer
    (
        .clk(clk),
        .d({result_h_wraddr, result_val_ctrl}),
        .q({result_h_wraddr_delayed, result_val_ctrl_delayed})
    );

    generate
        // create shift register column array, each length is the filter height
        for (i = 0; i < IMG_D; i = i + 1) begin
            for (j = 0; j < IMG_W;  j = j + 1) begin
                vc_shiftregisters_1d_ar #(DATA_WIDTH, FILTER_H) img_temp_sr
                (
                    .clk(clk),
                    .reset(reset),
                    .data_in(img_data_in[(i * IMG_W + j) * DATA_WIDTH +: DATA_WIDTH]),
                    .en(1'b1),
                    .val_in(),

                    .data_out(img_data_sr_out[i][j])
                );
            end
        end

        // create multiply and core array
        for (i = 0; i < RESULT_D; i = i + 1) begin
            for (j = 0; j < RESULT_W; j = j + 1) begin
                logic   [DATA_WIDTH-1:0]    input_flattened     [0:IMG_D * FILTER_H * FILTER_W- 1];
                logic   [DATA_WIDTH-1:0]    weight_flattened    [0:IMG_D * FILTER_H * FILTER_W - 1];
                multiply_core_evo_withaddr # (DATA_WIDTH, IMG_D * FILTER_H * FILTER_W, RESULT_H_ADDR_WIDTH, 1) mulcore
                (
                    .clk(clk),
                    .reset(reset),
                    .row(input_flattened),
                    .col(weight_flattened),

                    .addr_i_in(result_h_wraddr_delayed),
                    .addr_k_in(),
                    .val_in(result_val_ctrl_delayed),

                    .sum_out(result_data_out[(i * RESULT_W + j) * DATA_WIDTH +: DATA_WIDTH]),
                    .addr_i_out(result_wraddress[(i * RESULT_W + j) * RESULT_H_ADDR_WIDTH +: RESULT_H_ADDR_WIDTH]),
                    .addr_k_out(),
                    .val_out(result_wren[i * RESULT_W + j])
                );

                // connecting flattened wires
                for (p = 0; p < IMG_D; p = p + 1) begin
                    for (q = 0; q < FILTER_H; q = q + 1) begin
                        for (r = 0; r < FILTER_W; r = r + 1) begin
                            // assign filter_data_flattened[i * FILTER_H * FILTER_W + j * FILTER_W + k] = fil[(resd * IMG_D * FILTER_H * FILTER_W + i * FILTER_H * FILTER_W + j * FILTER_W + k) * DATA_WIDTH +: DATA_WIDTH];

                            // assign input_flattened[p * FILTER_H * FILTER_W + q * FILTER_W + r] = img_data_sr_out[p][j * STRIDE_W + r][FILTER_H - 1 - q];
                            assign input_flattened[p * FILTER_H * FILTER_W + q * FILTER_W + r] = img_data_sr_out[p][j * STRIDE_W + r][FILTER_H - 1 - q];
                            assign weight_flattened[p * FILTER_H * FILTER_W + q * FILTER_W + r] = fil[(i * IMG_D * FILTER_H * FILTER_W + p * FILTER_H * FILTER_W + q * FILTER_W + r) * DATA_WIDTH +: DATA_WIDTH];
                        end
                    end
                end
            end
        end
    endgenerate

    always_comb begin
        // default state transition
        state_next = state;
        img_h_rdaddr_next = img_h_rdaddr;
        result_h_wraddr_next = result_h_wraddr;
        // direct output
        rdy_in = 0;
        result_val_ctrl = 0;
        case (state)
            STATE_IDLE: begin
                rdy_in = 1;
                if (val_in) begin
                    state_next = STATE_FILL;
                    img_h_rdaddr_next = 0;
                    result_h_wraddr_next = 0;
                end
            end
            STATE_FILL: begin // fill the first few rows of the shift register
                img_h_rdaddr_next = img_h_rdaddr + 1;
                if (img_h_rdaddr == FILTER_H - 1 - STRIDE_H) begin
                    state_next = STATE_SLIDE;
                end
            end
            STATE_SLIDE: begin // slide through the image, and slide the shift register
                result_val_ctrl = 1;
                img_h_rdaddr_next = img_h_rdaddr + 1;
                result_h_wraddr_next = result_h_wraddr + 1;
                if (img_h_rdaddr == IMG_H - 1) begin
                    state_next = STATE_WAIT;
                end
            end
            STATE_WAIT: begin
                // if ((result_wraddress[RESULT_D-1][RESULT_W-1] == RESULT_H - 1) && result_wren[RESULT_D-1][RESULT_W-1]) begin
                if ((result_wraddress[((RESULT_D-1)*RESULT_W+RESULT_W-1)*RESULT_H_ADDR_WIDTH :+ RESULT_H_ADDR_WIDTH ] == RESULT_H - 1) && result_wren[(RESULT_D-1) * RESULT_W + RESULT_W-1]) begin
                    state_next = STATE_IDLE;
                end
            end
        endcase
    end

    // assign read address. if uses bram, then read has one cycle latency, so use the next value
    // if uses reg, then read has no latency, so use the current value
    generate
        if (use_bram) begin
            for (i = 0; i < IMG_D; i = i + 1) begin
                for (j = 0; j < IMG_W; j = j + 1) begin
                    // assign img_rdaddress[i][j] = img_h_rdaddr_next;
                    assign img_rdaddress[(i * IMG_W + j) * IMG_RAM_ADDR_WIDTH +: IMG_RAM_ADDR_WIDTH] = img_h_rdaddr_next;
                end
            end
        end else begin
            for (i = 0; i < IMG_D; i = i + 1) begin
                for (j = 0; j < IMG_W; j = j + 1) begin
                    assign img_rdaddress[(i * IMG_W + j) * IMG_RAM_ADDR_WIDTH +: IMG_RAM_ADDR_WIDTH] = img_h_rdaddr;
                end
            end
        end
    endgenerate
    
    // state registers
    always_ff @(posedge clk) begin
        if (reset) begin
            state <= STATE_IDLE;
            img_h_rdaddr <= 0;
            result_h_wraddr <= 0;
        end else begin
            state <= state_next;
            img_h_rdaddr <= img_h_rdaddr_next;
            result_h_wraddr <= result_h_wraddr_next;
        end
    end


endmodule

`endif
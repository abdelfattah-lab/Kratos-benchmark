// this is the process element unit for weigtht-stationary systolic array.
// maa is Multiply & Add. not accumulate.
// each cycle, it takes one input from north and one input from west, and do the following thins
// south <= north + weight * west
// east  <= west
`ifndef __SYSTOLIC_WS_PE_V__
`define __SYSTOLIC_WS_PE_V__

module systolic_ws_pe
#(
    parameter DATA_WIDTH = 8
)
(
    input   logic                       clk,
    input   logic                       reset, // reset not used, only for pin compatibility

    input   logic   [DATA_WIDTH-1:0]    north,
    input   logic   [DATA_WIDTH-1:0]    west,

    input   logic   [DATA_WIDTH-1:0]    weight,

    output  logic   [DATA_WIDTH-1:0]    south,
    output  logic   [DATA_WIDTH-1:0]    east,

    output  logic   [DATA_WIDTH-1:0]    mul_out
);

    always_comb begin
        mul_out = weight * west;
    end

    always_ff @(posedge clk) begin
        south <= north + mul_out;
        east <= west;
    end


endmodule

// since thiss is a weight stationary systolic array, this configuration is fixed.
// row_num and col_num refers to the row and column of the weight matrix.
// This might be different from other circuits.
module systolic_ws_pe_array
#(
    parameter DATA_WIDTH = 8,
    parameter ROW_NUM = 8,
    parameter COL_NUM = 8
)(
    input   logic                       clk,
    input   logic                       reset, // reset not used, only for pin compatibility

    input   logic   [DATA_WIDTH-1:0]    norths  [0:COL_NUM-1],
    input   logic   [DATA_WIDTH-1:0]    wests   [0:ROW_NUM-1],

    input   logic   [DATA_WIDTH-1:0]    weights [0:ROW_NUM-1][0:COL_NUM-1],

    output  logic   [DATA_WIDTH-1:0]    souths  [0:COL_NUM-1],
    output  logic   [DATA_WIDTH-1:0]    easts   [0:ROW_NUM-1]
);

    logic   [DATA_WIDTH-1:0]    ns_wires [0:ROW_NUM][0:COL_NUM-1];
    logic   [DATA_WIDTH-1:0]    we_wires [0:ROW_NUM-1][0:COL_NUM];

    genvar i, j;
    generate
        // assign west input and east output
        for (i = 0; i < ROW_NUM; i = i + 1) begin
            assign we_wires[i][0] = wests[i];
            assign easts[i] = we_wires[i][COL_NUM];
        end
        // assign north input and south output
        for (j = 0; j < COL_NUM; j = j + 1) begin
            assign ns_wires[0][j] = norths[j];
            assign souths[j] = ns_wires[ROW_NUM][j];
        end

        // create the systolic array
        for (i = 0; i < ROW_NUM; i = i + 1) begin
            for (j = 0; j < COL_NUM; j = j + 1) begin
                systolic_ws_pe #(DATA_WIDTH) spe
                (
                    .clk(clk),
                    .reset(reset),

                    .north(ns_wires[i][j]),
                    .west(we_wires[i][j]),

                    .weight(weights[i][j]),

                    .south(ns_wires[i+1][j]),
                    .east(we_wires[i][j+1]),
                    
                    .mul_out()
                );
            end
        end
    endgenerate

endmodule

`endif
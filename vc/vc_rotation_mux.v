module vc_rotation_mux_back_pipe
#(
    parameter DATA_WIDTH = 32,
    parameter NUM_ELEMENTS = 16,
    // parameters below are not meant to be set manually
    parameter ADDR_WIDTH = $clog2(NUM_ELEMENTS)
)(
    input   logic                       clk,
    input   logic   [DATA_WIDTH - 1:0]  data_in     [0:NUM_ELEMENTS - 1],
    input   logic   [ADDR_WIDTH - 1:0]  addr_in,
    output  logic   [DATA_WIDTH - 1:0]  data_out    [0:NUM_ELEMENTS - 1]
);

// rotational mux

genvar i;
generate
    for (i = 0; i < NUM_ELEMENTS; i = i + 1) begin
        always_ff @(posedge clk) begin
            data_out[i] <= data_in[(i + addr_in) % NUM_ELEMENTS];
            // if (i+addr_in < NUM_ELEMENTS) 
            //     data_out[i] <= data_in[i+addr_in];
            // else
            //     data_out[i] <= data_in[i+addr_in-NUM_ELEMENTS];
        end
    end
endgenerate

endmodule

module vc_rotation_mux_back_comb
#(
    parameter DATA_WIDTH = 32,
    parameter NUM_ELEMENTS = 16,
    // parameters below are not meant to be set manually
    parameter ADDR_WIDTH = $clog2(NUM_ELEMENTS)
)(
    input   logic   [DATA_WIDTH - 1:0]  data_in     [0:NUM_ELEMENTS - 1],
    input   logic   [ADDR_WIDTH - 1:0]  addr_in,
    output  logic   [DATA_WIDTH - 1:0]  data_out    [0:NUM_ELEMENTS - 1]
);

// rotational mux

genvar i;
generate
    for (i = 0; i < NUM_ELEMENTS; i = i + 1) begin
        always_comb begin
            data_out[i] = data_in[(i + addr_in) % NUM_ELEMENTS];
            // if (i+addr_in < NUM_ELEMENTS) 
            //     data_out[i] <= data_in[i+addr_in];
            // else
            //     data_out[i] <= data_in[i+addr_in-NUM_ELEMENTS];
        end
    end
endgenerate

endmodule

module vc_rotation_mux_forward_pipe
#(
    parameter DATA_WIDTH = 32,
    parameter NUM_ELEMENTS = 16,
    // parameters below are not meant to be set manually
    parameter ADDR_WIDTH = $clog2(NUM_ELEMENTS)
)(
    input   logic                       clk,
    input   logic   [DATA_WIDTH - 1:0]  data_in     [0:NUM_ELEMENTS - 1],
    input   logic   [ADDR_WIDTH - 1:0]  addr_in,
    output  logic   [DATA_WIDTH - 1:0]  data_out    [0:NUM_ELEMENTS - 1]
);

// rotational mux

genvar i;
generate
    for (i = 0; i < NUM_ELEMENTS; i = i + 1) begin
        always_ff @(posedge clk) begin
            data_out[i] <= data_in[(i - addr_in) % NUM_ELEMENTS];
            // if (i-addr_in >= 0) 
            //     data_out[i] <= data_in[i-addr_in];
            // else
            //     data_out[i] <= data_in[i-addr_in+NUM_ELEMENTS];
        end
    end
endgenerate

endmodule

module vc_rotation_mux_forward_comb
#(
    parameter DATA_WIDTH = 32,
    parameter NUM_ELEMENTS = 16,
    // parameters below are not meant to be set manually
    parameter ADDR_WIDTH = $clog2(NUM_ELEMENTS)
)(
    input   logic   [DATA_WIDTH*NUM_ELEMENTS - 1:0]  data_in,
    input   logic   [ADDR_WIDTH - 1:0]  addr_in,
    output  logic   [DATA_WIDTH*NUM_ELEMENTS - 1:0]  data_out
);

// rotational mux

genvar i;
generate
    for (i = 0; i < NUM_ELEMENTS; i = i + 1) begin

        logic [ADDR_WIDTH - 1:0] addr_sel_signal;
        assign addr_sel_signal = (i - addr_in) % NUM_ELEMENTS;
        always_comb begin
            data_out[(i+1)*DATA_WIDTH-1:i*DATA_WIDTH] = data_in[(addr_sel_signal+1)*DATA_WIDTH-1:addr_sel_signal*DATA_WIDTH];
            // if (i-addr_in >= 0) 
            //     data_out[i] <= data_in[i-addr_in];
            // else
            //     data_out[i] <= data_in[i-addr_in+NUM_ELEMENTS];
        end
    end
endgenerate

endmodule
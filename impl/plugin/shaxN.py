from structure.plugin import Plugin

class ShaxNPlugin(Plugin):
    """
    Plugin to add N chained instances of sha benchmark (from https://docs.verilogtorouting.org/en/latest/vtr/benchmarks/) alongside a main PluginDesign.
    """

    def check_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Default keys:
        * sha_num: N, default = 10
        """
        if 'sha_num' not in params:
            params['sha_num'] = 10
        
        return params
    
    def get_name(self, sha_num: int, **kwargs):
        return f"shax{sha_num}"
    
    def get_includes(self, **kwargs) -> str:
        return '`include "vtr_full_benchmarks/sha.v"'

    def get_pins(self, **kwargs) -> str:
        return """
    // form a long chain of N shas.
    // inputs -> sha 0 -> sha 1 -> sha 2 -> outputs
    input   sha_rst_i, 	    // global reset input , active high
	input	[31:0]	sha_text_i,	// text input 32bit
	output	[31:0]	sha_text_o,    // text output 32bit
	input	[2:0]	sha_cmd_i,	// command input
	input	sha_cmd_w_i,     // command input write enable
	output	[3:0]	sha_cmd_o	// command output(status)
"""

    def get_module(self, clk_pin: str, sha_num: int, **kwargs) -> str:
        return f"""
    // make intermediate wires.
    logic [31:0] sha_text_int[0:{sha_num}];
    logic [3:0] sha_cmd_int[0:{sha_num}];

    // assign initial and ending.
    assign sha_text_int[0] = sha_text_i;
    assign sha_text_o = sha_text_int[{sha_num}];
    assign sha_cmd_int[0] = {{ sha_cmd_i, sha_cmd_w_i }};
    assign sha_cmd_o = sha_cmd_int[{sha_num}];

    genvar i;
    generate
        for (i = 0; i < {sha_num}; i = i+1) begin : sha_block
            sha1 sha_inst
            (
                .clk_i({clk_pin}),

                .rst_i(sha_rst_i),
                .text_i(sha_text_int[i]),
                .text_o(sha_text_int[i+1]),
                .cmd_i(sha_cmd_int[i][3:1]),
                .cmd_w_i(sha_cmd_int[i][0]),
                .cmd_o(sha_cmd_int[i+1])
            );
        end
    endgenerate
"""
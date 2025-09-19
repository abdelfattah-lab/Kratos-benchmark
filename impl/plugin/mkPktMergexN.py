from structure.plugin import Plugin

class MkPktMergexNPlugin(Plugin):
    """
    Plugin to add N chained instances of mkPktMerge benchmark (from https://docs.verilogtorouting.org/en/latest/vtr/benchmarks/) alongside a main PluginDesign.
    """

    def check_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        Default keys:
        * mpm_num: N, default = 10
        """
        if 'mpm_num' not in params:
            params['mpm_num'] = 10
        
        return params
    
    def get_name(self, mpm_num: int, **kwargs):
        return f"mpmx{mpm_num}"
    
    def get_includes(self, **kwargs) -> str:
        return '`include "vtr_full_benchmarks/mkPktMerge.v"'

    def get_pins(self, **kwargs) -> str:
        return """
    // form a long chain of N mkPktMerges.
    // use output as duplicate inputs to both ports.
    // inputs -> 0 -> 1 -> ... -> outputs
    input  mpm_RST_N,

    // action method iport_put
    input  [152 : 0] mpm_iport_put,
    input  mpm_EN_iport_put,

    // actionvalue method oport_get
    output [152 : 0] mpm_oport_get,
    output mpm_RDY_oport_get
"""

    def get_module(self, clk_pin: str, mpm_num: int, **kwargs) -> str:
        return f"""
    // make intermediate wires.
    logic [152:0] mpm_port_int[0:{mpm_num}];
    logic mpm_signal_int[0:{mpm_num}];
    logic mpm_signal_merge0[0:{mpm_num-1}];
    logic mpm_signal_merge1[0:{mpm_num-1}];
    logic mpm_signal_merge_and[0:{mpm_num-1}];

    // assign initial and ending.
    assign mpm_port_int[0] = mpm_iport_put;
    assign mpm_oport_get = mpm_port_int[{mpm_num}];
    assign mpm_signal_int[0] = mpm_EN_iport_put;
    assign mpm_RDY_oport_get = mpm_signal_int[{mpm_num}];

    genvar i;
    generate
        for (i = 0; i < {mpm_num}; i = i+1) begin : mpm_block
            assign mpm_signal_merge_and[i] = mpm_signal_merge0[i] & mpm_signal_merge1[i];
            mkPktMerge mpm_inst
            (
                .CLK({clk_pin}),
                .RST_N(mpm_RST_N),

                .iport0_put(mpm_port_int[i]),
                .EN_iport0_put(mpm_signal_int[i]),
                .RDY_iport0_put(mpm_signal_merge0[i]),
                
                .iport1_put(mpm_port_int[i]),
                .EN_iport1_put(mpm_signal_int[i]),
                .RDY_iport1_put(mpm_signal_merge1[i]),

                .oport_get(mpm_port_int[i+1]),
                .EN_oport_get(mpm_signal_merge_and[i]),
                .RDY_oport_get(mpm_signal_int[i+1])
            );
        end
    endgenerate
"""
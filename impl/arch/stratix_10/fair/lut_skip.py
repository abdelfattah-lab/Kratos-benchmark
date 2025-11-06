"""
Taken from https://github.com/verilog-to-routing/vtr-verilog-to-routing/blob/master/vtr_flow/arch/COFFE_22nm/stratix10_arch.xml, as-is.

Modified:
- Breakable carry chains (set cin_mux_stride = 0 to revert to original)
- LUT skipping in arithmetic mode, and passing adder outputs directly into sneak paths
"""

from structure.arch import ArchFactory
from structure.util import ParamsChecker
import util.netstats as ns
import os

from lxml.etree import Element

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = open(os.path.join(BASE_DIR, 'base.xml'), 'r', encoding='utf-8').read()

def gen_carry_chain_links(ble_count=10, mux_stride=1):
    # mux inputs from FLE 2 - N
    mux_ins = ''
    if ble_count > 1:
        mux_ins_strs = []
        for x in range(1, ble_count):
          is_mux = x % mux_stride == 0 if mux_stride > 0 else False
          tag = 'mux' if is_mux else 'direct'
          
          # TO-DO: adjust mux delay
          tag_delay = '15.58e-12' if is_mux else '0.01e-12'
          
          mux_delay_lab = f'<delay_constant max="{tag_delay}" in_port="lab.cin" out_port="fle[{x}:{x}].cin"/>\n            ' if is_mux else ''
          mux_ins_strs.append(f"""          <{tag} name="cin{x}" input="{'lab.cin ' if is_mux else ''}fle[{x-1}:{x-1}].cout" output="fle[{x}:{x}].cin">
            {mux_delay_lab}<delay_constant max="{tag_delay}" in_port="fle[{x-1}:{x-1}].cout" out_port="fle[{x}:{x}].cin"/>
          </{tag}>
""")
          mux_ins = '\n'.join(mux_ins_strs)

    return f"""
          <direct name="carry_in" input="lab.cin" output="fle[0:0].cin">
            <!-- corresponds to LAB-LAB cin driver. -->
            <delay_constant max="20.18e-12" in_port="lab.cin" out_port="fle[0:0].cin"/>
            <pack_pattern name="chain_arith" in_port="lab.cin" out_port="fle[0:0].cin"/>
          </direct>
{mux_ins}
<direct name="couts" input="fle[{ble_count-1}:{ble_count-1}].cout" output="lab.cout">
    <pack_pattern name="chain_arith" in_port="fle[{ble_count-1}:{ble_count-1}].cout" out_port="lab.cout"/>
</direct>
"""   

def gen_lut6():
    return """<mode name="n1_lut6">
            <pb_type name="ble6" num_pb="1">
              <input name="in" num_pins="6"/>
              <output name="out" num_pins="4"/>
              <clock name="clk" num_pins="1"/>
              <pb_type name="lut6" blif_model=".names" num_pb="1" class="lut">
                <input name="in" num_pins="6" port_class="lut_in"/>
                <output name="out" num_pins="1" port_class="lut_out"/>
                <!-- LUT timing using delay matrix -->
                <!-- These are the physical delay inputs on a Stratix 10 LUT but because VPR cannot do LUT rebalancing,
                           we instead take the average of these numbers to get more stable results
                           231.11e-12
                           232.93e-12
                           177.84e-12
                           174.73e-12
                           104.73e-12
                           76.51e-12
                      -->
                <delay_matrix type="max" in_port="lut6.in" out_port="lut6.out">
                        166.31e-12
                        166.31e-12
                        166.31e-12
                        166.31e-12
                        166.31e-12
                        166.31e-12
                    </delay_matrix>
              </pb_type>
              <pb_type name="ff" blif_model=".latch" num_pb="2" class="flipflop">
                <input name="D" num_pins="1" port_class="D"/>
                <output name="Q" num_pins="1" port_class="Q"/>
                <clock name="clk" num_pins="1" port_class="clock"/>
                <T_setup value="18.91e-12" port="ff.D" clock="clk"/>
                <T_clock_to_Q max="60.32e-12" port="ff.Q" clock="clk"/>
              </pb_type>
              <interconnect>
                <direct name="lut6_inputs" input="ble6.in" output="lut6.in"/>
                <direct name="lut6_ff" input="lut6.out" output="ff[1].D">
                  <delay_constant max="15.2e-12" in_port="lut6.out" out_port="ff[1].D"/>
                  <pack_pattern name="ble6" in_port="lut6.out" out_port="ff[1].D"/>
                </direct>
                <complete name="clock" input="ble6.clk" output="ff.clk"/>
                <direct name="input_to_ff" input="ble6.in[0]" output="ff[0].D">
                  <delay_constant max="15.58e-12" in_port="ble6.in[0]" out_port="ff[0].D"/>
                </direct>
                <mux name="O1" input="ble6.in[0] ff[0].Q lut6.out" output="ble6.out[0]">
                  <delay_constant max="63.99e-12" in_port="ble6.in[0]" out_port="ble6.out[0]"/>
                  <delay_constant max="48.41e-12" in_port="lut6.out" out_port="ble6.out[0]"/>
                  <delay_constant max="48.41e-12" in_port="ff[0].Q" out_port="ble6.out[0]"/>
                </mux>
                <mux name="O3" input="ff[1].Q lut6.out" output="ble6.out[2]">
                  <delay_constant max="58.69e-12" in_port="lut6.out" out_port="ble6.out[2]"/>
                  <delay_constant max="43.49e-12" in_port="ff[1].Q" out_port="ble6.out[2]"/>
                </mux>
              </interconnect>
            </pb_type>
            <interconnect>
              <!-- ble6 takes inputs A, B, C, D, E, & F; where F is fle[7] -->
              <direct name="lut6_inputs1" input="fle.in[4:0]" output="ble6.in[4:0]"/>
              <direct name="lut6_inputs2" input="fle.in[7]" output="ble6.in[5]"/>
              <direct name="direct2" input="ble6.out" output="fle.out"/>
              <direct name="direct4" input="fle.clk" output="ble6.clk"/>
            </interconnect>
          </mode>
          <!-- n1_lut6 -->"""

def gen_layout_sizing(fixed_size: tuple[int, int]|None):
    if fixed_size is None:
        return '<auto_layout aspect_ratio="1.0">', '</auto_layout>'
    
    w, h = fixed_size
    return f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">', '</fixed_layout>'

DEFAULTS = {
    'cin_mux_stride': 0, # insert a 2:1 MUX in the carry chain every ? ALMs.
    'enable_lut6': True, # turn on/off 6-LUT mode
    'per_fle_area': 2248.0434, # LAB area / 10
    'fixed_size': None, # (w, h) of fixed size, None for auto sizing
}

class LUTSkipArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, cin_mux_stride: int, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-skip_cin.{cin_mux_stride}"
        if not enable_lut6:
            name += "_l6.off"
        if fixed_size is not None:
            w, h = fixed_size
            name += f"_fs.{w}x{h}"
        return name
    
    def verify_params(self, params):
        return self.verify_required_keys(DEFAULTS, [], params)
    
    def get_arch(self, cin_mux_stride: int, enable_lut6: bool, per_fle_area: float, fixed_size: tuple[int, int]|None, **kwargs):
        layout_sizing_start, layout_sizing_end = gen_layout_sizing(fixed_size)
        
        return TEMPLATE.format(
            carry_chain_links=gen_carry_chain_links(mux_stride=cin_mux_stride),
            mode_lut6=gen_lut6() if enable_lut6 else '',
            grid_logic_tile_area=per_fle_area * 10,
            layout_sizing_start=layout_sizing_start,
            layout_sizing_end=layout_sizing_end,
        )
    
    def should_update_netstats(self, netstats: dict[str, any]) -> bool:
        """
        Check for required keys.
        Update this function when you update get_netstats.
        """
        required_keys = ['lut4_wires', 'concurrent_lut5s']
        for key in required_keys:
            if key not in netstats:
                return True
        
        return False

    def get_netstats(self, root: Element) -> dict[str, any]:
        """
        Gets the following statistics:
        - lut4_wires: int -> number of 4-LUTs used as a wire.
        - concurrent_lut5s: int -> number of 5-LUTs used together with adders.

        Update should_update_netstats with keys produced by the latest implementation of this function.
        """
        lut4_wires = 0
        concurrent_lut5s = 0

        for arith_block in ns.find_all_block_instances(root, 'arithmetic[0]'):
            # concurrent 5-LUT check
            adder_block = ns.get_valid_child_block_instance(arith_block, 'adder[0]')
            lut5_block= ns.get_valid_child_block_mode(arith_block, 'as_lut5')
            if (adder_block is not None) and (lut5_block is not None):
                concurrent_lut5s += 1

            # 4-LUT wire check
            lut4s_block = ns.get_valid_child_block_mode(arith_block, 'as_dual_lut4s')
            if lut4s_block is not None:
                lut4_wire0 = ns.get_valid_child_block_instance(arith_block, 'lut4[0]', check_valid=ns.check_element_is_wire)
                lut4_wire1 = ns.get_valid_child_block_instance(arith_block, 'lut4[1]', check_valid=ns.check_element_is_wire)
                lut4_wires += (not lut4_wire0 is None) + (not lut4_wire1 is None)
        return dict(
            lut4_wires=lut4_wires,
            concurrent_lut5s=concurrent_lut5s,
        )

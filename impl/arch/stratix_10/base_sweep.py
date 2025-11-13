"""
Taken from https://github.com/verilog-to-routing/vtr-verilog-to-routing/blob/master/vtr_flow/arch/COFFE_22nm/stratix10_arch.xml, as-is.

!NOTE: should be used with a fixed routing channel width of 400.
"""

from structure.arch import ArchFactory
from structure.util import ParamsChecker
import util.netstats as ns
from pathlib import Path

from lxml import etree as ET


BASE_DIR = Path(__file__).resolve().parent
XML_DIR = BASE_DIR / 'xml'

TEMPLATE = (XML_DIR / 'sweep_base.xml').read_text(encoding='utf-8')

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
    'per_fle_area': 2167.3155, # LAB area / 10
    'enable_lut6': True, # turn on/off 6-LUT mode
    'fixed_size': None, # (w, h) of fixed size, None for auto sizing
    'fle_per_clb': 10,
}

class BaseSweepArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, enable_lut6: bool, fixed_size: tuple[int, int]|None, fle_per_clb: int = 10, **kwargs):
        name = "type.s10-base"
        if not enable_lut6:
            name += "_l6.off"
        if fixed_size is not None:
            w, h = fixed_size
            name += f"_fs.{w}x{h}"
        if fle_per_clb != 10:
            name += f"_fle.{fle_per_clb}"
        return name
    
    def verify_params(self, params):
        filled = self.verify_required_keys(DEFAULTS, [], params)
        fle_per_clb = int(filled.get('fle_per_clb', 10))
        if fle_per_clb <= 0:
            raise ValueError("fle_per_clb must be a positive integer.")
        if fle_per_clb > 10:
            raise ValueError("fle_per_clb > 10 is not supported by BaseSweepArchFactory.")
        filled['fle_per_clb'] = fle_per_clb
        return filled
    
    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, fle_per_clb: int = 10, **kwargs):
        layout_sizing_start, layout_sizing_end = gen_layout_sizing(fixed_size)
        grid_logic_tile_area = per_fle_area * fle_per_clb
        lab_output_pins = fle_per_clb * 4
        
        base_xml = TEMPLATE.format(
            grid_logic_tile_area=grid_logic_tile_area,
            mode_lut6=gen_lut6() if enable_lut6 else '',
            layout_sizing_start=layout_sizing_start,
            layout_sizing_end=layout_sizing_end,
            fle_per_clb=fle_per_clb,
            lab_output_pins=lab_output_pins,
        )
        return self._customize_fle_count(base_xml, fle_per_clb)

    def _customize_fle_count(self, xml_str: str, fle_per_clb: int) -> str:
        root = ET.fromstring(xml_str)
        fle_full_range = f"{fle_per_clb - 1}:0"
        lab_interconnect = root.xpath(".//pb_type[@name='lab']/interconnect")[0]
        clb_interconnect = root.xpath(".//pb_type[@name='clb']/interconnect")[0]
        directlist = root.xpath(".//directlist")[0]

        def update_complete(name: str, output: str):
            nodes = lab_interconnect.xpath(f"./complete[@name='{name}']")
            if nodes:
                nodes[0].set('output', output)

        lut_names = ['lutA', 'lutB', 'lutC', 'lutD', 'lutE', 'lutF', 'lutG', 'lutH']
        for idx, name in enumerate(lut_names):
            update_complete(name, f"fle[{fle_full_range}].in[{idx}:{idx}]")

        update_complete('clks', f"fle[{fle_full_range}].clk")

        labout_names = ['labouts1', 'labouts2', 'labouts3', 'labouts4']
        lab_o_ranges = [
            f"{(i + 1) * fle_per_clb - 1}:{i * fle_per_clb}"
            for i in range(4)
        ]
        for idx, name in enumerate(labout_names):
            nodes = lab_interconnect.xpath(f"./direct[@name='{name}']")
            if nodes:
                nodes[0].set('input', f"fle[{fle_full_range}].out[{idx}]")
                nodes[0].set('output', f"lab.O[{lab_o_ranges[idx]}]")

        def update_direct_with_children(node, attr_name, new_value):
            node.set(attr_name, new_value)
            for child in node:
                target_attr = 'out_port' if attr_name == 'output' else 'in_port'
                port = child.get(target_attr)
                if port and port.startswith('fle['):
                    child.set(target_attr, new_value)

        carry_in = lab_interconnect.xpath("./direct[@name='carry_in']")
        if carry_in:
            update_direct_with_children(carry_in[0], 'output', "fle[0:0].cin")

        carry_out = lab_interconnect.xpath("./direct[@name='carry_out']")
        last_idx = fle_per_clb - 1
        if carry_out:
            update_direct_with_children(carry_out[0], 'input', f"fle[{last_idx}:{last_idx}].cout")

        carry_link = lab_interconnect.xpath("./direct[@name='carry_link']")
        if fle_per_clb > 1:
            if carry_link:
                node = carry_link[0]
                update_direct_with_children(node, 'input', f"fle[{last_idx - 1}:0].cout")
                update_direct_with_children(node, 'output', f"fle[{last_idx}:1].cin")
        else:
            for node in carry_link:
                node.getparent().remove(node)

        def compute_segments(total: int, count: int) -> list[int]:
            base = total // count
            remainder = total % count
            return [base + (1 if i < remainder else 0) for i in range(count)]

        def remove_nodes(nodes):
            for node in nodes:
                node.getparent().remove(node)

        total_outputs = fle_per_clb * 4
        direct_specs = [
            ('direct_right_1', 'I1', 5),
            ('direct_right_2', 'I2', 5),
            ('direct_right_3', 'I3', 5),
            ('direct_right_4', 'I4', 5),
            ('direct_left_1', 'I1', 10),
            ('direct_left_2', 'I2', 10),
            ('direct_left_3', 'I3', 10),
            ('direct_left_4', 'I4', 10),
        ]
        segments = compute_segments(total_outputs, len(direct_specs))
        start = 0
        MAX_SEG_LEN = 5
        direct_ranges: dict[str, tuple[int, int, int]] = {}

        for seg_len, (name, port, target_base) in zip(segments, direct_specs):
            nodes = directlist.xpath(f"./direct[@name='{name}']")
            if not nodes:
                continue
            if seg_len == 0:
                remove_nodes(nodes)
                continue
            if seg_len > MAX_SEG_LEN:
                raise ValueError("fle_per_clb setting exceeds available direct connection pins.")
            node = nodes[0]
            hi = start + seg_len - 1
            lo = start
            start += seg_len
            node.set('from_pin', f"clb.O[{hi}:{lo}]")
            direct_ranges[name] = (lo, hi, seg_len)
            target_hi = target_base + seg_len - 1
            node.set('to_pin', f"clb.{port}[{target_hi}:{target_base}]")

        feedback_map = {
            'Input_feedback_I1': 'direct_right_1',
            'Input_feedback_I3': 'direct_right_3',
            'Input_feedback_I2': 'direct_left_1',
            'Input_feedback_I4': 'direct_left_3',
        }
        for fb_name, direct_name in feedback_map.items():
            nodes = clb_interconnect.xpath(f"./complete[@name='{fb_name}']")
            if not nodes:
                continue
            range_info = direct_ranges.get(direct_name)
            if not range_info or range_info[2] == 0:
                remove_nodes(nodes)
                continue
            lo, hi, _ = range_info
            nodes[0].set('input', f"lab.O[{hi}:{lo}]")

        return ET.tostring(root, encoding='unicode', pretty_print=True)
    
    def should_update_netstats(self, netstats):
        """
        Check for required keys.
        Update this function when you update get_netstats.
        """
        required_keys = ['lut4_wires']
        for key in required_keys:
            if key not in netstats:
                return True
        
        return False
    
    def get_netstats(self, root):
        """
        Gets the following statistics:
        - lut4_wires: int -> number of 4-LUTs used as a wire.
        - concurrent_lut5s: int -> number of 5-LUTs used together with adders.

        Update should_update_netstats with keys produced by the latest implementation of this function.
        """
        lut4_wires = 0
        
        for arith_block in ns.find_all_block_instances(root, 'arithmetic[0]'):
            lut4_wire0 = ns.get_valid_child_block_instance(arith_block, 'lut4[0]', check_valid=ns.check_element_is_wire)
            lut4_wire1 = ns.get_valid_child_block_instance(arith_block, 'lut4[1]', check_valid=ns.check_element_is_wire)
            lut4_wires += (not lut4_wire0 is None) + (not lut4_wire1 is None)
        
        return dict(
            lut4_wires=lut4_wires,
            concurrent_lut5s=0,
        )

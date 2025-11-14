"""
Sweepable Stratix-10 double carry-chain FLE architectures.

Split from four_bit_adder.py so we can provide alternate input-feedback mappings.
"""

from pathlib import Path

from lxml import etree as ET

from structure.arch import ArchFactory
from structure.util import ParamsChecker

BASE_DIR = Path(__file__).resolve().parent
XML_DIR = BASE_DIR / 'xml'

TEMPLATE_SWEEP = (XML_DIR / 'sweep_4bit_adder_dcc2.xml').read_text(encoding='utf-8')
TEMPLATE_FAITHFUL = (XML_DIR / 'sweep_4bit_adder_dcc2_faithful.xml').read_text(encoding='utf-8')


def gen_layout_sizing(fixed_size: tuple[int, int] | None):
    if fixed_size is None:
        return '<auto_layout aspect_ratio="1.0">', '</auto_layout>'

    w, h = fixed_size
    return f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">', '</fixed_layout>'


DEFAULTS = {
    'per_fle_area': 2443.995,
    'enable_lut6': True,
    'fixed_size': None,
}


def _build_arch(
    template: str,
    include_clb_feedback_inputs: bool,
    per_fle_area: float,
    fixed_size: tuple[int, int] | None,
    fle_per_clb: int,
):
    layout_sizing_start, layout_sizing_end = gen_layout_sizing(fixed_size)
    grid_logic_tile_area = per_fle_area * fle_per_clb
    lab_output_pins = fle_per_clb * 4
    num_carry_chains = 2 if fle_per_clb > 5 else 1

    base_xml = template.format(
        grid_logic_tile_area=grid_logic_tile_area,
        fle_per_clb=fle_per_clb,
        layout_sizing_start=layout_sizing_start,
        layout_sizing_end=layout_sizing_end,
        lab_output_pins=lab_output_pins,
        num_carry_chains=num_carry_chains,
    )

    return _customize_fle_count(base_xml, fle_per_clb, include_clb_feedback_inputs)


def _customize_fle_count(xml_str: str, fle_per_clb: int, include_clb_feedback_inputs: bool) -> str:
    root = ET.fromstring(xml_str)

    lab_output_pins = fle_per_clb * 4
    first_half = min(fle_per_clb, 5)
    second_half = max(fle_per_clb - 5, 0)
    has_second_chain = second_half > 0
    num_chains = 1 + int(has_second_chain)
    fle_full_range = f"{fle_per_clb - 1}:0"

    def set_num_pins(xpath: str, value: int):
        for elem in root.xpath(xpath):
            elem.set('num_pins', str(value))

    for target in ['.//tile[@name=\'clb\']//input[@name=\'cin\']',
                   './/pb_type[@name=\'clb\']/input[@name=\'cin\']',
                   './/pb_type[@name=\'lab\']/input[@name=\'cin\']']:
        set_num_pins(target, num_chains)

    for target in ['.//tile[@name=\'clb\']//output[@name=\'cout\']',
                   './/pb_type[@name=\'clb\']/output[@name=\'cout\']',
                   './/pb_type[@name=\'lab\']/output[@name=\'cout\']']:
        set_num_pins(target, num_chains)

    for target in ['.//tile[@name=\'clb\']//output[@name=\'O\']',
                   './/pb_type[@name=\'clb\']/output[@name=\'O\']',
                   './/pb_type[@name=\'lab\']/output[@name=\'O\']']:
        set_num_pins(target, lab_output_pins)

    lab_interconnect = root.xpath(".//pb_type[@name='lab']/interconnect")[0]
    clb_interconnect = root.xpath(".//pb_type[@name='clb']/interconnect")[0]
    directlist = root.xpath(".//directlist")[0]

    def get_chunk_range(group_idx: int, chunk_idx: int):
        if chunk_idx == 0:
            length = first_half
            offset = 0
        else:
            length = second_half
            offset = first_half
        if length <= 0:
            return None
        base = group_idx * fle_per_clb + offset
        hi = base + length - 1
        return hi, base, length

    lut_names = ['lutA', 'lutB', 'lutC', 'lutD', 'lutE', 'lutF', 'lutG', 'lutH']
    for idx, name in enumerate(lut_names):
        nodes = lab_interconnect.xpath(f"./complete[@name='{name}']")
        if nodes:
            nodes[0].set('output', f"fle[{fle_full_range}].in[{idx}:{idx}]")

    clk_nodes = lab_interconnect.xpath("./complete[@name='clks']")
    if clk_nodes:
        clk_nodes[0].set('output', f"fle[{fle_full_range}].clk")

    lab_o_ranges = [f"{(i + 1) * fle_per_clb - 1}:{i * fle_per_clb}" for i in range(4)]
    labout_names = ['labouts11', 'labouts12', 'labouts13', 'labouts14']
    for idx, name in enumerate(labout_names):
        nodes = lab_interconnect.xpath(f"./direct[@name='{name}']")
        if nodes:
            nodes[0].set('input', f"fle[{fle_full_range}].out[{idx}]")
            nodes[0].set('output', f"lab.O[{lab_o_ranges[idx]}]")

    def remove_node(node_list):
        for node in node_list:
            parent = node.getparent()
            parent.remove(node)

    def update_chain(chain_idx: int, start_idx: int, length: int):
        carry_in = lab_interconnect.xpath(f"./direct[@name='carry_in{chain_idx}']")
        carry_out = lab_interconnect.xpath(f"./direct[@name='carry_out{chain_idx}']")
        carry_link = lab_interconnect.xpath(f"./direct[@name='carry_link{chain_idx}']")

        if length <= 0:
            remove_node(carry_in + carry_out + carry_link)
            return

        end_idx = start_idx + length - 1
        fle_cin = f"fle[{start_idx}:{start_idx}].cin"
        fle_cout = f"fle[{end_idx}:{end_idx}].cout"

        if carry_in:
            node = carry_in[0]
            node.set('output', fle_cin)
            for child in node:
                out_port = child.get('out_port')
                if out_port and out_port.startswith('fle['):
                    child.set('out_port', fle_cin)

        if carry_out:
            node = carry_out[0]
            node.set('input', fle_cout)
            for child in node:
                in_port = child.get('in_port')
                if in_port and in_port.startswith('fle['):
                    child.set('in_port', fle_cout)

        if length > 1:
            link_in = f"fle[{end_idx - 1}:{start_idx}].cout"
            link_out = f"fle[{end_idx}:{start_idx + 1}].cin"
            if carry_link:
                node = carry_link[0]
                node.set('input', link_in)
                node.set('output', link_out)
                for child in node:
                    in_port = child.get('in_port')
                    if in_port and in_port.startswith('fle['):
                        child.set('in_port', link_in)
                    out_port = child.get('out_port')
                    if out_port and out_port.startswith('fle['):
                        child.set('out_port', link_out)
        else:
            remove_node(carry_link)

    update_chain(1, 0, first_half)
    update_chain(2, 5, second_half)

    def update_feedback(name: str, clb_port: str, group_idx: int, chunk_idx: int):
        nodes = clb_interconnect.xpath(f"./complete[@name='{name}']")
        if not nodes:
            return
        rng = get_chunk_range(group_idx, chunk_idx)
        inputs: list[str] = []
        if include_clb_feedback_inputs:
            inputs.append(f"clb.{clb_port}")
        if rng:
            hi, lo, _ = rng
            inputs.append(f"lab.O[{hi}:{lo}]")
        if not inputs:
            remove_node(nodes)
            return
        nodes[0].set('input', ' '.join(inputs))

    update_feedback('Input_feedback_I1', 'I1', 0, 0)
    update_feedback('Input_feedback_I2', 'I2', 2, 0)
    update_feedback('Input_feedback_I3', 'I3', 0, 1)
    update_feedback('Input_feedback_I4', 'I4', 2, 1)

    if not has_second_chain:
        for name in ['carry_in2', 'carry_out2']:
            nodes = clb_interconnect.xpath(f"./direct[@name='{name}']")
            remove_node(nodes)

    def update_direct(name: str, group_idx: int, chunk_idx: int, target_port: str, target_low: int):
        nodes = directlist.xpath(f"./direct[@name='{name}']")
        if not nodes:
            return
        rng = get_chunk_range(group_idx, chunk_idx)
        if rng is None:
            remove_node(nodes)
            return
        hi, lo, length = rng
        node = nodes[0]
        node.set('from_pin', f"clb.O[{hi}:{lo}]")
        target_high = target_low + length - 1
        node.set('to_pin', f"clb.{target_port}[{target_high}:{target_low}]")

    direct_specs = [
        ('direct_right_1', 0, 0, 'I1', 5),
        ('direct_right_2', 2, 0, 'I2', 5),
        ('direct_right_3', 0, 1, 'I3', 5),
        ('direct_right_4', 2, 1, 'I4', 5),
        ('direct_left_1', 1, 0, 'I1', 10),
        ('direct_left_2', 3, 0, 'I2', 10),
        ('direct_left_3', 1, 1, 'I3', 10),
        ('direct_left_4', 3, 1, 'I4', 10),
    ]
    for spec in direct_specs:
        update_direct(*spec)

    if not has_second_chain:
        remove_node(directlist.xpath("./direct[@name='adder_carry2']"))

    return ET.tostring(root, encoding='unicode', pretty_print=True)


class FourBitDCC2SweepArchFactory(ArchFactory, ParamsChecker):
    """Matches the previous sweep behaviour (CLB inputs visible in feedback)."""

    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int] | None,
                 fle_per_clb: int = 10, **kwargs):
        name = "type.s10-chain_2"
        if fle_per_clb != 10:
            name += f"_fle.{fle_per_clb}"
        return name

    def verify_params(self, params):
        filled = self.verify_required_keys(DEFAULTS, [], params)
        filled['per_fle_area'] = 2520.19
        fle_per_clb = int(params.get('fle_per_clb', 10))
        if fle_per_clb <= 0:
            raise ValueError("fle_per_clb must be a positive integer")
        filled['fle_per_clb'] = fle_per_clb
        return filled

    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int] | None,
                 fle_per_clb: int = 10, **kwargs):
        return _build_arch(
            TEMPLATE_SWEEP,
            True,
            per_fle_area,
            fixed_size,
            fle_per_clb,
        )


class FourBitDCC2SweepFaithfulArchFactory(ArchFactory, ParamsChecker):
    """Feedback-only version that mirrors the base architecture's wiring."""

    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int] | None,
                 fle_per_clb: int = 10, **kwargs):
        name = "type.s10-chain_2_faithful"
        if fle_per_clb != 10:
            name += f"_fle.{fle_per_clb}"
        return name

    def verify_params(self, params):
        filled = self.verify_required_keys(DEFAULTS, [], params)
        filled['per_fle_area'] = 2520.19
        fle_per_clb = int(params.get('fle_per_clb', 10))
        if fle_per_clb <= 0:
            raise ValueError("fle_per_clb must be a positive integer")
        filled['fle_per_clb'] = fle_per_clb
        return filled

    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int] | None,
                 fle_per_clb: int = 10, **kwargs):
        return _build_arch(
            TEMPLATE_FAITHFUL,
            False,
            per_fle_area,
            fixed_size,
            fle_per_clb,
        )

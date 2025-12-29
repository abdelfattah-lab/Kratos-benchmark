"""
Taken from https://github.com/verilog-to-routing/vtr-verilog-to-routing/blob/master/vtr_flow/arch/COFFE_22nm/stratix10_arch.xml, as-is.

Modified:
- Breakable carry chains (set cin_mux_stride = 0 to revert to original)
- LUT skipping in arithmetic mode, and passing adder outputs directly into sneak paths
"""

from structure.arch import ArchFactory
from structure.util import ParamsChecker
import util.netstats as ns
from pathlib import Path

from lxml import etree as ET
from lxml.etree import Element

BASE_DIR = Path(__file__).resolve().parent
XML_DIR = BASE_DIR / 'xml'
TEMPLATE = (XML_DIR / '4bit_adder_dcc3_lut_skip.xml').read_text(encoding='utf-8')

def gen_layout_sizing(fixed_size: tuple[int, int]|None):
    if fixed_size is None:
        return '<auto_layout aspect_ratio="1.0">', '</auto_layout>'
    
    w, h = fixed_size
    return f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">', '</fixed_layout>'

DEFAULTS = {
    # Note: per_fle_area is used by the reporting pipeline (e.g., area_fle = fle * per_fle_area).
    # The XML templates below hard-code grid_logic_tile_area. Keep this default in sync per-class.
    # This base DEFAULTS is used by DCC1; DCC2/DCC3 override in verify_params.
    'per_fle_area': 2443.995, # DCC1: grid_logic_tile_area 24439.95 => /10
    'enable_lut6': True, # turn on/off 6-LUT mode
    'fixed_size': None, # (w, h) of fixed size, None for auto sizing
}


class LUTSkipDCC3ArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-skip_chain_3"
        return name
    
    def verify_params(self, params):
        # DCC3 template uses grid_logic_tile_area=25241.08 (small)
        filled = self.verify_required_keys(DEFAULTS, [], params)
        filled['per_fle_area'] = 2604.8359
        return filled
    
    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        # Inject fixed layout sizing if requested; otherwise return template as-is
        if fixed_size is None:
            return TEMPLATE
        w, h = fixed_size
        s = TEMPLATE
        s = s.replace('<auto_layout aspect_ratio="1.0">', f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">')
        s = s.replace('</auto_layout>', '</fixed_layout>')
        return s

    def should_update_netstats(self, netstats: dict[str, any]) -> bool:
        """
        Check for required keys.
        Update this function when you update get_netstats.
        """
        required_keys = ['concurrent_lut5s']
        for key in required_keys:
            if key not in netstats:
                return True

        return False

    def get_netstats(self, root: Element) -> dict[str, any]:
        """
        Gets the following statistics:
        - concurrent_lut5s: int -> number of 5-LUTs used together with adders.

        Update should_update_netstats with keys produced by the latest implementation of this function.
        """
        concurrent_lut5s = 0

        for arith_block in ns.find_all_block_instances(root, 'arithmetic[0]'):
            # concurrent 5-LUT check: look for dual_lut4s in as_lut5 mode AND an active adder
            lut5_block = ns.get_valid_child_block_mode(arith_block, 'as_lut5')
            adder0_block = ns.get_valid_child_block_instance(arith_block, 'adder[0]')
            adder1_block = ns.get_valid_child_block_instance(arith_block, 'adder[1]')

            # Count as concurrent if LUT5 is used AND at least one adder is active
            if lut5_block is not None and (adder0_block is not None or adder1_block is not None):
                concurrent_lut5s += 1

        return dict(
            concurrent_lut5s=concurrent_lut5s,
        )


CONCURRENT_ADDER_TEMPLATE = (XML_DIR / '4bit_adder_dcc3_adder_skip.xml').read_text(encoding='utf-8')

ADDER_SKIP_DEFAULTS = {
    'per_fle_area': 2604.8359,  # DCC3 template uses grid_logic_tile_area=25241.08 (small)
    'enable_lut6': True,  # turn on/off 6-LUT mode
    'fixed_size': None,  # (w, h) of fixed size, None for auto sizing
}


class AdderSkipDCC3ArchFactory(ArchFactory, ParamsChecker):
    """
    Architecture factory for concurrent adder usage in DCC3.

    This architecture enables concurrent use of both adder chains by adding
    2 direct inputs that mux at the sumout link point (instead of 4 inputs
    at the LUT output as in LUT skip).
    """

    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-adder_skip_chain_3"
        return name

    def verify_params(self, params):
        filled = self.verify_required_keys(ADDER_SKIP_DEFAULTS, [], params)
        filled['per_fle_area'] = 2604.8359
        return filled

    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        # Inject fixed layout sizing if requested; otherwise return template as-is
        if fixed_size is None:
            return CONCURRENT_ADDER_TEMPLATE
        w, h = fixed_size
        s = CONCURRENT_ADDER_TEMPLATE
        s = s.replace('<auto_layout aspect_ratio="1.0">', f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">')
        s = s.replace('</auto_layout>', '</fixed_layout>')
        return s

    def should_update_netstats(self, netstats: dict[str, any]) -> bool:
        """
        Check for required keys.
        Update this function when you update get_netstats.
        """
        required_keys = ['concurrent_adders']
        for key in required_keys:
            if key not in netstats:
                return True

        return False

    def get_netstats(self, root: Element) -> dict[str, any]:
        """
        Gets the following statistics:
        - concurrent_adders: int -> number of adder pairs used concurrently (via simple_chain).

        Update should_update_netstats with keys produced by the latest implementation of this function.
        """
        concurrent_adders = 0

        for arith_block in ns.find_all_block_instances(root, 'arithmetic[0]'):
            # concurrent adder check: both adder[0] and adder[1] are active
            adder0_block = ns.get_valid_child_block_instance(arith_block, 'adder[0]')
            adder1_block = ns.get_valid_child_block_instance(arith_block, 'adder[1]')

            # Count as concurrent if both adders are active
            if adder0_block is not None and adder1_block is not None:
                concurrent_adders += 1

        return dict(
            concurrent_adders=concurrent_adders,
        )

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

BASE_DIR = Path(__file__).resolve().parent
XML_DIR = BASE_DIR / 'xml'

TEMPLATE_DCC1 = (XML_DIR / '4bit_adder_dcc1.xml').read_text(encoding='utf-8')
TEMPLATE_DCC2 = (XML_DIR / '4bit_adder_dcc2.xml').read_text(encoding='utf-8')
TEMPLATE_DCC2_FAITHFUL = (XML_DIR / '4bit_adder_dcc2_faithful.xml').read_text(encoding='utf-8')
TEMPLATE_DCC3 = (XML_DIR / '4bit_adder_dcc3.xml').read_text(encoding='utf-8')
TEMPLATE_DCC3_EXP = (XML_DIR / '4bit_adder_dcc3_exp.xml').read_text(encoding='utf-8')

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

class DCC1ArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        # Distinguish single-chain vs. double-chain in the generated folder name
        name = f"type.s10-chain_1"
        return name
    
    def verify_params(self, params):
        # DCC1 template uses grid_logic_tile_area=24439.95
        filled = self.verify_required_keys(DEFAULTS, [], params)
        filled['per_fle_area'] = 2443.995
        return filled
    
    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        # Inject fixed layout sizing if requested; otherwise return template as-is
        if fixed_size is None:
            return TEMPLATE_DCC1
        w, h = fixed_size
        s = TEMPLATE_DCC1
        s = s.replace('<auto_layout aspect_ratio="1.0">', f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">')
        s = s.replace('</auto_layout>', '</fixed_layout>')
        return s


class DCC2ArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-chain_2"
        return name
    
    def verify_params(self, params):
        # DCC2 template uses grid_logic_tile_area=25201.9
        filled = self.verify_required_keys(DEFAULTS, [], params)
        filled['per_fle_area'] = 2520.19
        return filled
    
    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        # Inject fixed layout sizing if requested; otherwise return template as-is
        if fixed_size is None:
            return TEMPLATE_DCC2
        w, h = fixed_size
        s = TEMPLATE_DCC2
        s = s.replace('<auto_layout aspect_ratio="1.0">', f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">')
        s = s.replace('</auto_layout>', '</fixed_layout>')
        return s

class DCC2FaithfulArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-chain_2"
        return name
    
    def verify_params(self, params):
        # DCC2 template uses grid_logic_tile_area=25201.9
        filled = self.verify_required_keys(DEFAULTS, [], params)
        filled['per_fle_area'] = 2520.19
        return filled
    
    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        # Inject fixed layout sizing if requested; otherwise return template as-is
        if fixed_size is None:
            return TEMPLATE_DCC2_FAITHFUL
        w, h = fixed_size
        s = TEMPLATE_DCC2_FAITHFUL
        s = s.replace('<auto_layout aspect_ratio="1.0">', f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">')
        s = s.replace('</auto_layout>', '</fixed_layout>')
        return s


class DCC3ArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-chain_3"
        return name

    def verify_params(self, params):
        # DCC3 template uses grid_logic_tile_area=25241.08 (small)
        filled = self.verify_required_keys(DEFAULTS, [], params)
        filled['per_fle_area'] = 2524.108
        return filled

    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        # Inject fixed layout sizing if requested; otherwise return template as-is
        if fixed_size is None:
            return TEMPLATE_DCC3
        w, h = fixed_size
        s = TEMPLATE_DCC3
        s = s.replace('<auto_layout aspect_ratio="1.0">', f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">')
        s = s.replace('</auto_layout>', '</fixed_layout>')
        return s


class DCC3ExpArchFactory(ArchFactory, ParamsChecker):
    """DCC3 experimental architecture with single FF per arithmetic mode."""
    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-chain_3_exp"
        return name

    def verify_params(self, params):
        # DCC3 Exp uses same grid_logic_tile_area=25241.08 as DCC3
        filled = self.verify_required_keys(DEFAULTS, [], params)
        filled['per_fle_area'] = 2524.108
        return filled

    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        # Inject fixed layout sizing if requested; otherwise return template as-is
        if fixed_size is None:
            return TEMPLATE_DCC3_EXP
        w, h = fixed_size
        s = TEMPLATE_DCC3_EXP
        s = s.replace('<auto_layout aspect_ratio="1.0">', f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">')
        s = s.replace('</auto_layout>', '</fixed_layout>')
        return s

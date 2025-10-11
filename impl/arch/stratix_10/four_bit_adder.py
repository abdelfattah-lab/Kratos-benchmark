"""
Taken from https://github.com/verilog-to-routing/vtr-verilog-to-routing/blob/master/vtr_flow/arch/COFFE_22nm/stratix10_arch.xml, as-is.

Modified:
- Breakable carry chains (set cin_mux_stride = 0 to revert to original)
- LUT skipping in arithmetic mode, and passing adder outputs directly into sneak paths
"""

from structure.arch import ArchFactory
from structure.util import ParamsChecker
import util.netstats as ns

from lxml.etree import Element

# Override TEMPLATE to read from external file as requested
TEMPLATE_SINGLE = open('/home/ayf7/repos/Kratos-benchmark/impl/arch/stratix_10/4bit_adder_single_chain_arch.xml', 'r', encoding='utf-8').read()
TEMPLATE_DOUBLE = open('/home/ayf7/repos/Kratos-benchmark/impl/arch/stratix_10/4bit_adder_single_chain_arch.xml', 'r', encoding='utf-8').read()

def gen_layout_sizing(fixed_size: tuple[int, int]|None):
    if fixed_size is None:
        return '<auto_layout aspect_ratio="1.0">', '</auto_layout>'
    
    w, h = fixed_size
    return f'<fixed_layout name="fixed_arch_size" width="{w}" height="{h}">', '</fixed_layout>'

DEFAULTS = {
    'per_fle_area': 2167.3155, # LAB area / 10
    'enable_lut6': True, # turn on/off 6-LUT mode
    'fixed_size': None, # (w, h) of fixed size, None for auto sizing
}

class FourBitSingleChainArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-chain_2"
        return name
    
    def verify_params(self, params):
        return self.verify_required_keys(DEFAULTS, [], params)
    
    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        return TEMPLATE_SINGLE


class FourBitDoubleChainArchFactory(ArchFactory, ParamsChecker):
    def get_name(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        name = f"type.s10-chain_2"
        return name
    
    def verify_params(self, params):
        return self.verify_required_keys(DEFAULTS, [], params)
    
    def get_arch(self, per_fle_area: float, enable_lut6: bool, fixed_size: tuple[int, int]|None, **kwargs):
        return TEMPLATE_DOUBLE
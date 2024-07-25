from structure.util import ParamsChecker, DynamicallyNamed

class Design(DynamicallyNamed, ParamsChecker):
    """
    {abstract}
    Specifies a design to be used for an experiment.
    Final products:
    - TCL & SDC files (Quartus-only)
    - Wrapper file (design.v)
    """

    def __init__(self, impl: str, module_dir: str, wrapper_module_name: str):
        self.impl = impl
        self.module_dir = module_dir
        if wrapper_module_name is None and impl is not None:
            wrapper_module_name = f"{impl}_wrapper"
        self.wrapper_module_name = wrapper_module_name
    
    def gen_sdc(self, **kwargs) -> str:
        """
        Generate an SDC file (Quartus-only).
        """
        self.raise_unimplemented("gen_sdc")
    
    def gen_tcl(self, **kwargs) -> str:
        """
        Generate a TCL file (Quartus-only).
        """
        self.raise_unimplemented("gen_tcl")

    def gen_wrapper(self, **kwargs):
        """
        Generate a wrapper file.
        """
        self.raise_unimplemented("gen_wrapper")


DEFAULTS_SDC = {
    'clock': 1
}
class StandardizedSdcDesign(Design):
    """
    Design with standardized SDC file.
    """

    def gen_sdc(self, **kwargs) -> str:
        """
        Optional arguments:
        *clock_time:int, clock time, default: DEFAULT_CLOCK_TIME
        """
        use_params = self.autofill_defaults(DEFAULTS_SDC, kwargs)
        template = f"create_clock -period {use_params['clock']} [get_ports clk]"
        return template
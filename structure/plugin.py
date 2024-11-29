from structure.util import DynamicallyNamed

class Plugin(DynamicallyNamed):
    """
    Passed into PluginDesign to add additional module(s) alongside the main Verilog module.
    """
    def check_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        {abstract}
        Check if Design parameters also includes required Plugin parameters.
        """
        self.raise_unimplemented('check_params')

    def get_includes(self, **kwargs) -> str:
        """
        {abstract}
        Returns the Verilog includes needed for the plug-in.
        """
        self.raise_unimplemented('get_includes')

    def get_pins(self, **kwargs) -> str:
        """
        {abstract}
        Returns the set of pins to add alongside the main Verilog module pins.
        """
        self.raise_unimplemented('get_pins')
    
    def get_module(self, clk_pin: str, **kwargs) -> str:
        """
        {abstract}
        Returns the Verilog module to place alongside the main Verilog module.

        Required arguments:
        * clk_pin: str, clock input used by the main Design.
        """
        self.raise_unimplemented('get_module')
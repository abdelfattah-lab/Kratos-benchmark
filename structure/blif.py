from structure.design import Design

class BlifDesign(Design):
    """
    {abstract}
    Generate a custom .blif file to be used directly with VPR, skipping synthesis.
    """
    def __init__(self):
        super().__init__('', '', '')

    def gen_blif(self, **kwargs) -> str:
        """
        {abstract}
        Generate a .blif file.
        """
        self.raise_unimplemented("gen_blif")
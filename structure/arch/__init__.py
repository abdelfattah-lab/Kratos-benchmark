from structure.util import DynamicallyNamed

class ArchFactory(DynamicallyNamed):
    """
    {abstract}
    Factory that generates an architecture XML file from provided parameters.
    """

    def get_arch(self, **kwargs) -> str:
        """
        {abstract}
        Refer to concrete ArchFactory class for specification.

        @return "arch.xml" file, in a single string.
        """
        self.raise_unimplemented("get_arch")
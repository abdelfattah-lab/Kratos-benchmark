"""
Basic utility classes.
"""

class Abstract():
    """
    Simulate abstract behaviour of standard OOP languages e.g. Java.
    """
    def raise_unimplemented(method_name: str) -> None:
        """
        Use as stub for methods that are meant to be abstract.
        """
        raise RuntimeError(f"Unimplemented method {method_name}()!")
    
class ParamsChecker(Abstract):
    """
    Used for classes which take in a set of parameters.
    Enable checking of default against provided parameters.
    """
    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        """
        {abstract}
        Verify that parameters are as required, and simultaneously fill defaults.
        """
        self.raise_unimplemented("verify_params")

    def autofill_defaults(self, defaults: dict[str, any], params: dict[str, any], print_warning: bool = False) -> dict[str, any]:
        """
        Checks parameters against provided defaults, and only modifies defaults if available.
        """
        ret = defaults.copy()
        default_keys = defaults.keys()

        for k, v in params.items():
            if k in ret:
                ret[k] = v
            elif print_warning:
                print(f"[{self.__class__.__name__}]: Could not find key {k} in default keys {default_keys}, ignoring value {v}.")

        return ret
    
    def verify_required_keys(self, defaults: dict[str, any], required_keys: list[str], params: dict[str, any]) -> dict[str, any]:
        """
        Enforces a list of required keys in the provided parameters, and fills the rest with defaults.
        (Note that the required keys should be distinct from the default keys, i.e., an error will be thrown as long as params does not have a required key.)
        """
        ret = defaults.copy()
        required_keys_left = required_keys.copy()

        for k, v in params.items():
            ret[k] = v # override/add to defaults
            if k in required_keys_left:
                required_keys_left.remove(k) # remove key if exists
        
        if len(required_keys_left) > 0:
            # not all required keys are seen
            raise ValueError(f"Provided parameters:\n{params}\n\nis missing the following keys:\n{required_keys_left}")
        
        return ret
    
class DynamicallyNamed(Abstract):
    """
    Used for classes that have to provide a dynamic name based on its properties.
    """

    def get_name(self, **kwargs) -> str:
        """
        Get a dynamic name based on the kwargs provided.
        @returns name in string
        """
        self.raise_unimplemented("get_name")
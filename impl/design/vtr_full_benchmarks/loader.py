from structure.design import StandardizedSdcDesign

import os

DEFAULTS = {
    'verilog_dir': 'verilog/vtr_full_benchmarks',
}

class VtrBenchmarkLoaderDesign(StandardizedSdcDesign):
    """
    Loads a full VTR Verilog benchmark.
    """
    def __init__(self):
        super().__init__('', '', '')

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        return self.verify_required_keys(DEFAULTS, ['subset', 'impl'], params)
    
    def get_name(self, subset: str, impl: str, **kwargs):
        return f"{subset}-{impl}"

    def get_formal_name(self) -> str:
        return 'vtr-loader'

    def gen_wrapper(self, verilog_dir: str, impl: str, **kwargs):
        assert os.path.exists(verilog_dir)

        impl_path = os.path.join(verilog_dir, f"{impl}.v")
        assert os.path.exists(impl_path)

        impl_file = open(impl_path, 'r')
        impl_str = impl_file.read()
        impl_file.close()

        return impl_str
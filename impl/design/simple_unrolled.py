from structure.design import StandardizedSdcDesign
from structure.consts.shared_defaults import DEFAULTS_TCL
from structure.consts.shared_requirements import REQUIRED_KEYS_SIMPLE_UNROLLED

from structure.consts.quartus import DEVICE_FAMILY, DEVICE_NAME, TURN_OFF_DSPS

from util.bit_gen import gen_verilog_random_hex_constant

class SimpleUnrolledDesign(StandardizedSdcDesign):
    def __init__(self, impl: str = 'simple_unrolled', module_dir: str = 'simple_unrolled', wrapper_module_name: str = 'simple_unrolled_wrapper'):
        super().__init__(impl, module_dir, wrapper_module_name)

    def get_name(self, data_width: int, const_weight: int, **kwargs) -> str:
        return f'i.{self.impl}_d.{data_width}_c.{const_weight}'
    
    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        return self.verify_required_keys({}, REQUIRED_KEYS_SIMPLE_UNROLLED, params)
    
    def gen_tcl(self, wrapper_file_name: str, **kwargs) -> str:
        """
        Generate TCL file.

        Required arguments:
        wrapper_file_name:str, top level file name

        Optional arguments (defaults to DEFAULTS_TCL):
        output_dir:str, reports output directory
        parallel_processors_num:int, number of parallel processors
        execute_flow_type: 'compile' or 'implement' (prime only)
        """
        kwargs = self.autofill_defaults(DEFAULTS_TCL, kwargs)
        output_dir = kwargs['output_dir']
        parallel_processors_num = kwargs['parallel_processors_num']
        execute_flow_type = kwargs['execute_flow_type']
        template = f'''# load packages
load_package flow

# new project
project_new -revision v1 -overwrite {self.impl}

# device
set_global_assignment -name FAMILY "{DEVICE_FAMILY}"
set_global_assignment -name DEVICE {DEVICE_NAME}

# misc
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY {output_dir}
set_global_assignment -name NUM_PARALLEL_PROCESSORS {parallel_processors_num}
set_global_assignment -name SDC_FILE flow.sdc

# seed
set_global_assignment -name SEED 114514

# files
set_global_assignment -name TOP_LEVEL_ENTITY {self.wrapper_module_name}
set_global_assignment -name SYSTEMVERILOG_FILE {wrapper_file_name}

# virtual pins
set_instance_assignment -name VIRTUAL_PIN ON -to clk
set_instance_assignment -name VIRTUAL_PIN ON -to reset


set_instance_assignment -name VIRTUAL_PIN ON -to val_in
set_instance_assignment -name VIRTUAL_PIN ON -to rdy_in
set_instance_assignment -name VIRTUAL_PIN ON -to weights[*][*][*]

set_instance_assignment -name VIRTUAL_PIN ON -to src_data_in[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to src_wraddr[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to src_wr_en[*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_rdaddr[*][*]
set_instance_assignment -name VIRTUAL_PIN ON -to result_data_out[*][*]


# effort level
set_global_assignment -name OPTIMIZATION_MODE "HIGH PERFORMANCE EFFORT"

# turn DSPs off
{TURN_OFF_DSPS}

# run compilation
execute_flow -{execute_flow_type}


# close project
project_close
'''

        return template
    
    def gen_wrapper(self, data_width: int, const_weight: int, **kwargs) -> str:
        template = f"""module {self.wrapper_module_name} #(
	DATA_WIDTH = {data_width}
)
(
	input [DATA_WIDTH - 1:0] a,
	output reg [2 * DATA_WIDTH - 1:0] s,
	input clk
);
	wire [DATA_WIDTH-1:0] b = {data_width}'d{const_weight};
	always @ (posedge clk) begin
		s <= a * b;
	end
endmodule
"""

        return template
    
    def gen_tb_params(self, data_width, **kwargs):
        return dict(
            cycles=dict(
                reset=1,
                hold=1,
            ),
            pins=dict(
                clk='clk',
                input=[('a', data_width)],
                output=[('s', 2 * data_width)],   
            )
        )
    
    def gen_test_case(self, data_width, **kwargs):
        return f"a = {gen_verilog_random_hex_constant(data_width)};"
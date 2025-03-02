DEVICE_FAMILY = "Stratix 10"
DEVICE_NAME = "1SG250HH1F55E1VG" # https://www.intel.com/content/www/us/en/products/sku/210289/intel-stratix-10-gx-2500-fpga/specifications.html

TURN_OFF_DSPS = """set_global_assignment -name DSP_BLOCK_BALANCING_IMPLEMENTATION "LOGIC ELEMENTS"
set_global_assignment -name MAX_BALANCING_DSP_BLOCKS 0
set_global_assignment -name AUTO_DSP_RECOGNITION OFF
"""

EXECUTE_FLOW_TYPE = "implement" # change accordingly before use
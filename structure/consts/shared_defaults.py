"""
Defaults that are shared across multiple implementations.
"""

DEFAULTS_EXP = {
    'stdout_file': 'std.out',
    'stderr_file': 'std.err',
}

DEFAULTS_EXP_QUARTUS = {
    **DEFAULTS_EXP,
    'output_dir': 'outputs',
}

DEFAULTS_TCL = {
    'output_dir': 'output',
    'parallel_processors_num': 4
}

# Wrapper defaults
DEFAULTS_WRAPPER = {
    'constant_weight': True
}
DEFAULTS_WRAPPER_CONV = {
    'separate_filters': False,
    **DEFAULTS_WRAPPER
}
DEFAULTS_WRAPPER_CONV_2D = {
    'buffer_stages': 0,
    **DEFAULTS_WRAPPER_CONV
}
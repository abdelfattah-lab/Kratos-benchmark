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
    'constant_weight': True,
    'sparsity': 0.0,
    'clock': 1
}
DEFAULTS_WRAPPER_CONV = {
    'buffer_stages': 0,
    'kernel_only': False,
    'separate_filters': False,
    **DEFAULTS_WRAPPER
}
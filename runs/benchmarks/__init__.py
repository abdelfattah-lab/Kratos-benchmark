import structure.consts.keys as keys

import os.path as path
from copy import deepcopy

def get_params(base_params: dict[str, any], exp_root_dir: str, design_params: dict[str, any]) -> dict[str, any]:
    """
    Populate base parameters with experiment-specific parameters.

    Required arguments:
    * base_params:dict[str, any], base parameters to add to.
    * exp_root_dir:str, the name of the experiment's root directory. Will be created with parent 'experiments'.
    * design_params:dict[str, any], design specific parameters.
    """
    params = deepcopy(base_params)
    params[keys.KEY_EXP] |= {
        'root_dir': path.join('experiments', exp_root_dir)
    }
    params[keys.KEY_DESIGN] |= design_params

    return params
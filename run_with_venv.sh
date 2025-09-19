#!/bin/bash

# This is intended to use a Python virtualenv (as opposed to conda or other virtual environments).

# Change these parameters to your system.
DEFAULT_VTR_ROOT="/media/samsdrive/vtr-exploration/vtr-updated/"    # Default VTR path to use, if VTR_ROOT is not set.
VENV_ROOT_PATH="/media/samsdrive/vtr-exploration/venv/"             # Path to the virtual-env root.
SCRIPT_FILE="run.py"                                                # change this to the Python script to run.

if [ -z ${VTR_ROOT} ]; then
    export VTR_ROOT=$DEFAULT_VTR_ROOT
fi

. "${VENV_ROOT_PATH}/bin/activate"
python -u $SCRIPT_FILE # run with unbuffered output (to work with parent bash script's nohup)
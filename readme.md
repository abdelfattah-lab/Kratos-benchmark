# Repository for Kratos FPGA benchmark

## code structure

folder `conv_1d`, `conv_2d`, `gemms`, `gemmt` contains the SystemVerilog code for the corresponding benchmarks, including the module and wrapper generate script.

The `flow_general.py` contains two classes of `QuartusRunner` and `VTRRunner` for automatically running the benchmark set.

## Kernel table

![kernel_table](<./kernel table.png>)

## Usage

Use the `sample.py` as a example: First import the `flow_general.py` to import necessary tools. Then create a dictionary to specify the parameters of a kernel. Next, create a `VTRRunner` object with the kernel module and the parameters. Finally, run the kernel with `run` method and get the result with `get_result` method. The runner will create a folder in current directory to store the generated files and the result. Standard output and standard error of the running process will be captured and stored in the folder.


``` python
from flow_general import *

settings = {
    'data_width': 8,
    'row_num': 8,
    'col_num': 8,
    'length': 8,
    'sparsity': 0.5,
}

q = VTRRunner(flow_gemmt_fu_util, settings)
q.run()
q.wait()
print(q.get_result())
```

For more advanced usage, please read the comment and the code in `flow_general.py`.
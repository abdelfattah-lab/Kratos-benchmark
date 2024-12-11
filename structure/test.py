"""
The 'tb_params' used by functions in this class follow the following format:
{
    'cycles': {
        'reset': <number of cycles to pump all inputs to 0>,
        'hold': <number of cycles to wait after initial input>,
    },
    'pins': {
        'clk': <clock pin name>,
        'input': [
            (<input pin name>, <size>), 
            ...
        ],
        'output': [
            (<output pin name>, <size>), 
            ...
        ],
    }
}
"""

from structure.util import Abstract

import os
import re
from typing import Callable

# line separator
LINE_SEP = '|'
# Mark a line as mismatch
MISMATCH_TAG = '<!MISMATCH!>'

class VerilogImplTester(Abstract):
    """
    {abstract}
    Generates and runs a testbench comparing a post VTR implementation Verilog module with its pre-VTR design.
    """

    def _get_module_name(self, module_path: str) -> str:
        """
        Get the first module name of the provided file.
        
        Required arguments:
        * module_path: str, absolute path of module file
        """

        if not os.path.exists(module_path):
            raise ValueError(f"Cannot find module file at path {module_path}!")
        
        with open(module_path, 'r') as f:
            for line in f:
                if line.startswith("module "):
                    # Get module name from line
                    module_name_pattern = r"module (\w+)"
                    module_name_match = re.search(module_name_pattern, line)
                    if not module_name_match:
                        raise ValueError("Cannot find module name in specified module file!")
                    return module_name_match.group(1)

    def _prep_post_impl_module_file(self, post_impl_module_path: str) -> None:
        """
        Edits the post-implementation Verilog netlist:
        1. appends '_post_impl' to the module name to differentiate it from the original module.

        Required arguments:
        * post_impl_module_path: str, absolute path to the verilog file containing the module file for testing. 
        """
        
        if not os.path.exists(post_impl_module_path):
            raise ValueError(f"Cannot find module file at path {post_impl_module_path}!")
        
        # find module name
        post_impl_module_name = self._get_module_name(post_impl_module_path)

        # write postfix if not already done.
        postfix = '_post_impl'
        if not post_impl_module_name.endswith(postfix):
            # replace and re-write file.
            rf = open(post_impl_module_path, 'r')
            file_str = rf.read().replace(post_impl_module_name, post_impl_module_name + postfix)
            rf.close()
            with open(post_impl_module_path, 'w') as wf:
                wf.write(file_str)

    def _gen_testbench(self, tb_params: dict[str, dict[str, any]], test_case_generator: Callable[[], str], module_name: str, post_impl_module_path: str, test_cases: int = 1000) -> str:
        """
        Generates a testbench for the given module name.
        Please prepare the post-implementation netlist with _prep_post_impl_module_file first.

        Required arguments:
        * tb_params: dict[str, dict[str, any]], tb_params as per top of the file.
        * test_case_generator: () -> str, get a set of inputs for the next test case.
        * module_name: str, module name of the initial module.
        * post_impl_module_path: str, absolute path to the verilog file containing the module file for testing.

        Optional arguments:
        * test_cases: int, number of random test cases to run.
        """

        if not os.path.exists(post_impl_module_path):
            raise ValueError(f"Cannot find module file at path {post_impl_module_path}!")
        
        # Get information from module file
        post_impl_module_name = ""
        available_pins = {
            'input': set(),
            'output': set(),
        }
        with open(post_impl_module_path, 'r') as f:
            module_file_str = f.read()

            # grab module name
            module_name_pattern = r"module (\w+)"
            module_name_match = re.search(module_name_pattern, module_file_str)
            if not module_name_match:
                raise ValueError("Cannot find module name in specified module file!")
            post_impl_module_name = module_name_match.group(1)

            # grab pins
            io_pin_pattern = r"([a-z]{2,3}put) (\\?\w+\~?\d*)"
            io_pins_match = re.findall(io_pin_pattern, module_file_str)
            for pin_type, pin in io_pins_match:
                available_pins[pin_type].add(pin)

        
        tb_pins = tb_params['pins']
        module_pin_mappings = []
        post_impl_pin_mappings = []
        post_impl_zero_assigns = []
        # Generate module pin mappings
        for key, value in tb_pins.items():

            if key == 'clk':
                # add clock mappings
                module_pin_mappings.append(f".{value}({value})")

                clk_pin = value
                if clk_pin not in available_pins["input"]:
                    clk_pin = f"\{value}"
                    if clk_pin not in available_pins["input"]:
                        raise ValueError("Cannot find clock pin!")
                
                post_impl_pin_mappings.append(f".{clk_pin} ({value})")
                continue
            
            available_pins_set = available_pins[key]
            pre_prefix = "pre_" if key == 'output' else ''
            post_prefix = "post_" if key == 'output' else ''
            for pin_name, size in value:
                # post-implementation mappings
                if size > 1:
                    for i in range(size):
                        pin = f"\{pin_name}~{i}"
                        if pin in available_pins_set:
                            post_impl_pin_mappings.append(f".{pin} ({post_prefix}{pin_name}[{i}])")
                        elif key == 'output':
                            post_impl_zero_assigns.append(f"assign {post_prefix}{pin_name}[{i}] = 1'b0;")
                else:
                    if pin in available_pins_set:
                        post_impl_pin_mappings.append(f".{pin} ({post_prefix}{pin_name})")
                
                # module mappings
                module_pin_mappings.append(f".{pin_name}({pre_prefix}{pin_name})")

        def gen_random_testcase():
            output_checks = []
            for pin_name, size in tb_pins['output']:
                output_checks.append(f"""$display("{pin_name}{LINE_SEP}%h{LINE_SEP}%h", pre_{pin_name}, post_{pin_name});
if (pre_{pin_name} !== post_{pin_name}) begin
    $display("{MISMATCH_TAG}{pin_name}{LINE_SEP}%h{LINE_SEP}%h", pre_{pin_name}, post_{pin_name});
    $display("bit mask: %h", pre_{pin_name} ^ post_{pin_name});
end""")
            return f"{test_case_generator()}\n# {10 * tb_params['cycles']['hold']}\n{chr(10).join(output_checks)}"

        # write final file.
        return f"""module {module_name}_tb;
logic clk;
{chr(10).join([f"logic [{size-1}:0] {pin_name};" for pin_name, size in tb_pins['input']])}
{chr(10).join([f"logic [{size-1}:0] pre_{pin_name};" for pin_name, size in tb_pins['output']])}
{chr(10).join([f"logic [{size-1}:0] post_{pin_name};" for pin_name, size in tb_pins['output']])}

// rising edge every 10 steps
always # 5 clk = !clk;

// instantiate both modules
{module_name} pre_mod (
{(','+chr(10)).join(module_pin_mappings)}
);
{post_impl_module_name} post_mod (
{(','+chr(10)).join(post_impl_pin_mappings)}
);

// tie unused outputs to 0
{chr(10).join(post_impl_zero_assigns)}

initial begin

// reset sequence
clk = 0;
{chr(10).join([f"{pin_name} = 0;" for pin_name, _ in tb_pins['input']])}
# {10 * tb_params['cycles']['reset']}

// random input testing
{chr(10).join([gen_random_testcase() for _ in range(test_cases)])}

$finish;
end
endmodule
"""
    
    def _process_tb_outputs(self, output_pins: list[tuple[str, int]], out_file_path: str) -> dict[str, dict[str, int]]:
        """
        Process the output file of the tester used, and track $display messages starting with:
        - MISMATCH_TAG: indicates a mismatch between pre and post-implementation output.

        Required arguments:
        * output_pins: [(<output_pin>, <size>), ...], i.e., tb_params['pins']['output'].
        * out_file_path: str, output file of the testbench program used. Put a text file where the $display messages will be visible.

        returns {<output_pin>: {
            <tag>: <statistic>,
            ...
        }}
        """
        # sanity checks
        if not os.path.exists(out_file_path):
            raise ValueError(f"Provided out file {out_file_path} does not exist!")
        
        # Make return dictionary
        stats = {
            k: {
                MISMATCH_TAG: 0
            }
            for k, _ in output_pins
        }

        # helper function: hex character to integer
        def get_int_value(c: str) -> int:
            if c.isdigit():
                return int(c)
            
            return 10 + ord(c) - ord('a')

        # count statistics
        with open(out_file_path, 'r') as out_file:
            line = out_file.readline().strip()

            while line:
                if line.startswith(MISMATCH_TAG):
                    # mismatch error found; count mismatched bits
                    output_pin, pre_val, post_val = line.replace(MISMATCH_TAG, '').split(LINE_SEP)
                    mismatches = 0
                    for pre_c, post_c in zip(pre_val.lower(), post_val.lower()):
                        if pre_c == post_c:
                            continue

                        # one set is high impedance; mark as entirely wrong
                        if pre_c == 'x' or post_c == 'x':
                            mismatches += 4
                        else:
                            mismatches += (get_int_value(pre_c) ^ get_int_value(post_c)).bit_count()
       
                    stats[output_pin][MISMATCH_TAG] += mismatches

                # get next line
                line = out_file.readline().strip()
        
        # return stats
        return stats
    
    def verify(self, tb_params: dict[str, dict[str, any]], test_case_generator: Callable[[], str],
               working_dir: str, pre_module_path: str, post_module_path: str, 
               include_dir: str|None = None, add_verilog_file_paths: list[str] = [], 
               test_cases: int = 1000) -> dict[str, any]:
        """
        {abstract}
        Generates the testbench and runs with a Verilog testbench runner of choice.

        Required arguments:
        * tb_params: as above
        * test_case_generator: () -> str, get a set of inputs for the next test case. 
        * working_dir: str, where to generate and run testbench files.
        * *_module_path: str, absolute paths pointing to the pre and post-implementation module files.
        
        Optional arguments:
        * include_dir: str, directory to include in verilog include directories. Default: None
        * add_verilog_file_paths: list[str], absolute paths to more verilog files to add alongside the generated files. Default: []
        * test_cases: int, number of random test cases to use. Default: 1000

        Returns:
        {
            'verified': True if verification passed, else False,
            'output_checks': <return from _process_tb_outputs>,
        } 
        Additional details should be written into a log file in the working directory.
        """
        self.raise_unimplemented('verify')
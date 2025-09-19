from structure.test import VerilogImplTester, MISMATCH_TAG
from util.flow import start_dependent_process

import os
import shutil
from typing import Callable

class IVerilogImplTester(VerilogImplTester):
    """
    VerilogImplTester that makes use of iverilog (https://github.com/steveicarus/iverilog).
    """

    def verify(self, tb_params: dict[str, dict[str, any]], test_case_generator: Callable[[], str], working_dir: str, pre_module_path: str, post_module_path: str, include_dir: str|None = None, add_verilog_file_paths: list[str] = [], test_cases: int = 1000) -> dict[str, any]:
        """
        iverilog verification.
        Report written to 'iverilog.report'
        """
        # sanity checks
        if shutil.which('iverilog') is None or shutil.which('vvp') is None:
            raise ValueError("Ensure iverilog and vvp are on PATH!")
        if not os.path.exists(working_dir):
            raise ValueError(f"Cannot find directory {working_dir}!")

        # Generate file information
        pre_module_name = self._get_module_name(pre_module_path)
        self._prep_post_impl_module_file(post_module_path)
        tb_file_str = self._gen_testbench(tb_params, test_case_generator, pre_module_name, post_module_path)
        
        # write vvp file
        tb_file_path = os.path.join(working_dir, f'{pre_module_name}_tb.v')
        with open(tb_file_path, 'w') as f:
            f.write(tb_file_str)
        vvp_out_path = os.path.join(working_dir, f'{pre_module_name}_vvp_exec')

        vvp_gen_cmd = ['iverilog', 
                       '-g', '2012', # latest systemverilog
                       '-o', vvp_out_path]
        if include_dir is not None:
            vvp_gen_cmd += ['-I', include_dir]
        
        vvp_gen_cmd += add_verilog_file_paths
        vvp_gen_cmd += [pre_module_path, post_module_path, tb_file_path]

        # make stdout and stderr files
        vvp_gen_stdout_path = os.path.join(working_dir, 'iverilog.out')
        vvp_gen_stderr_path = os.path.join(working_dir, 'iverilog.err')
        vvp_gen_stdout_file = open(vvp_gen_stdout_path, 'w')
        vvp_gen_stderr_file = open(vvp_gen_stderr_path, 'w')
        vvp_gen_stdout_file.write(" ".join(vvp_gen_cmd) + '\n')

        vvp_writer = start_dependent_process(vvp_gen_cmd, stdout=vvp_gen_stdout_file, stderr=vvp_gen_stderr_file)
        vvp_writer.wait()
        vvp_gen_stdout_file.close()
        vvp_gen_stderr_file.close()
        with open(vvp_gen_stderr_path, 'r') as vvp_gen_stderr_file:
            if vvp_writer.returncode != 0 or len(vvp_gen_stderr_file.read().strip()) > 0:
                raise RuntimeError(f"Failed iverilog, check {vvp_gen_stdout_path} and {vvp_gen_stderr_path}")
        
        # cleanup output files
        # os.remove(vvp_gen_stdout_path)
        os.remove(vvp_gen_stderr_path)

        # run vvp
        vvp_cmd = ['vvp', vvp_out_path]
        vvp_stdout_path = os.path.join(working_dir, 'vvp.out')
        vvp_stdout_file = open(vvp_stdout_path, 'w')

        vvp = start_dependent_process(vvp_cmd, stdout=vvp_stdout_file)
        vvp.wait()
        vvp_stdout_file.close()

        # process output file
        output_pins = tb_params['pins']['output']
        stats = self._process_tb_outputs(output_pins, vvp_stdout_path)

        # cleanup output file
        # os.remove(vvp_stdout_path)
        
        # generate return objects
        verified = True
        mismatch_lines = []
        for pin, size in output_pins:
            # check mismatches
            mismatches = stats[pin][MISMATCH_TAG]
            if mismatches > 0:
                verified = False
            
            total_size = size * test_cases
            correct = total_size - mismatches
            mismatch_lines.append(f"{pin.ljust(20)}: {correct}/{total_size} matched ({(correct/total_size*100):.2f}%)")
        
        # write report
        report_str = f"""Verification report:
--- OUTPUT MATCHING ---
{chr(10).join(mismatch_lines)}
"""
        with open(os.path.join(working_dir, 'iverilog.report'), 'w') as report_file:
            report_file.write(report_str)
        
        # return format
        return dict( 
            verified=verified,
            output_checks=stats,
        )

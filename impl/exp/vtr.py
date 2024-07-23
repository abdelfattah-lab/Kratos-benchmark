from structure.exp import Experiment
from structure.consts.shared_requirements import REQUIRED_KEYS_EXP
from util import extract_info_vtr, start_dependent_process

import os
from subprocess import DEVNULL

class VtrExperiment(Experiment):
    """
    VTR implementation of an Experiment.
    """

    def run(self, clean=True, dry_run=False, ending=None, seed=1127, **kwargs) -> None:
        """
        Run on VTR.

        dry_run: if True, only generate files, do not run VTR
        clean: if True, zip the temp files after VTR finishes to save space
        ending: ending stage of VTR, if None, run the whole flow, options: 'parmys', 'vpr'
        seed: random seed for VTR
        """
        self._prerun_check()

        # generic experiment setup
        self._setup_exp(REQUIRED_KEYS_EXP)

        # generate wrapper file
        wrapper_file_name = 'design.v'
        with open(os.path.join(self.exp_dir, wrapper_file_name), 'w') as f:
            f.write(self.design.gen_wrapper(**self.design_params))

        # generate architecture file
        arch_file_name = 'arch.xml'
        with open(os.path.join(self.exp_dir, arch_file_name), 'w') as f:
            f.write(self.arch.get_arch(**self.arch_params))

        if dry_run:
            print(f"""(!) Created under {self.exp_dir}:
- README file: {self.readme_file_name}
- Wrapper file: {wrapper_file_name}
- Architecture file: {arch_file_name}
>>> Dry run completed.""")
            return
        
        # Find VTR and define command
        vtr_root = os.environ.get('VTR_ROOT')
        if vtr_root is None:
            raise RuntimeError('VTR_ROOT not found in environment variables; unable to execute VTR.')
        vtr_script_path = os.path.join(vtr_root, 'vtr_flow/scripts/run_vtr_flow.py')
        cmd = ['python', vtr_script_path, wrapper_file_name, arch_file_name,
               '-parser', 'system-verilog', '-top', self.design_params['wrapper_module_name'], '-search', self.verilog_search_dir, '--seed', str(seed)]
        if ending is not None:
            cmd += ['-ending_stage', ending]
        
        # Make out and error files
        self.stdout_file = open(os.path.join(self.exp_dir, self.exp_params['stdout_file']), 'w')
        self.stderr_file = open(os.path.join(self.exp_dir, self.exp_params['stderr_file']), 'w')

        # start VTR on subprocess        
        self.process = start_dependent_process(cmd, stdout=self.stdout_file, stderr=self.stderr_file, cwd=self.exp_dir)

        # start GC thread
        self._start_gc_thread(self._clean, (clean,))

    def _clean(self, clean=True) -> None:
        """
        VTR cleanup with zipping of large files.
        """
        super()._clean()
        if not clean:
            return
        
        output_temp_dir = os.path.join(self.exp_dir, 'temp')

        # zip parmys.out and delete the original file
        # using subprocess to zip the file
        possible_list = ['parmys.out', 'design.net.post_routing', 'design.net', 'design.route']
        remove_list = []

        for possible in possible_list:
            if os.path.exists(os.path.join(output_temp_dir, possible)):
                remove_list.append(possible)

        cmd = ['zip', '-r', 'largefile.zip'] + remove_list
        zip_result = start_dependent_process(cmd, cwd=output_temp_dir, stdout=DEVNULL, stderr=DEVNULL)

        if zip_result.returncode == 0:
            for remove_file in remove_list:
                remove_path = os.path.join(output_temp_dir, remove_file)
                if os.path.exists(remove_path):
                    os.remove(remove_path)
        else:
            raise RuntimeError('Unable to zip parmys.out')
        
    def get_result(self) -> dict:
        """
        Get result of VTR run.
        """
        self._preresult_check()

        self.result = extract_info_vtr(os.path.join(self.exp_dir, 'temp'), ['clb', 'fle'])
        return self.result


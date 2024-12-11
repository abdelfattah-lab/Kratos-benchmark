from structure.exp import Experiment
from structure.test import VerilogImplTester
from structure.consts.shared_defaults import DEFAULTS_EXP_VTR
from structure.consts.shared_requirements import REQUIRED_KEYS_EXP_VERILOG
from util.extract import extract_info_vtr
from util.flow import start_dependent_process
from util.search import find_first_file_with_suffix

import os
import subprocess
from lxml import etree as ET
import json
import zipfile

class VtrExperiment(Experiment):
    """
    VTR implementation of an Experiment.
    """

    def get_name(self, adder_cin_global: bool, avoid_mult: bool, soft_multiplier_adders: bool, compressor_tree_type: str, force_denser_packing: bool, **kwargs):
        route_chan_width = kwargs.get('route_chan_width', -1)
        
        name = "vtr"
        if adder_cin_global:
            name += "_acg"
        if avoid_mult:
            name += "_am"
        name += "_c."
        if soft_multiplier_adders:
            name += "0"
        else:
            name += compressor_tree_type
        if route_chan_width >= 0:
            name += f"_rcw.{route_chan_width}"
        if force_denser_packing:
            name += "_dp"

        return name
        
    def run(self) -> None:
        """
        Run on VTR.

        dry_run: if True, only generate files, do not run VTR
        clean: if True, zip the temp files after VTR finishes to save space
        ending: ending stage of VTR, if None, run the whole flow, options: 'parmys', 'vpr'
        verify: verification stage of VTR; ignore if None. Options: 'synthesis' - post-synthesis, 'impl' - post-implementation.  
        verify_tester: an instance of a VerilogImplTester. Must be provided if verification is to be done.
        seed: random seed for VTR
        allow_skipping: if True, then the experiment is skipped if the folder already exists with valid results
        allow_skip_existing: if True, then the experiment is skipped if the folder already exists, regardless of valid results. Will only apply if allow_skipping is True.
        adder_cin_global: tells VTR to connect the first cin of an adder/subtractor chain to (True) global GND/Vdd, or (False) a dummy adder. Default: False
        soft_multiplier_adders: tells VTR to use cascading adder chains if True, else a compressor tree, to implement soft multiplication. Default: False
        compressor_tree_type: chooses a compressor tree type to implement:
            - 'wallace': chooses Proposed Wallace (Asif & Kong, https://doi.org/10.1155/2014/343960)
            - 'dadda': chooses Dadda (Dadda, L. (1990). Some schemes for parallel multipliers. IEEE Computer Society Press.)
            - 'cascade': ignore this flag, and set soft_multiplier_adders to True.
            - 'old': ignore all new implementations, and revert to vanilla VTR soft multiplication.
        avoid_mult: if True, then avoids using hard multipliers. Default: False
        route_chan_width: int, if provided >= 0, then routes with this fixed channel width, else ask VTR to find the minimum channel width. Default: None
        force_denser_packing: if True, then force VPR to pack as tightly as possible. Default: False
        """
        self._prerun_check()
        
        # get variables
        dry_run = self.exp_params.get('dry_run', False)
        allow_skipping = self.exp_params.get('allow_skipping', False)
        allow_skip_existing = self.exp_params.get('allow_skip_existing', False)

        # generic experiment setup
        self._setup_exp(DEFAULTS_EXP_VTR, REQUIRED_KEYS_EXP_VERILOG, clear_exp_dir=not allow_skipping)
        self.verilog_search_dir = self.exp_params['verilog_search_dir']
        self.vtr_output_dir = os.path.join(self.exp_dir, 'temp') # VTR output directory

        # Check for viable result (i.e., it has been run in the past)
        if (not dry_run) and allow_skipping:
            if (allow_skip_existing and os.path.exists(self.vtr_output_dir)) or self.get_result().get('status', False):
                return
        
        # Check for verification run
        self.verify = self.exp_params.get('verify', None)
        self.verify_tester: VerilogImplTester = self.exp_params.get('verify_tester', None)
        if self.verify not in [None, 'synthesis', 'impl']:
            raise ValueError(f"Unrecognised 'verify' argument: {self.verify}!")
        if self.verify is not None and self.verify_tester is None:
            raise ValueError('verify_tester must be provided if verify stage is specified!')

        # get variables
        clean = self.exp_params.get('clean', True)
        ending = self.exp_params['ending']
        seed = self.exp_params['seed']
        adder_cin_global = self.exp_params.get('adder_cin_global', False)
        soft_multiplier_adders = self.exp_params.get('soft_multiplier_adders', False)
        compressor_tree_type = self.exp_params['compressor_tree_type']
        avoid_mult = self.exp_params.get('avoid_mult', False)
        route_chan_width = self.exp_params.get('route_chan_width', -1) 
        force_denser_packing = self.exp_params.get('force_denser_packing', False)

        # generate wrapper file
        wrapper_file_name = 'design.v'
        self.wrapper_file_path = os.path.join(self.exp_dir, wrapper_file_name)
        with open(self.wrapper_file_path, 'w') as f:
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
        self.vtr_root = os.environ.get('VTR_ROOT')
        if self.vtr_root is None:
            raise RuntimeError('VTR_ROOT not found in environment variables; unable to execute VTR.')
        vtr_script_path = os.path.join(self.vtr_root, 'vtr_flow/scripts/run_vtr_flow.py')
        cmd = ['python', vtr_script_path, wrapper_file_name, arch_file_name,
               '-parser', 'system-verilog', 
               '--sweep_constant_primary_outputs', 'on', # remove LUTs that drive constant '0's
               '-top', self.design.wrapper_module_name, 
               '-search', self.verilog_search_dir, 
               '--seed', str(seed),
            ]
        if adder_cin_global:
            cmd += ['-adder_cin_global'] # only works with self-modified fork: https://github.com/abdelfattah-lab/vtr-updated

        if soft_multiplier_adders or compressor_tree_type == 'cascade':
            cmd += ['-soft_multiplier_adders'] # only works with self-modified fork: https://github.com/abdelfattah-lab/vtr-updated
        elif compressor_tree_type != 'cascade':
            cmd += ['-compressor_tree_type', compressor_tree_type] # only works with self-modified fork: https://github.com/abdelfattah-lab/vtr-updated

        if avoid_mult:
            cmd += ['-min_hard_mult_size', '9999'] # arbitrarily large multiplier size
        if ending is not None:
            cmd += ['-ending_stage', ending]

        # Add VPR commands
        if self.verify == 'impl':
            cmd += ['--gen_post_synthesis_netlist', 'on']

        if route_chan_width >= 0:
            # set route channel width
            cmd += ['--route_chan_width', str(int(route_chan_width))]

        if force_denser_packing:
            # enable unrelated clustering
            cmd += ['--allow_unrelated_clustering', 'on']
            # focus solely on area
            cmd += ['--alpha_clustering', '0']

        # Make out and error files
        self.stdout_file = open(os.path.join(self.exp_dir, self.exp_params['stdout_file']), 'w')
        self.stderr_file = open(os.path.join(self.exp_dir, self.exp_params['stderr_file']), 'w')

        # start VTR on subprocess
        self.process = start_dependent_process(cmd, stdout=self.stdout_file, stderr=self.stderr_file, cwd=self.exp_dir)

        # start post-processing thread
        self._start_post_thread(self._post_thread, ())
        # start GC thread
        self._start_gc_thread(self._clean, (clean,))

    def _post_thread(self) -> None:
        self._wait_main_process()

        # add a lightweight .json summary from .net file before zipping
        net_path = os.path.join(self.vtr_output_dir, 'design.net')
        if os.path.exists(net_path):
            self._generate_netstats_json(ET.parse(net_path).getroot(), self.vtr_output_dir)

        # verify netlists if required
        if self.verify is not None:
            post_module_suffix = '_post_synthesis.v' if self.verify == 'impl' else '_post_yosys.v'
            post_module_path = find_first_file_with_suffix(self.vtr_output_dir, post_module_suffix)
            if post_module_path is None:
                raise ValueError(f"Cannot find module to verify with suffix '{post_module_suffix}' in directory '{self.vtr_output_dir}'!")
            verification_output = self.verify_tester.verify(
                tb_params=self.design.gen_tb_params(**self.design_params),
                test_case_generator=lambda: self.design.gen_test_case(**self.design_params),
                working_dir=self.vtr_output_dir,
                pre_module_path=self.wrapper_file_path,
                post_module_path=post_module_path,
                include_dir=self.verilog_search_dir,
                add_verilog_file_paths=[
                    os.path.join(self.vtr_root, 'vtr_flow', 'primitives_no_specify.v'), # VTR primitives
                ],
            )
            
            with open(os.path.join(self.vtr_output_dir, 'verify.json'), 'w') as f:
                json.dump(verification_output, f)

    def _generate_netstats_json(self, net_root: ET.Element, output_dir: str) -> dict[str, any]:
        """
        Uses the ArchFactory to generate vital information from 'design.net' file, and saves a 'netstats.json' file in the same directory.
        @returns netstats dictionary.
        """
        netstats = self.arch.get_netstats(net_root)
        with open(os.path.join(output_dir, 'netstats.json'), 'w') as f:
            json.dump(netstats, f)

        return netstats

    def _clean(self, clean=True) -> None:
        """
        VTR cleanup with zipping of large files.
        """
        super()._clean()
        if not clean:
            return
        
        output_temp_dir = self.vtr_output_dir
        # zip parmys.out and delete the original file
        # using subprocess to zip the file
        possible_list = ['parmys.out', 'design.net.post_routing', 'design.net', 'design.route']
        remove_list = []

        for possible in possible_list:
            if os.path.exists(os.path.join(output_temp_dir, possible)):
                remove_list.append(possible)

        cmd = ['zip', '-r', 'largefile.zip'] + remove_list

        try:
            zip_result = subprocess.run(cmd, cwd=output_temp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if zip_result.returncode == 0:
                for remove_file in remove_list:
                    remove_path = os.path.join(output_temp_dir, remove_file)
                    if os.path.exists(remove_path):
                        os.remove(remove_path)
            else:
                print(f"Unable to perform zipping for: {output_temp_dir}")
        except:
            print(f"Unable to perform zipping for: {output_temp_dir}")

    def get_result(self, **kwargs) -> dict:
        """
        Get result of VTR run.
        """
        self._preresult_check()

        # load netstats if available
        netstats = {}
        netstats_path = os.path.join(self.vtr_output_dir, 'netstats.json')
        needs_updating = True
        if os.path.exists(netstats_path):
            with open(netstats_path, 'r') as netstats_file:
                netstats = json.load(netstats_file)
            needs_updating = self.arch.should_update_netstats(netstats)

        if needs_updating:
            net_file_path = os.path.join(self.vtr_output_dir, 'design.net')
            if os.path.exists(net_file_path):
                # file exists as-is
                netstats = self._generate_netstats_json(ET.parse(net_file_path).getroot(), self.vtr_output_dir)
            else:
                # file may exist in a .zip file
                largefile_zip_path = os.path.join(self.vtr_output_dir, 'largefile.zip')
                if os.path.exists(largefile_zip_path):
                    with zipfile.ZipFile(largefile_zip_path) as z:
                        if 'design.net' in z.namelist():
                            with z.open('design.net') as net_file:
                                netstats = self._generate_netstats_json(ET.parse(net_file).getroot(), self.vtr_output_dir)

        self.result = { **extract_info_vtr(self.vtr_output_dir, **kwargs), **netstats }

        # add verification result
        if self.verify is not None:
            verify_json_path = os.path.join(self.vtr_output_dir, 'verify.json')
            is_verified = False
            if os.path.exists(verify_json_path):
                with open(verify_json_path, 'r') as verify_json_file:
                    is_verified = json.load(verify_json_file)['verified']

            self.result['status'] = self.result['status'] & is_verified
            self.result['verified'] = is_verified

        return self.result


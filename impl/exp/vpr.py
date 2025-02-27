from structure.exp import Experiment
from structure.blif import BlifDesign
from structure.consts.shared_defaults import DEFAULTS_EXP_VPR
from structure.consts.shared_requirements import REQUIRED_KEYS_EXP
from util.extract import extract_info_vtr
from util.flow import start_dependent_process

import os
import subprocess
from lxml import etree as ET
import json
import zipfile

# map ending stage to VPR argument.
ENDING_ARGS = {
    'pack': '--pack',
    'place': '--pack --place',
    'route': '--pack --place --route',
}
class VprExperiment(Experiment):
    """
    VPR implementation of an Experiment. Uses a .blif file as input instead of high-level Verilog, and skips synthesis.
    """
    def __init__(self, arch, design, params):
        super().__init__(arch, design, params)

        # sanity check for BlifDesign
        if not isinstance(self.design, BlifDesign):
            raise ValueError("VprExperiment requires BlifDesign!")

    def get_name(self, **kwargs) -> str:
        ending = kwargs.get('ending', None)
        route_chan_width = kwargs.get('route_chan_width', -1)
        force_denser_packing = kwargs.get('force_denser_packing', False)

        name = "vpr"
        if ending is not None:
            name += f"_e.{ending}"
        if route_chan_width >= 0:
            name += f"_rcw.{route_chan_width}"
        if force_denser_packing:
            name += "_dp"
        
        return name
    
    def run(self) -> None:
        """
        Run on VPR.

        dry_run: if True, only generate files, do not run VPR
        ending: ending stage of VPR, if None, run the whole flow, options: 'pack', 'place', 'route'
        seed: random seed for VPR
        allow_skipping: if True, then the experiment is skipped if the folder already exists with valid results
        allow_skip_existing: if True, then the experiment is skipped if the folder already exists, regardless of valid results. Will only apply if allow_skipping is True.
        route_chan_width: int, if provided >= 0, then routes with this fixed channel width, else ask VTR to find the minimum channel width. Default: None
        force_denser_packing: if True, then force VPR to pack as tightly as possible (--allow_unrelated_clustering on). Default: False
        target_ext_pin_util: float, Sets the external pin utilization target (fraction between 0.0 and 1.0) during clustering. This determines how many pin the clustering engine will aim to use in a given cluster before closing it and opening a new cluster.
        """
        self._prerun_check()

        # get variables
        dry_run = self.exp_params.get('dry_run', False)
        allow_skipping = self.exp_params.get('allow_skipping', False)
        allow_skip_existing = self.exp_params.get('allow_skip_existing', False)

        # generic experiment setup
        self._setup_exp(DEFAULTS_EXP_VPR, REQUIRED_KEYS_EXP, clear_exp_dir=not allow_skipping)
        self.output_dir = self.exp_dir # VPR outputs directly to experiment directory

        # Check for viable result (i.e., it has been run in the past)
        if (not dry_run) and allow_skipping:
            if allow_skip_existing or self.get_result().get('status', False):
                return
        
        # get variables
        clean = self.exp_params.get('clean', True)
        ending = self.exp_params['ending']
        seed = self.exp_params['seed']
        route_chan_width = self.exp_params.get('route_chan_width', -1)
        force_denser_packing = self.exp_params.get('force_denser_packing', False)
        pin_util = self.exp_params.get('target_ext_pin_util', 'auto')
        
        # generate BLIF file
        blif_file_name = 'design.blif'
        with open(os.path.join(self.exp_dir, blif_file_name), 'w') as f:
            assert isinstance(self.design, BlifDesign)
            f.write(self.design.gen_blif(**self.design_params))
        
        # generate architecture file
        arch_file_name = 'arch.xml'
        with open(os.path.join(self.exp_dir, arch_file_name), 'w') as f:
            f.write(self.arch.get_arch(**self.arch_params))
        
        if dry_run:
            print(f"""(!) Created under {self.exp_dir}:
- README file: {self.readme_file_name}
- BLIF file: {blif_file_name}
- Architecture file: {arch_file_name}
>>> Dry run completed.""")
            return
        
        # Find VPR and define command
        vtr_root = os.environ.get('VTR_ROOT')
        if vtr_root is None:
            raise RuntimeError('VTR_ROOT not found in environment variables; unable to execute VTR.')
        vpr_path = os.path.join(vtr_root, 'build/vpr/vpr')
        if not os.path.exists(vpr_path):
            raise RuntimeError(f'VPR has not been built in specfied VTR_ROOT {vtr_root}.')
        cmd = [vpr_path, arch_file_name, blif_file_name,
                '--seed', str(seed),   
            ]
        
        if ending is not None:
            assert ending in ENDING_ARGS
            cmd += [ENDING_ARGS[ending]]
        if route_chan_width >= 0:
            # set route channel width
            cmd += ['--route_chan_width', str(int(route_chan_width))]
        if force_denser_packing:
            # enable unrelated clustering
            cmd += ['--allow_unrelated_clustering', 'on']
            # # disable time driven clustering
            # cmd += ['--timing_driven_clustering', 'off']  # added by @Xilai for testing packing
            
        # set target pin utilization
        cmd += ['--target_ext_pin_util', pin_util]

        # Make out and error files
        self.stdout_file = open(os.path.join(self.exp_dir, self.exp_params['stdout_file']), 'w')
        self.stderr_file = open(os.path.join(self.exp_dir, self.exp_params['stderr_file']), 'w')

        # start VPR on subprocess        
        self.process = start_dependent_process(cmd, stdout=self.stdout_file, stderr=self.stderr_file, cwd=self.exp_dir)

        # start post-processing thread
        self._start_post_thread(self._post_thread, ())
        # start GC thread
        self._start_gc_thread(self._clean, (clean,))

    def _post_thread(self) -> None:
        self._wait_main_process()

        # add a lightweight .json summary from .net file before zipping
        net_path = os.path.join(self.output_dir, 'design.net')
        if os.path.exists(net_path):
            self._generate_netstats_json(ET.parse(net_path).getroot(), self.output_dir)

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
        
        output_temp_dir = self.output_dir
        # zip parmys.out and delete the original file
        # using subprocess to zip the file
        possible_list = ['design.net.post_routing', 'design.net', 'design.route']
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
        netstats_path = os.path.join(self.output_dir, 'netstats.json')
        needs_updating = True
        if os.path.exists(netstats_path):
            with open(netstats_path, 'r') as netstats_file:
                netstats = json.load(netstats_file)
            needs_updating = self.arch.should_update_netstats(netstats)

        if needs_updating:
            net_file_path = os.path.join(self.output_dir, 'design.net')
            if os.path.exists(net_file_path):
                # file exists as-is
                netstats = self._generate_netstats_json(ET.parse(net_file_path).getroot(), self.output_dir)
            else:
                # file may exist in a .zip file
                largefile_zip_path = os.path.join(self.output_dir, 'largefile.zip')
                if os.path.exists(largefile_zip_path):
                    with zipfile.ZipFile(largefile_zip_path) as z:
                        if 'design.net' in z.namelist():
                            with z.open('design.net') as net_file:
                                netstats = self._generate_netstats_json(ET.parse(net_file).getroot(), self.output_dir)

        self.result = { **extract_info_vtr(self.output_dir, **kwargs), **netstats }
        return self.result
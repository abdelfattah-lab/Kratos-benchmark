from structure.util import Abstract, ParamsChecker
from structure.arch import ArchFactory
from structure.design import Design
import structure.consts.keys as keys
import structure.consts.translation as translations
from structure.consts.shared_defaults import DEFAULTS_EXP

import os, threading
from copy import deepcopy
from typing import Type, TypeVar, Callable
from tabulate import tabulate

class Experiment(ParamsChecker):
    """
    {abstract}
    Experiment meant to be run by a structure.run.Runner.
    """

    def __init__(self, arch: ArchFactory, design: Design, params: dict[str, dict[str, any]]) -> None:
        """
        Takes in an ArchFactory, Design, and a full set of Experiment parameters (meant to be split for different subclasses).
        """
        self.full_params = params

        self.exp_params = params.get(keys.KEY_EXP)
        if self.exp_params is None:
            raise ValueError(f"Experiment parameters requires base parameters provided under key '{keys.KEY_EXP}'!")

        self.arch_params = params.get(keys.KEY_ARCH)
        if self.arch_params is None:
            raise ValueError(f"Experiment parameters requires ArchFactory parameters provided under key '{keys.KEY_ARCH}'!")
        
        self.design_params = params.get(keys.KEY_DESIGN)
        if self.design_params is None:
            raise ValueError(f"Experiment parameters requires Design parameters provided under key '{keys.KEY_DESIGN}'!")
        
        self.root_dir = None
        self.arch = arch
        self.arch_params = self.arch.verify_params(self.arch_params)
        self.design = design
        self.design_params = self.design.verify_params(self.design_params)

        # create placeholders
        self.process = None  # subprocess
        self.stdout_file = None  # stdout file
        self.stderr_file = None  # stderr file
        self.gcthread = None  # thread for garbage collection
        self.result = None  # result of the experiment

    def _setup_exp(self, required_keys: list[str]) -> None:
        # Check all parameters.
        self.exp_params = self.verify_required_keys(DEFAULTS_EXP, required_keys, self.exp_params)
         # make root and experiment directory
        self.root_dir = self.exp_params['root_dir']
        self.verilog_search_dir = self.exp_params['verilog_search_dir']
        self.exp_dir = os.path.join(self.root_dir, f"{self.arch.get_name(**self.arch_params)}--{self.design.get_name(**self.design_params)}")
        os.makedirs(self.exp_dir, exist_ok=True)

        # generate README file
        self.readme_file_name = 'README.txt'
        with open(os.path.join(self.root_dir, self.readme_file_name), 'w') as f:
            f.write(self.gen_readme(self.exp_params.get('extra_info')))

    def _prerun_check(self) -> None:
        """
        Call at the top of every run() implementation.
        """
        if self.process is not None:
            raise RuntimeError('Experiment is already running or has finished.')
    
    def _clean(self) -> None:
        if self.process is not None:
            self.process.wait()
            self.stdout_file.close()
            self.stderr_file.close()
        else:
            raise RuntimeError('Experiment is not running.')
        
    def _start_gc_thread(self, fn: Callable[..., None], args: tuple) -> None:
        self.gcthread = threading.Thread(target=fn, args=args)
        self.gcthread.start()

    def run(self, dry_run=False, **kwargs) -> None:
        """
        {abstract}
        Implement the run based on tool (e.g., VTR, Quartus)
        """
        self.raise_unimplemented("run")

    def is_running(self):
        """
        Check if Experiment is running.
        """
        if self.process is not None:
            return self.process.poll() is None
        
        return False

    def wait(self):
        """
        Wait for finished execution of Experiment.
        """
        if self.process is not None:
            self.process.wait()
    
    def _get_readme_section(self, param_group: str, translations: dict[str, str], params: dict[str, any]) -> str:
        """
        Get a section of the README.
        """
        table = []
        for k, v in params.items():
            label = translations.get(k, k)
            table.append([label, v])

        return f"{param_group} parameters:\n{tabulate(table, tablefmt='rounded_grid')}\n"
    
    def gen_readme(self, extra_info: str = None) -> str:
        """
        Generates the README file for this experiment.
        i.e., a readout of all valid parameters provided.

        @returns a string representing the README file.
        """
        # Get all README sections.
        exp_section = self._get_readme_section('Experiment', translations.TRANSLATIONS_EXP, self.exp_params)
        arch_section = self._get_readme_section('Architecture', translations.TRANSLATIONS_ARCH, self.arch_params)
        design_section = self._get_readme_section('Design', translations.TRANSLATIONS_DESIGN, self.design_params)

        ret = f"{exp_section}\n{arch_section}\n{design_section}"

        # Insert additional information (if any).
        if not extra_info is None:
            ret += f"\nAdditional information:\n{extra_info}"
        
        return ret

    def _preresult_check(self) -> None:
        """
        Call this at the start of every get_result() implementation.
        """
        if (self.process is not None) and self.is_running():
            raise RuntimeError("Experiment is still running; unable to get result.")
        
    def get_result(self) -> dict:
        """
        {abstract}
        Get the result of the Experiment.
        """
        self.raise_unimplemented("get_result")

E = TypeVar('E', bound=Experiment)
class ExperimentFactory():
    """
    Takes in variable parameters, and generates experiments for each combination of parameters.
    """
    
    def __init__(self, arch: ArchFactory, design: Design, experiment_class: Type[E]) -> None:
        """
        Provide the ArchFactory, Design and Experiment class to be used for all generated Experiments.
        """
        self.arch = arch
        self.design = design
        self.experiment_class = experiment_class

    def gen_experiments(self, params: dict[str, any]) -> list[E]:
        """
        Searches through the parameters for variable parameters, specified as a list under the original key.
        """
        
        # Step 1: find all variable parameters
        variable_params = []
        def traverse(cur: dict[str, any], keys_path: list[str]) -> None:
            for k, v in cur.items():
                if isinstance(v, dict):
                    # is a dictionary, continue search (DFS)
                    traverse(v, [*keys_path, k])
                elif isinstance(v, list):
                    # save key path and list to variable_params
                    variable_params.append(([*keys_path, k], v))
    
        traverse(params, [])
        
        # Step 2: generate combinations
        variable_params_count = len(variable_params)
        experiments = []
        def generate_experiment(i: int, d: dict[str, any]) -> None:
            if i >= variable_params_count:
                # reached the end of variable parameters; construct, append, return
                experiments.append(self.experiment_class(self.arch, self.design, d))
                return
            
            keys_path, v_list = variable_params[i]
            for v in v_list:
                new_params = deepcopy(d)
                cur = new_params
                for key in keys_path[:-1]:
                    cur = cur[key]
                cur[keys_path[-1]] = v

                generate_experiment(i + 1, new_params)
        
        generate_experiment(0, params)
        return experiments

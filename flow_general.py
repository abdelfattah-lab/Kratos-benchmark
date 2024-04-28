import os
import re
import subprocess
import threading
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import track
from rich.style import Style

# systolic gemm
import gemms.flow_gemms_util as flow_gemms_util
# reduction tree gemm
import gemmt.flow_gemmt_rp_util as flow_gemmt_rp_util
import gemmt.flow_gemmt_fu_util as flow_gemmt_fu_util
# conv 1d
import conv_1d.flow_conv_1d_pw_util as flow_conv_1d_pw_util
import conv_1d.flow_conv_1d_fu_util as flow_conv_1d_fu_util
# conv 2d
import conv_2d.flow_conv_2d_pw_util as flow_conv_2d_pw_util
import conv_2d.flow_conv_2d_rp_util as flow_conv_2d_rp_util
import conv_2d.flow_conv_2d_fu_util as flow_conv_2d_fu_util
# tools
import util
import arch_generator

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
ERR_REPORT_FILE = 'experiments/errors.txt'


class QuartusRunner:
    def __init__(self, flow, settings):
        # store settings and flow
        self.settings = flow.check_settings(settings)
        self.flow = flow
        # create placceholders
        self.process = None  # subprocess quartus
        self.stdout_file = None  # stdout file for quartus
        self.stderr_file = None  # stderr file for quartus
        self.gcthread = None  # thread for garbage collection
        self.result = None  # result of the flow, alm, fmax ...

        # generate experiment name and directory
        self.exp_name = self.settings['exp_name']
        self.exp_dir = self.settings['exp_dir']

    def run(self, dry_run=False, seed=0):
        if self.process is not None:
            raise RuntimeError('QuartusRunner is already running or has finished.')

        current_dir = os.getcwd()

        # create folders
        os.makedirs(self.flow.EXPERIMENT_ROOT_DIR, exist_ok=True)
        os.makedirs(self.exp_dir, exist_ok=True)
        os.makedirs(self.flow.WRAPPER_DIR, exist_ok=True)

        # generate wrapper file
        wrapper_file_name = self.settings['wrapper_file_name']
        wrapper_str = self.flow.gen_wrapper(**self.settings)
        with open(wrapper_file_name, 'w') as wrapper_file:
            wrapper_file.write(wrapper_str)

        # generate tcl/sdc/readme file
        tcl_file_name = 'flow.tcl'
        with open(os.path.join(self.exp_dir, tcl_file_name), 'w') as tcl_file:
            tcl_file.write(self.flow.gen_tcl(**self.settings))
        sdc_file_name = 'flow.sdc'
        with open(os.path.join(self.exp_dir, sdc_file_name), 'w') as sdc_file:
            sdc_file.write(self.flow.gen_sdc(**self.settings))
        readme_file_name = 'README.txt'
        with open(os.path.join(self.exp_dir, readme_file_name), 'w') as readme_file:
            readme_file.write(self.flow.gen_readme(**self.settings))

        if dry_run:
            print('wrapper file created, tcl file created, sdc file created, readme file created, dry run finished.')
            os.chdir(current_dir)
            return
        # run quartus
        self.stdout_file = open(os.path.join(self.exp_dir, self.flow.DEFAULT_STDOUT_FILE), 'w')
        self.stderr_file = open(os.path.join(self.exp_dir, self.flow.DEFAULT_STDERR_FILE), 'w')
        cmd = ['quartus_sh', '-t', tcl_file_name]
        self.process = subprocess.Popen(cmd, stdout=self.stdout_file, stderr=self.stderr_file, cwd=os.path.join(ROOT_DIR, self.exp_dir))

        self.gcthread = threading.Thread(target=self.__clean_after_finish__)
        self.gcthread.start()

        # back to root dir
        os.chdir(current_dir)

    def __clean_after_finish__(self):
        if self.process is not None:
            self.process.wait()
            self.stdout_file.close()
            self.stderr_file.close()
        else:
            raise RuntimeError('QuartusRunner is not running.')

    def is_running(self):
        if self.process is not None:
            return self.process.poll() is None
        else:
            raise RuntimeError('QuartusRunner is not running.')

    def wait(self):
        if self.process is not None:
            self.process.wait()
        else:
            raise RuntimeError('QuartusRunner is not running.')

    def get_result(self):
        if (self.process is not None) and self.is_running():
            raise RuntimeError('QuartusRunner is still running.')
        else:
            self.result = util.extract_info_quartus(os.path.join(self.exp_dir, self.flow.DEFAULT_OUTPUT_DIR))
            return self.result


class VTRRunner:
    def __init__(self, flow, settings):
        # store settings and flow
        self.settings = flow.check_settings(settings)
        self.flow = flow
        # create placceholders
        self.process = None  # subprocess quartus
        self.stdout_file = None  # stdout file for vtr
        self.stderr_file = None  # stderr file for vtr
        self.gcthread = None  # thread for garbage collection
        self.result = None  # result of the flow, clb, fmax ...

        # generate experiment name and directory
        self.exp_name = self.settings['exp_name']
        self.exp_dir_vtr = self.settings['exp_dir_vtr']

    def run(self, dry_run=False, clean=True, ending=None, seed=1127):
        '''
        run the VTR flow
        dry_run: if True, only generate files, do not run VTR
        clean: if True, zip the temp files after VTR finishes to save space
        ending: ending stage of VTR, if None, run the whole flow, options: 'parmys', 'vpr'
        seed: random seed for VTR
        '''
        if self.process is not None:
            raise RuntimeError('VTRRunner is already running or has finished.')

        current_dir = os.getcwd()
        # create folders
        os.makedirs(self.flow.EXPERIMENT_ROOT_DIR_VTR, exist_ok=True)
        os.makedirs(self.exp_dir_vtr, exist_ok=True)
        # unlike quartus, wrapper is now created in the experiment folder

        # generate wrapper file, generate the file in the flow folder
        wrapper_file_name = 'design.v'
        wrapper_str = self.flow.gen_wrapper(**self.settings)
        with open(os.path.join(self.exp_dir_vtr, wrapper_file_name), 'w') as wrapper_file:
            wrapper_file.write(wrapper_str)

        # generate architecture file
        CLB_pins_per_group = self.settings.get('CLB_pins_per_group', 13)
        num_feedback_ble = self.settings.get('num_feedback_ble', 5)
        lut_size = self.settings.get('lut_size', 6)
        arch_str = arch_generator.generate_arch(CLB_pins_per_group, num_feedback_ble, lut_size)
        arch_file_name = 'arch.xml'
        with open(os.path.join(self.exp_dir_vtr, arch_file_name), 'w') as arch_file:
            arch_file.write(arch_str)

        # generate readme file
        readme_file_name = 'README.txt'
        with open(os.path.join(self.exp_dir_vtr, readme_file_name), 'w') as readme_file:
            readme_file.write(self.flow.gen_readme(**self.settings))

        if dry_run:
            print('wrapper file created, arch file created, readme file created, dry run finished.')
            os.chdir(current_dir)
            return

        # run vtr
        self.stdout_file = open(os.path.join(self.exp_dir_vtr, self.flow.DEFAULT_STDOUT_FILE), 'w')
        self.stderr_file = open(os.path.join(self.exp_dir_vtr, self.flow.DEFAULT_STDERR_FILE), 'w')
        # get environment variables $VTR_ROOT, if not found, raise error
        vtr_root = os.environ.get('VTR_ROOT')
        if vtr_root is None:
            raise RuntimeError('VTR_ROOT not found in environment variables. unable to execute VTR.')
        vtr_script_path = os.path.join(vtr_root, 'vtr_flow/scripts/run_vtr_flow.py')
        cmd = ['python', vtr_script_path, wrapper_file_name, arch_file_name,
               '-parser', 'system-verilog', '-top', self.flow.DEFAULT_WRAPPER_MODULE_NAME, '-search', ROOT_DIR, '--seed', str(seed)]
        if ending is not None:
            cmd += ['-ending_stage', ending]
        # print(cmd)
        # print(' '.join(cmd))
        self.process = subprocess.Popen(cmd, stdout=self.stdout_file, stderr=self.stderr_file, cwd=os.path.join(ROOT_DIR, self.exp_dir_vtr))

        self.gcthread = threading.Thread(target=self.__clean_after_finish__, args=(clean,))
        self.gcthread.start()

    def __clean_after_finish__(self, clean=True):
        if self.process is not None:
            self.process.wait()
            self.stdout_file.close()
            self.stderr_file.close()

            if not clean:
                return

            output_temp_dir = os.path.join(self.exp_dir_vtr, 'temp')

            # zip parmys.out and delete the original file
            # using subprocess to zip the file
            possible_list = ['parmys.out', 'design.net.post_routing', 'design.net', 'design.route']
            remove_list = []

            for possible in possible_list:
                if os.path.exists(os.path.join(output_temp_dir, possible)):
                    remove_list.append(possible)

            cmd = ['zip', '-r', 'largefile.zip'] + remove_list
            zip_result = subprocess.run(cmd, cwd=output_temp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if zip_result.returncode == 0:
                for remove_file in remove_list:
                    os.remove(os.path.join(output_temp_dir, remove_file))
            else:
                raise RuntimeError('Unable to zip parmys.out')

        else:
            raise RuntimeError('VTRRunner is not running.')

    def is_running(self):
        if self.process is not None:
            return self.process.poll() is None
        else:
            raise RuntimeError('VTRRunner is not running.')

    def wait(self):
        if self.process is not None:
            self.process.wait()
        else:
            raise RuntimeError('VTRRunner is not running.')

    def get_result(self):
        if (self.process is not None) and self.is_running():
            raise RuntimeError('VTRRunner is still running.')
        else:
            self.result = util.extract_info_vtr(os.path.join(self.exp_dir_vtr, 'temp'), ['clb', 'fle'])
            return self.result


def execute_runner(runner: QuartusRunner | VTRRunner, dry_run=False):
    runner.run(dry_run=dry_run, seed=2001)
    runner.wait()
    return runner.get_result()


def batch_run(flow, settings, num_parallel_tasks=1, flow_runner: QuartusRunner | VTRRunner = QuartusRunner):
    current_dir = os.getcwd()
    data_width_list = settings['data_width'] if isinstance(settings['data_width'], list) else [settings['data_width']]
    sparsity_list = settings['sparsity'] if isinstance(settings['sparsity'], list) else [settings['sparsity']]

    setting_remain = settings.copy()
    del setting_remain['data_width']
    del setting_remain['sparsity']

    len_a1 = len(sparsity_list)
    len_a2 = len(data_width_list)
    rfmaxs = np.zeros((len_a1, len_a2), dtype=np.float64)
    alms = np.zeros((len_a1, len_a2), dtype=np.int64)

    runners_tuples = []
    for i in range(len_a1):
        for j in range(len_a2):
            setting_new = setting_remain.copy()
            setting_new['data_width'] = data_width_list[j]
            setting_new['sparsity'] = sparsity_list[i]
            runner = flow_runner(flow, setting_new)
            runners_tuples.append((runner, i, j))

    futures_dict = {}  # (runner, future, Exception)
    futures = []
    with ThreadPoolExecutor(max_workers=num_parallel_tasks) as executor:
        for runners_tuple in runners_tuples:
            runner, i, j = runners_tuple
            future = executor.submit(execute_runner, runner)
            futures_dict[future] = runners_tuple
            futures.append(future)

    # Wait for all of them to finish
    completed = 0

    for future in as_completed(futures):
        try:
            result = future.result()
            runner, i, j = futures_dict[future]
            completed += 1
            rfmaxs[i, j] = result['fmax']
            alms[i, j] = result['fle']
            print(f'finished {completed}/{len(futures)}, status: {result["status"]}')
        except Exception as exc:
            print(f'generated an exception: {exc}')
            # create error report parent dir
            os.makedirs(os.path.dirname(ERR_REPORT_FILE), exist_ok=True)
            # write error report
            with open(ERR_REPORT_FILE, 'a') as f:
                err_str = '----------------------------------------\n'
                err_str += f'Exception in {runner.exp_dir}\n'
                err_str += f'runner config:\n{runner.settings}\n'
                err_str += f'Exception:\n{exc}\n'
                err_str += '----------------------------------------\n'
                f.write(err_str)
                print(err_str)

    os.makedirs(flow.DEFAULT_RESULT_DIR, exist_ok=True)

    fname = util.gen_dict_file_name(setting_remain)
    tname = util.gen_dict_title(setting_remain)
    # plot results
    util.plot_result(sparsity_list, data_width_list, rfmaxs, description1='sparsity', description2='data width', description3='restricted fmax (MHz)',
                     title=f'fmax vs sparsity and data width\n{tname}', save_name=os.path.join(flow.DEFAULT_RESULT_DIR, f'fmax_{fname}.png'), azimuth=125)
    util.plot_result(sparsity_list, data_width_list, alms, description1='sparsity', description2='data width', description3='ALMs',
                     title=f'ALMs vs sparsity and data width\n{tname}', save_name=os.path.join(flow.DEFAULT_RESULT_DIR, f'alms_{fname}.png'), azimuth=-55)
    # save results in txt
    with open(os.path.join(flow.DEFAULT_RESULT_DIR, f'fmax_{fname}.txt'), 'w') as f:
        f.write(util.gen_result_table(sparsity_list, data_width_list, rfmaxs, info='sparsity\\data width'))
    with open(os.path.join(flow.DEFAULT_RESULT_DIR, f'alms_{fname}.txt'), 'w') as f:
        f.write(util.gen_result_table(sparsity_list, data_width_list, alms, info='sparsity\\data width'))
    # back to root dir
    os.chdir(current_dir)


@DeprecationWarning
def batch_run_arch(flow, settings, num_parallel_tasks=8):
    current_dir = os.getcwd()
    num_feedback_ble_list = settings['num_feedback_ble'] if isinstance(settings['num_feedback_ble'], list) else [settings['num_feedback_ble']]
    lut_size_list = settings['lut_size'] if isinstance(settings['lut_size'], list) else [settings['lut_size']]

    setting_remain = settings.copy()
    del setting_remain['num_feedback_ble']
    del setting_remain['lut_size']

    len_a1 = len(num_feedback_ble_list)
    len_a2 = len(lut_size_list)

    rfmaxs = np.zeros((len_a1, len_a2), dtype=np.float64)
    alms = np.zeros((len_a1, len_a2), dtype=np.int64)

    runners_tuples = []
    for i in range(len_a1):
        for j in range(len_a2):
            setting_new = setting_remain.copy()
            setting_new['num_feedback_ble'] = num_feedback_ble_list[i]
            setting_new['lut_size_large'] = lut_size_list[j]
            setting_new['lut_size_small'] = lut_size_list[j] - 1
            runner = VTRRunner(flow, setting_new)
            runner.exp_dir_vtr = os.path.join(runner.exp_dir_vtr, f'fb_{num_feedback_ble_list[i]}_lut_{lut_size_list[j]}')
            runners_tuples.append((runner, i, j))

    futures_dict = {}  # (runner, future, Exception)
    futures = []
    with ThreadPoolExecutor(max_workers=num_parallel_tasks) as executor:
        for runners_tuple in runners_tuples:
            runner, i, j = runners_tuple
            future = executor.submit(execute_runner, runner)
            futures_dict[future] = runners_tuple
            futures.append(future)

    # Wait for all of them to finish
    completed = 0

    for future in as_completed(futures):
        try:
            result = future.result()
            runner, i, j = futures_dict[future]
            completed += 1
            if result['status'] == True:
                rfmaxs[i, j] = result['fmax']
                alms[i, j] = result['fle']
            print(f'finished {completed}/{len(futures)}, status: {result["status"]}')
        except Exception as exc:
            print(f'generated an exception: {exc}')
            # create error report parent dir
            os.makedirs(os.path.dirname(ERR_REPORT_FILE), exist_ok=True)
            # write error report
            with open(ERR_REPORT_FILE, 'a') as f:
                err_str = '----------------------------------------\n'
                err_str += f'Exception in {runner.exp_dir_vtr}\n'
                err_str += f'runner config:\n{runner.settings}\n'
                err_str += f'Exception:\n{exc}\n'
                err_str += '----------------------------------------\n'
                f.write(err_str)
                print(err_str)

    os.makedirs(flow.DEFAULT_RESULT_DIR, exist_ok=True)

    fname = util.gen_dict_file_name(setting_remain)
    tname = util.gen_dict_title(setting_remain)
    # plot results
    util.plot_result(num_feedback_ble_list, lut_size_list, rfmaxs, description1='num_feedback_ble', description2='lut_size', description3='restricted fmax (MHz)',
                     title=f'fmax vs num_feedback_ble and lut_size\n{tname}', save_name=os.path.join(flow.DEFAULT_RESULT_DIR, f'fmax_{fname}.png'), azimuth=125)
    util.plot_result(num_feedback_ble_list, lut_size_list, alms, description1='num_feedback_ble', description2='lut_size', description3='ALMs',
                     title=f'ALMs vs num_feedback_ble and lut_size\n{tname}', save_name=os.path.join(flow.DEFAULT_RESULT_DIR, f'alms_{fname}.png'), azimuth=-55)
    # save results in txt
    with open(os.path.join(flow.DEFAULT_RESULT_DIR, f'fmax_{fname}.txt'), 'w') as f:
        f.write(util.gen_result_table(num_feedback_ble_list, lut_size_list, rfmaxs, info='num_feedback_ble\\lut_size'))
    with open(os.path.join(flow.DEFAULT_RESULT_DIR, f'alms_{fname}.txt'), 'w') as f:
        f.write(util.gen_result_table(num_feedback_ble_list, lut_size_list, alms, info='num_feedback_ble\\lut_size'))
    # back to root dir
    os.chdir(current_dir)


def arch_name_patch(CLB_pins_per_group, num_feedback_ble, lut_size) -> str:
    return f'clb_{CLB_pins_per_group}_fb_{num_feedback_ble}_lut_{lut_size}'


@DeprecationWarning
def batch_run_arch_cartesian(flow, settings, num_parallel_tasks=5):
    # extract three list ‘CLB_pins_per_group’, ‘num_feedback_ble’, ‘lut_size’
    current_dir = os.getcwd()

    # extract arch configuration
    CLB_pins_per_group_list = settings['CLB_pins_per_group'] if isinstance(settings['CLB_pins_per_group'], list) else [settings['CLB_pins_per_group']]
    num_feedback_ble_list = settings['num_feedback_ble'] if isinstance(settings['num_feedback_ble'], list) else [settings['num_feedback_ble']]
    lut_size_list = settings['lut_size'] if isinstance(settings['lut_size'], list) else [settings['lut_size']]

    # get design configuration: data_width, sparsity
    data_width_list = settings['data_width'] if isinstance(settings['data_width'], list) else [settings['data_width']]
    sparsity_list = settings['sparsity'] if isinstance(settings['sparsity'], list) else [settings['sparsity']]

    setting_remain = settings.copy()
    del setting_remain['CLB_pins_per_group']
    del setting_remain['num_feedback_ble']
    del setting_remain['lut_size']
    del setting_remain['data_width']
    del setting_remain['sparsity']

    # get length to create result matrix
    l1 = len(CLB_pins_per_group_list)
    l2 = len(num_feedback_ble_list)
    l3 = len(lut_size_list)
    l4 = len(data_width_list)
    l5 = len(sparsity_list)

    fmax_mat = np.zeros((l1, l2, l3, l4, l5), dtype=np.float64)
    clb_mat = np.zeros((l1, l2, l3, l4, l5), dtype=np.int64)
    fle_mat = np.zeros((l1, l2, l3, l4, l5), dtype=np.int64)

    runner_info_dict = {}
    runners = []
    for i1 in range(l1):
        for i2 in range(l2):
            for i3 in range(l3):
                for i4 in range(l4):
                    for i5 in range(l5):
                        settings_new = setting_remain.copy()
                        settings_new['CLB_pins_per_group'] = CLB_pins_per_group_list[i1]
                        settings_new['num_feedback_ble'] = num_feedback_ble_list[i2]
                        settings_new['lut_size_large'] = lut_size_list[i3]
                        settings_new['lut_size_small'] = lut_size_list[i3] - 1
                        settings_new['data_width'] = data_width_list[i4]
                        settings_new['sparsity'] = sparsity_list[i5]
                        runner = VTRRunner(flow, settings_new)
                        runner.exp_dir_vtr = os.path.join(runner.exp_dir_vtr, arch_name_patch(CLB_pins_per_group_list[i1], num_feedback_ble_list[i2], lut_size_list[i3]))
                        runners.append(runner)
                        runner_info_dict[runner] = (i1, i2, i3, i4, i5)

    future_dict = {}  # (future -> runner)
    futures = []
    executor = ThreadPoolExecutor(max_workers=num_parallel_tasks)
    for runner in runners:
        future = executor.submit(execute_runner, runner)
        futures.append(future)
        future_dict[future] = runner

    for future in track(as_completed(futures), description='Running VTR', finished_style=Style(color='green'), total=len(futures)):
        try:
            result = future.result()
            runner = future_dict[future]
            i1, i2, i3, i4, i5 = runner_info_dict[runner]
            completed += 1
            if result['status'] == True:
                fmax_mat[i1, i2, i3, i4, i5] = result['fmax']
                clb_mat[i1, i2, i3, i4, i5] = result['clb']
                fle_mat[i1, i2, i3, i4, i5] = result['fle']
            print(f'finished {completed}/{len(futures)}, status: {result["status"]}')
        except Exception as exc:
            # create error report parent dir
            os.makedirs(os.path.dirname(ERR_REPORT_FILE), exist_ok=True)
            # write error report
            with open(ERR_REPORT_FILE, 'a') as f:
                err_str = '----------------------------------------\n'
                err_str += f'Exception in {runner.exp_dir_vtr}\n'
                err_str += f'runner config:\n{runner.settings}\n'
                err_str += f'Exception:\n{exc}\n'
                err_str += '----------------------------------------\n'
                f.write(err_str)
                print(err_str)

    executor.shutdown()

    # save results to csv.
    os.makedirs(flow.DEFAULT_RESULT_DIR, exist_ok=True)
    fname = util.gen_dict_file_name(setting_remain) + '_cartesian'

    # if file exists, then name by 2 3 ...
    if os.path.exists(os.path.join(flow.DEFAULT_RESULT_DIR, fname + '.csv')):
        i = 2
        while os.path.exists(os.path.join(flow.DEFAULT_RESULT_DIR, fname + f'_{i}.csv')):
            i += 1
        fname = fname + f'_{i}'

    with open(os.path.join(flow.DEFAULT_RESULT_DIR, fname + '.csv'), 'w') as w:
        other_setting_key_list = list(setting_remain.keys())
        header = ','.join(other_setting_key_list + ['CLB_pins_per_group', 'num_feedback_ble', 'lut_size', 'data_width', 'sparsity', 'fmax', 'clb', 'fle']) + '\n'
        w.write(header)
        for i1 in range(l1):
            for i2 in range(l2):
                for i3 in range(l3):
                    for i4 in range(l4):
                        for i5 in range(l5):
                            other_setting_value_list = [str(setting_remain[key]) for key in other_setting_key_list]
                            other_setting_value_str = ','.join(other_setting_value_list)
                            line = f'{other_setting_value_str},{CLB_pins_per_group_list[i1]},{num_feedback_ble_list[i2]},{lut_size_list[i3]},{data_width_list[i4]},{sparsity_list[i5]},{fmax_mat[i1, i2, i3, i4, i5]},{clb_mat[i1, i2, i3, i4, i5]},{fle_mat[i1, i2, i3, i4, i5]}\n'
                            w.write(line)

    # back to root dir
    os.chdir(current_dir)


@DeprecationWarning
def batch_run_arch_explore_lut(flow, settings: dict, num_parallel_tasks=5, description='lut_explore'):
    # what we want collect: [status, clb, fle, fmax, cpd, rcw]
    current_dir = os.getcwd()
    # the full collect list is not here, to extract all data, use extract_vtr.py
    collect_list = ['clb', 'fle', 'fmax', 'cpd', 'rcw']  # status is not here but we still need it

    CLB_PIN_DICT = {3: 6, 4: 8, 5: 10, 6: 13}
    # extract arch configuration
    lut_size_list = settings['lut_size'] if isinstance(settings['lut_size'], list) else [settings['lut_size']]
    # DO NOT use num clb pins as calculated by formula

    # get design configuration: data_width, sparsity
    data_width_list = settings['data_width'] if isinstance(settings['data_width'], list) else [settings['data_width']]
    sparsity_list = settings['sparsity'] if isinstance(settings['sparsity'], list) else [settings['sparsity']]

    setting_remain = settings.copy()
    del setting_remain['lut_size']
    del setting_remain['data_width']
    del setting_remain['sparsity']
    if 'CLB_pins_per_group' in setting_remain:
        del setting_remain['CLB_pins_per_group']

    runner_info_dict = {}
    runner_result_dict = {}
    runners = []
    for dw in data_width_list:
        for sp in sparsity_list:
            for ls in lut_size_list:
                settings_new = setting_remain.copy()
                # configure arch
                settings_new['lut_size'] = ls
                settings_new['CLB_pins_per_group'] = CLB_PIN_DICT[ls]
                # configure design
                settings_new['data_width'] = dw
                settings_new['sparsity'] = sp

                runner = VTRRunner(flow, settings_new)
                # patch exp_dir_vtr
                runner.exp_dir_vtr = os.path.join(runner.exp_dir_vtr, f'lut_{ls}')
                runners.append(runner)
                # sequence: data_width, sparsity, lut_size
                runner_info_dict[runner] = (dw, sp, ls)

    future_dict = {}  # (future -> runner)
    futures = []
    executor = ThreadPoolExecutor(max_workers=num_parallel_tasks)
    for runner in runners:
        future = executor.submit(execute_runner, runner)
        futures.append(future)
        future_dict[future] = runner

    for future in track(as_completed(futures), description=description, finished_style=Style(color='green'), total=len(futures)):
        try:
            result = future.result()
            runner = future_dict[future]
            runner_result_dict[runner] = result
            dw, sp, ls = runner_info_dict[runner]
            info_assem = {'data_width': dw, 'sparsity': sp, 'lut_size': ls}
            print(str(info_assem) + '@' + str(result))
        except Exception as exc:
            # create error report parent dir
            os.makedirs(os.path.dirname(ERR_REPORT_FILE), exist_ok=True)
            # write error report
            with open(ERR_REPORT_FILE, 'a') as f:
                err_str = '----------------------------------------\n'
                err_str += f'Exception in {runner.exp_dir_vtr}\n'
                err_str += f'runner config:\n{runner.settings}\n'
                err_str += f'Exception:\n{exc}\n'
                err_str += '----------------------------------------\n'
                f.write(err_str)
                print(err_str)

    executor.shutdown()

    # save results to csv.
    os.makedirs(flow.DEFAULT_RESULT_DIR, exist_ok=True)
    fname = util.gen_dict_file_name(setting_remain) + '-lut_explore'

    # if file exists, then name by 2 3 ...
    if os.path.exists(os.path.join(flow.DEFAULT_RESULT_DIR, fname + '.csv')):
        i = 2
        while os.path.exists(os.path.join(flow.DEFAULT_RESULT_DIR, fname + f'_{i}.csv')):
            i += 1
        fname = fname + f'_{i}'

    with open(os.path.join(flow.DEFAULT_RESULT_DIR, fname + '.csv'), 'w') as w:
        other_setting_key_list = list(setting_remain.keys())
        header = ','.join(other_setting_key_list + ['data_width', 'sparsity', 'lut_size'] + ['status'] + collect_list) + '\n'
        w.write(header)
        for runner in runners:
            dw, sp, ls = runner_info_dict[runner]
            other_setting_value_list = [str(setting_remain[key]) for key in other_setting_key_list]
            other_setting_value_str = ','.join(other_setting_value_list)
            status = 1 if runner_result_dict[runner]['status'] else 0
            line = f'{other_setting_value_str},{dw},{sp},{ls},{status}'
            for collect in collect_list:
                line += f',{runner_result_dict[runner][collect]}'
            line += '\n'
            w.write(line)

    # back to root dir
    os.chdir(current_dir)

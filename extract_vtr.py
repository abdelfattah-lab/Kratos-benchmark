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
from flow_general import VTRRunner


ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
ERR_REPORT_FILE = 'experiments/errors.txt'


def extract_runner(runner: VTRRunner):
    return runner.get_result()


def batch_run_extract_arch_explore_lut(flow, settings: dict, description='lut_explore'):
    # what we want collect: [status, clb, fle, fmax, cpd, rcw]
    current_dir = os.getcwd()

    collect_list = ['clb', 'fle', 'fmax', 'cpd', 'rcw', 'foutm', 'fouta', 'gridx', 'gridy', 'gridtotal',
                    'twl', 'wlpg', 'blocks', 'tle', 'lelr', 'lelo', 'lero']  # status is not here but we still need it

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
    executor = ThreadPoolExecutor(max_workers=1)
    for runner in runners:
        future = executor.submit(extract_runner, runner)
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


if __name__ == '__main__':

    design_space = {
        'data_width': [4, 8],
        'sparsity': [0.0, 0.5, 0.9],
    }

    arch_space = {'lut_size': [3, 4, 5, 6]}

    settings_mm_bram = {
        'row_num': 32,
        'col_num': 32,
        'length': 32,
    } | design_space | arch_space

    # batch_run_extract_arch_explore_lut(flow_mm_tree_util, settings_mm_bram)

    settings_conv_1d_bram = {
        'img_w': 32,
        'img_d': 64,
        'fil_w': 3,
        'res_d': 64,
        'stride_w': 1,
    } | design_space | arch_space

    # batch_run_extract_arch_explore_lut(flow_conv_bram_1d_util, settings_conv_1d_bram)

    settings_conv_bram_sr_fast_small = {
        'img_w': 25,
        'img_h': 25,
        'img_d': 32,
        'fil_w': 3,
        'fil_h': 3,
        'res_d': 64,
        'stride_w': 1,
        'stride_h': 1,
    } | design_space | arch_space

    batch_run_extract_arch_explore_lut(flow_conv_2d_pw_util, settings_conv_bram_sr_fast_small)

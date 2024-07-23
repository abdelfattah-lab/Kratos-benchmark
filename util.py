import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
import os
import requests
from tabulate import tabulate
import numpy as np
import pandas as pd
import random
import re
from io import StringIO

random.seed(114514)
DATA_WIDTH_DEFAULT = [1, 2, 4, 8]
SPARSITY_DEFAULT = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
COLOR_LIST_DEFAULT = [
    ['#fb6a4a', '#fcae91', '#d9181d'],
    ['#41b6c4', '#a1cac4', '#225ea8'],
    ['#74c476', '#bae4b3', '#238b45'],
    ['#fd8d3c', '#fdbe85', '#d94701'],
    ['#6baed6', '#bdd7e7', '#2171b5'],
    ['#78c679', '#c2e699', '#238443']
]


def plot_trend(mat_list: list[np.ndarray], labels: list[str], color_list=COLOR_LIST_DEFAULT, xlabel='', ylabel='', title='', save_name=''):
    assert len(mat_list) == len(labels)

    for idx in range(len(mat_list)):
        mat = mat_list[idx]
        label_name = labels[idx]
        data = mat / np.amax(mat, axis=0)
        # print(data)
        x_values = SPARSITY_DEFAULT

        # Calculate statistics
        means = np.mean(data, axis=1)
        lower_bound = np.min(data, axis=1)
        percentile_25 = np.percentile(data, 25, axis=1)
        # percentile_50 = np.percentile(data, 50, axis=1)
        percentile_75 = np.percentile(data, 75, axis=1)
        upper_bound = np.max(data, axis=1)

        # Plotting
        bar_width = 0.05

        transparency = 0.9

        for i, x in enumerate(x_values):
            plt.errorbar(x, means[i], yerr=[[means[i] - lower_bound[i]], [upper_bound[i] - means[i]]], color=color_list[idx][0], capsize=5, label='', alpha=transparency)
            plt.errorbar(x, means[i], yerr=[[means[i] - percentile_25[i]], [percentile_75[i] - means[i]]], elinewidth=10, color=color_list[idx][1], capsize=0, label='', alpha=transparency)

        # plot mean at top of the graph
        plt.plot(x_values, means, color=color_list[idx][2], label=label_name, linewidth=1, alpha=transparency)

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    if (save_name is not None) and (save_name != ''):
        plt.savefig(save_name, dpi=600)

    # plt.show()
    plt.clf()
    plt.close()


def plot_result(axis1, axis2, datapoints, description1='', description2='', description3='', title='', save_name='', elevation=25, azimuth=-145, alpha=1.0):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    _x = np.arange(len(axis1))
    _y = np.arange(len(axis2))
    _xx, _yy = np.meshgrid(_x, _y)
    x, y = _xx.ravel(), _yy.ravel()

    # Heights of bars are given by frequency
    datapoints = np.array(datapoints).T  # for unknown reason, datapoints is transposed, then it is correctly converted to 3d bar plot
    top = datapoints.ravel()
    bottom = np.zeros_like(top)

    # Change the width and depth here to make bars thinner
    width = depth = 0.5

    # Normalize to [0,1]
    norm = plt.Normalize(top.min(), top.max())

    # Create colormap
    colors = cm.Reds(norm(top))

    ax.bar3d(x, y, bottom, width, depth, top, color=colors, shade=True, edgecolor='black', alpha=alpha)
    ax.set_xticks(_x)
    ax.set_yticks(_y)
    ax.set_xticklabels(axis1)
    ax.set_yticklabels(axis2)
    ax.set_xlabel(description1)
    ax.set_ylabel(description2)
    ax.set_zlabel(description3)
    # Set the view angle
    ax.view_init(elev=elevation, azim=azimuth)
    ax.set_title(title)
    # save the figure in png with white background and high resolution
    if save_name != '':
        plt.savefig(save_name, bbox_inches='tight', pad_inches=1, transparent=False, dpi=600)

    plt.clf()
    plt.close(fig)


def gen_result_table(axis1, axis2, matrix, info=''):
    header = [info] + [str(width) for width in axis2]
    # Create a table with the matrix data
    table = []
    for i, row in enumerate(matrix):
        table.append([axis1[i]] + list(row))

    # Print the table using tabulate
    return tabulate(table, headers=header, tablefmt='rounded_grid')


def gen_result_df(axis1, axis2, matrix, info=''):
    # use pandas to generate csv
    header = [info] + [str(width) for width in axis2]
    # Create a table with the matrix data
    table = []
    for i, row in enumerate(matrix):
        table.append([axis1[i]] + list(row))
    df = pd.DataFrame(table, columns=header)
    return df


def check_and_fill_defaults(kwargs: dict, required_fields: list, default_fields: dict):
    '''
    check if settings are valid
    and fill in default values, return the settings
    '''
    filled_kwargs = kwargs.copy()
    for field in required_fields:
        if field not in kwargs:
            raise RuntimeError(f'{field} not specified')
    for field in default_fields:
        if field not in kwargs:
            filled_kwargs[field] = default_fields[field]
    return filled_kwargs


def extract_info_quartus(path='.'):

    # read information
    fit_successfull = False
    alm_usage = -1
    fmax = -1.0
    rfmax = -1.0

    # if summary file exists
    # read file 'v1.fit.summary'
    fit_path = os.path.join(path, 'v1.fit.summary')
    if os.path.exists(fit_path):
        smy = open(fit_path, 'r')
        fit_summary = smy.read()
        smy.close()
        status_match = re.search(r"Fitter Status : (\w+)", fit_summary)
        if status_match:
            fitter_status: str = status_match.group(1)
            if 'success' in fitter_status.lower():
                fit_successfull = True
                alm_match = re.search(r"Logic utilization \(in ALMs\) : ([\d,]+) \/ ([\d,]+)", fit_summary)
                if alm_match:
                    alm_usage = int(alm_match.group(1).replace(',', ''))
                else:
                    alm_usage = -1

    # if time analysis file exists
    # read file 'v1.sta.rpt'
    sta_rpt_path = os.path.join(path, 'v1.sta.rpt')
    if os.path.exists(sta_rpt_path):
        sta_rpt_file = open(sta_rpt_path, 'r')
        while True:
            line = sta_rpt_file.readline()
            if not line:
                break
            if '; Fmax Summary' in line:
                sta_rpt_file.readline()
                sta_rpt_file.readline()
                sta_rpt_file.readline()
                freqs = sta_rpt_file.readline().strip().split()
                fmax = float(freqs[1])  # fmax in MHz
                rfmax = float(freqs[4])  # restricted fmax in MHz
                break
        sta_rpt_file.close()

    return {'status': fit_successfull, 'alm': alm_usage, 'fmax': fmax, 'rfmax': rfmax}


def extract_info_vtr(path='.', extract_blocks_list=['clb', 'fle']) -> dict:
    # this will extract by default:
    # status for flow (status)
    # fmax (fmax)
    # cirtical path delay (cpd)
    # route channel width (rcw)
    # all elements in extract_blocks_list, e.g. clb, fle,

    # by 2023.10.12: extract:[status, fmax, cpd, rcw, clb, fle, foutm, fouta, gridn, gridtotal, twl, blocks]

    # if extract list is not a list, then we convert it to a list
    if not isinstance(extract_blocks_list, list):
        extract_blocks_list = [extract_blocks_list]

    result_dict = {}
    result_dict['status'] = False
    result_dict['fmax'] = -1.0
    result_dict['cpd'] = -1.0
    result_dict['rcw'] = 999999
    result_dict['foutm'] = 0        # max fanout
    result_dict['fouta'] = 0        # average fanout
    result_dict['gridx'] = 0        # number of grid on x
    result_dict['gridy'] = 0        # number of grid on y
    result_dict['gridtotal'] = 0    # total number of grid
    result_dict['twl'] = 0          # total wire length
    result_dict['wlpg'] = 0         # wire length per grid
    result_dict['blocks'] = 0       # total number of blocks, aka primitive cells
    result_dict['tle'] = 0          # Total number of Logic Elements used
    result_dict['lelr'] = 0         # LEs used for logic and registers
    result_dict['lelo'] = 0         # LEs used for logic only
    result_dict['lero'] = 0         # LEs used for registers only

    # fill default values with -1
    for c in extract_blocks_list:
        result_dict[c] = -1.0

    # vpr output is not same as quartus, the status is at the end of the file, so we need to extract the block usage first and later extratc flow status
    vpr_out_path = os.path.join(path, 'vpr.out')
    # if not exit, then return
    if not os.path.exists(vpr_out_path):
        return result_dict

    f = open(vpr_out_path, 'r')
    for line in f:
        line = line.strip()
        # extract block usage
        if line.startswith('Pb types usage'):
            # this indicates the start of synthesis resourse usage
            # we read maximum 50 lines or if a line is empty, then we stop
            for i in range(50):
                line = f.readline().strip()
                if line == '':
                    # reach the end of the block usage table
                    break
                parts = line.split()
                for c in extract_blocks_list:
                    if parts[0] == c:
                        # try if parts[1] or parts[2] is a number
                        try:
                            result_dict[c] = int(parts[1])
                        except:
                            result_dict[c] = int(parts[2])
                        break

        # extract flow status
        if line.startswith('VPR succeeded'):
            result_dict['status'] = True

        # extract critical path delay and fmax
        if line.startswith('Final critical path delay'):
            l_colon = line.find(':')
            info_left = line[l_colon+1:].strip()
            parts = info_left.split()
            result_dict['cpd'] = float(parts[0])
            result_dict['fmax'] = float(parts[3])

        # extract route channel width
        if line.startswith('Circuit successfully routed with a channel width factor of'):
            if line.endswith('.'):
                line = line[:-1]
            parts = line.split()
            result_dict['rcw'] = int(parts[-1])

        # extract fanout
        if line.startswith('Max Fanout'):
            parts = line.split()
            result_dict['foutm'] = int(float(parts[-1]))
        if line.startswith('Avg Fanout'):
            parts = line.split()
            result_dict['fouta'] = float(parts[-1])

        # extract grid number
        if line.startswith('FPGA sized to') and 'grid' in line:
            line = line.replace(':', '')
            parts = line.split()
            result_dict['gridx'] = int(parts[3])
            result_dict['gridy'] = int(parts[5])
            result_dict['gridtotal'] = int(parts[6])

        # total wire length
        if line.startswith('Total wirelength'):
            line = line.replace(':', '').replace(',', '')
            parts = line.split()
            result_dict['twl'] = int(parts[2])
        # blocks:
        if line.startswith('Circuit Statistics:'):
            line = f.readline().strip()
            line = line.replace(':', '')
            parts = line.split()
            result_dict['blocks'] = int(parts[1])

        # Logic Element (fle) detailed count:
        # Total number of Logic Elements used
        if line.startswith('Total number of Logic Elements used'):
            line = line.replace(':', '').replace(',', '')
            parts = line.split()
            result_dict['tle'] = int(parts[-1])

        # LEs used for logic and registers
        if line.startswith('LEs used for logic and registers'):
            line = line.replace(':', '').replace(',', '')
            parts = line.split()
            result_dict['lelr'] = int(parts[-1])

        # LEs used for logic only
        if line.startswith('LEs used for logic only'):
            line = line.replace(':', '').replace(',', '')
            parts = line.split()
            result_dict['lelo'] = int(parts[-1])

        # LEs used for registers only
        if line.startswith('LEs used for registers only'):
            line = line.replace(':', '').replace(',', '')
            parts = line.split()
            result_dict['lero'] = int(parts[-1])

    f.close()

    # calculate wire length per grid
    if (result_dict['gridtotal'] != 0) and (result_dict['twl'] != 0):
        result_dict['wlpg'] = result_dict['twl'] / result_dict['gridtotal']

    return result_dict


def gen_dict_file_name(dic):
    name = ''
    for key in dic:
        name += f'{key}.{dic[key]}-'
    return name[:-1]


def gen_dict_title(dic, length_per_line=30):
    title = ''
    # produce a string in this format: key=value, key=value, ... but each line has at most length_per_line characters
    for key in dic:
        title += f'{key}={dic[key]}, '
        # if len(title) > length_per_line:
        #     title += '\n'
    return title[:-2]


def reset_seed(n=114514):
    random.seed(n)
    np.random.seed(n)


def generate_specific_array(length, data_width, value):
    params = np.zeros((length), dtype=int)
    for i in range(length):
        params[i] = value[i]

    # create array string in verilog format
    arr_str = '\'{'
    for i in range(length):
        arr_str += f'{data_width}\'d{int(params[i])}'
        if i != length-1:
            arr_str += ', '
    arr_str += '}'

    return arr_str


def generate_random_array(length, data_width, sparsity):
    params = np.zeros((length), dtype=int)
    threshold = int(length * sparsity)
    count = 0
    for i in range(length):
        count += 1
        if count > threshold:
            params[i] = random.randint(1, pow(2, data_width)-1)
    np.random.shuffle(params)

    return generate_specific_array(length, data_width, params)


def generate_specific_matrix(row_num, column_num, data_width, value):
    params = np.zeros((row_num, column_num), dtype=int)
    for i in range(row_num):
        for j in range(column_num):
            params[i][j] = value[i][j]

    # create array string in verilog format
    arr_str = '\'{'
    for i in range(row_num):
        arr_str += '\'{'
        for j in range(column_num):
            arr_str += f'{data_width}\'d{int(params[i][j])}'
            if j != column_num-1:
                arr_str += ', '
        arr_str += '}'
        if i != row_num-1:
            arr_str += ', '
    arr_str += '}'

    return arr_str


def generate_random_matrix(row_num, column_num, data_width, sparsity):
    total_num = row_num * column_num
    params = np.zeros((total_num), dtype=int)
    threshold = int(total_num * sparsity)
    count = 0
    for i in range(total_num):
        count += 1
        if count > threshold:
            params[i] = random.randint(1, pow(2, data_width)-1)
    np.random.shuffle(params)
    params = params.reshape((row_num, column_num))

    return generate_specific_matrix(row_num, column_num, data_width, params)

    # # create array string in verilog format
    # arr_str = '\'{'
    # for i in range(row_num):
    #     arr_str += '\'{'
    #     for j in range(column_num):
    #         arr_str += f'{data_width}\'d{int(params[i][j])}'
    #         if j != column_num-1:
    #             arr_str += ', '
    #     arr_str += '}'
    #     if i != row_num-1:
    #         arr_str += ', '
    # arr_str += '}'

    # return arr_str


def generate_random_matrix_3d(depth, row_num, column_num, data_width, sparsity):
    total_num = row_num * column_num * depth
    params = np.zeros((total_num), dtype=int)
    threshold = int(total_num * sparsity)
    count = 0
    for i in range(total_num):
        count += 1
        if count > threshold:
            params[i] = random.randint(1, pow(2, data_width)-1)
    np.random.shuffle(params)
    params = params.reshape((depth, row_num, column_num))

    # create array string in verilog format
    arr_str = '\'{'
    for i in range(depth):
        arr_str += '\'{'
        for j in range(row_num):
            arr_str += '\'{'
            for k in range(column_num):
                arr_str += f'{data_width}\'d{int(params[i][j][k])}'
                if k != column_num-1:
                    arr_str += ', '
            arr_str += '}'
            if j != row_num-1:
                arr_str += ', '
        arr_str += '}'
        if i != depth-1:
            arr_str += ', '
    arr_str += '}'

    return arr_str


def generate_random_matrix_4d(filter_num, depth, row_num, column_num, data_width, sparsity):
    total_num = row_num * column_num * depth * filter_num
    params = np.zeros((total_num), dtype=int)
    threshold = int(total_num * sparsity)
    count = 0
    for i in range(total_num):
        count += 1
        if count > threshold:
            params[i] = random.randint(1, pow(2, data_width)-1)
    np.random.shuffle(params)
    params = params.reshape((filter_num, depth, row_num, column_num))

    # create array string in verilog format
    arr_str = '\'{'
    for i in range(filter_num):
        arr_str += '\'{'
        for j in range(depth):
            arr_str += '\'{'
            for k in range(row_num):
                arr_str += '\'{'
                for l in range(column_num):
                    arr_str += f'{data_width}\'d{int(params[i][j][k][l])}'
                    if l != column_num-1:
                        arr_str += ', '
                arr_str += '}'
                if k != row_num-1:
                    arr_str += ', '
            arr_str += '}'
            if j != depth-1:
                arr_str += ',\n    '
        arr_str += '}'
        if i != filter_num-1:
            arr_str += ',\n  '
    arr_str += '}'

    return arr_str


def generate_flattened_bit(data_width, total_num, sparsity, number=None):
    '''
    this method will return a bit string of length total_number * data_width, for example
    if data_width = 8, and total_number is 4, then it will return 32'hdeadbeef

    currently only support data width of 4,8
    '''

    params = np.zeros((total_num), dtype=int)
    threshold = int(total_num * sparsity)
    count = 0
    for i in range(total_num):
        count += 1
        if count > threshold:
            params[i] = np.random.randint(1, pow(2, data_width)-1)

    np.random.shuffle(params)
    # print count of non zero elements
    total_bit_length = total_num * data_width
    result = str(total_bit_length) + "'h"
    for n in params:
        if data_width == 4:
            result += format(n, 'x')
        elif data_width == 8:
            result += format(n, 'x').zfill(2)
        else:
            raise Exception("unsupported data width")

    return result


def gen_long_constant_bits(length, sparsity, length_placeholder, bits_name='constfil'):
    # divide the long contstant string into multiple small one so parser will work, maximum bits per const is 8192. (the actual limit of parmys is 16384)
    assert length % 4 == 0, "length must be multiple of 4"
    num_complete = length // 8192
    num_remain = length % 8192
    str_temp = 'localparam bit [{total_length}:0] const_fil_part_{i} = {arr_str};'
    constructed_parts_consts = ''
    data_width = 4
    for i in range(num_complete):
        arr_str = generate_flattened_bit(data_width, 8192 // data_width, sparsity)
        constructed_parts_consts += str_temp.format(total_length=8191, i=i, arr_str=arr_str) + '\n'
    if num_remain != 0:
        arr_str = generate_flattened_bit(data_width, num_remain // data_width, sparsity)
        constructed_parts_consts += str_temp.format(total_length=num_remain-1, i=num_complete, arr_str=arr_str) + '\n'

    idxs = '{' + ','.join([f'const_fil_part_{i}' for i in range(num_complete + 1)]) + '}'
    constant_bits = constructed_parts_consts + f'localparam bit [{length_placeholder}-1:0] {bits_name} = {idxs};'
    return constant_bits


def bark(content='default flow notification', title='FPGA FLOW'):
    urls = os.getenv('BARKURL')
    if urls:
        urls = urls.strip().split()
        for url in urls:
            # print(url)
            if url.endswith('/'):
                url = url[:-1]

            try:
                resp = requests.get(url + f'/{title}/{content}')
                if resp.status_code == 200:
                    continue
                else:
                    print('Bark internet failed')

            except Exception as e:
                print(e)
                print('Bark unknown failed')

    else:
        print('Bark URL not set')
        return False

def pretty(d: dict, indent=0, to_string=False) -> str:
    """
    Pretty-print a dictionary.

    Optional arguments:
    * indent:int, base indent, default 0
    * to_string:bool, True: returns a pretty-printed string; False: prints directly to console, default False
    """

    file = StringIO() if to_string else None

    for key, value in d.items():
        print('\t' * indent + str(key), end='', file=file)
        if isinstance(value, dict):
            print(file=file)
            pretty(value, indent+1)
        else:
            print(f": {value}", file=file)

    if to_string:
        ret = file.getvalue()
        file.close()
        return ret

    return None
"""
Convenience functions for data extraction from external tool reports (e.g., Quartus, VTR).
"""

import re, os
import math

def extract_info_quartus(path='.'):
    # read information
    fit_successfull = False
    alm_usage = -1
    virtual_pins = -1
    fmax = -1.0
    rfmax = -1.0
    lut_logic = {}
    lut_rt = -1
    lut_total = -1

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

    if fit_successfull:
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
                    status = sta_rpt_file.readline()
                    if "No paths to report" in status:
                        break

                    sta_rpt_file.readline()
                    freqs = sta_rpt_file.readline().strip().split()
                    fmax = float(freqs[1])  # fmax in MHz
                    rfmax = float(freqs[4])  # restricted fmax in MHz
                    break
            sta_rpt_file.close()

        # if fit report file exists
        #read file 'v1.fit.rpt'
        fit_rpt_path = os.path.join(path, 'v1.fit.rpt')
        if os.path.exists(fit_rpt_path):
            place_rpt_file = open(fit_rpt_path, 'rb') # read in bytes because there might be special non-utf8 characters (quite stupid)
            
            # information changes based on edition
            quartus_edition = 'pro'

            # dictionaries for identification
            alut_usage_search = {
                'pro': 'Combinational ALUT usage for logic',
                'standard': 'Combinational ALUT usage by number of inputs',
            }
            alm_search = {
                'pro': 'Logic utilization (ALMs needed / total ALMs on device)',
                'standard': 'ALMs:  partially or completely used',
            }
            virtual_pins_search = {
                'pro': 'Virtual pins',
                'standard': 'Virtual pins',
            }

            line = place_rpt_file.readline()
            while line:
                try:
                    line = str(line)
                except:
                    line = place_rpt_file.readline()
                    continue
            
                # Grab Quartus edition
                if "Quartus Prime Version" in line:
                    edition_match = re.search(r"\s([a-zA-Z]+)\sEdition", line)
                    if edition_match:
                        quartus_edition = edition_match.group(1).lower()

                # Grab LUT usage
                if alut_usage_search[quartus_edition] in line:
                        # read all LUT sizes
                        while True:
                            line = str(place_rpt_file.readline())
                            lut_size_match = re.search(r"--\D*([\d,]+) input function\D*;\s*([\d,]+)", line) 
                            if not lut_size_match:
                                # read past all possible input function lines
                                break

                            # add size and count
                            lut_size = int(lut_size_match.group(1).replace(',', ''))
                            lut_count = int(lut_size_match.group(2).replace(',', ''))
                            lut_logic[lut_size] = lut_count
                        
                        if quartus_edition == 'pro':
                            # read route-throughs
                            lut_rt_match = re.search(r"Combinational ALUT usage for route-throughs\s*;\s*([d,]+)", line)
                            if lut_rt_match:
                                lut_rt = int(lut_rt_match.group(1).replace(',', ''))
                        else:
                            lut_rt = 0
                
                # Grab ALM count
                if alm_search[quartus_edition] in line:
                    alm_match = re.search(r"([\d,]+)\s*\/\s*[\d,]+", line)
                    if alm_match:
                        alm_usage = int(alm_match.group(1).replace(',', ''))

                # Grab virtual pins
                if virtual_pins_search[quartus_edition] in line:
                    virtual_pins_match = re.search(r";\s*([\d,]+)\s*;", line)
                    if virtual_pins_match:
                        virtual_pins = int(virtual_pins_match.group(1).replace(',', ''))
                line = place_rpt_file.readline()

            # Calculate LUT total
            if lut_rt >= 0 and len(lut_logic) > 0:
                lut_total = lut_rt + sum(lut_logic.values())
            
            # Calculate ALMs without virtual I/O
            if virtual_pins > 0 and alm_usage >= 0:
                alm_usage -= math.ceil(virtual_pins / 2)

    return {
        'status': fit_successfull, 
        'alm': alm_usage, 
        'virtual_pins': virtual_pins,
        'fmax': fmax, 
        'rfmax': rfmax, 
        **{f"lut{size}": count for size, count in lut_logic.items()}, 
        'lut_rt': lut_rt,
        'lut_total': lut_total
    }


def extract_info_vtr(path='.', extract_blocks_list=['clb', 'fle']) -> dict:
    """
    Available extracted information from vpr.out:

    Raw data:
    * status: whether flow succeeded (True/False)
    * fmax: max frequency, MHz
    * cpd: critical path delay, ns
    * rcw: route channel width
    * area_le: area of logic tiles, in MWTAs
    * area_le_used: used area of logic only, in MWTAs
    * area_r: used area of routing, in MWTAs
    * foutm: max fanout
    * fouta: average fanout
    * gridx: number of grids on x
    * gridy: number of grids on y
    * gridtotal: total number of grids
    * twl: total wire length
    * blocks: total number of blocks, aka primitive cells
    * tle: total number of logic elements (LEs) used
    * lelr: LEs used for logic and registers
    * lelo: LEs used for logic only
    * lero: LEs used for registers only
    * nets_total: total logical nets
    * nets_absorbed:  absorbed logical nets during clustering
    * <keys specified in extract_blocks_list>: these will extract counts of specific PB types, e.g., CLBs, FLEs.
    You can specify a hierarchy with '<level 1>.<level 2>':
    - <level 2> does not need to be a direct child of <level 1>.
    - ALL counts that match the hierarchy will be added to this key's count.
    e.g.:
    one 10
        two_a 20
            three 10
                a 10
                b 50
        two_b 10
            a 20
    then 'one' = 10, 'three' = 10, 'one.a' = 30, 'two_a.b' = 50

    Derived:
    * wlpg: wire length per grid
    * area_total: total area of logic tiles and routing, in MWTAs
    * area_total_used: total area used, in MWTAs
    * lelr_frac: lelr / tle
    * lelo_frac: lelo / tle
    * lero_frac: lero / tle
    * nets_absorbed_frac: nets_absorbed / nets_total
    """
    # if extract list is not a list, then we convert it to a list
    if not isinstance(extract_blocks_list, list):
        extract_blocks_list = [extract_blocks_list]
    result_dict = {}
    result_dict['status'] = False
    result_dict['fmax'] = -1.0                  # max frequency, MHz
    result_dict['cpd'] = -1.0                   # critical path delay, ns
    result_dict['rcw'] = 999999                 # route channel width
    result_dict['area_le'] = -1.0               # area of logic tiles, in MWTAs
    result_dict['area_le_used'] = -1.0          # used area of logic only, in MWTAs
    result_dict['area_r'] = -1.0                # used area of routing, in MWTAs
    result_dict['area_total'] = -1              # total area of logic tiles and routing, in MWTAs
    result_dict['area_total_used'] = -1         # total area used, in MWTAs
    result_dict['foutm'] = 0                    # max fanout
    result_dict['fouta'] = 0                    # average fanout
    result_dict['gridx'] = 0                    # number of grid on x
    result_dict['gridy'] = 0                    # number of grid on y
    result_dict['gridtotal'] = 0                # total number of grid
    result_dict['twl'] = 0                      # total wire length
    result_dict['wlpg'] = 0                     # wire length per grid
    result_dict['blocks'] = 0                   # total number of blocks, aka primitive cells
    result_dict['tle'] = 0                      # Total number of Logic Elements used
    result_dict['lelr'] = 0                     # LEs used for logic and registers
    result_dict['lelo'] = 0                     # LEs used for logic only
    result_dict['lero'] = 0                     # LEs used for registers only
    result_dict['lelr_frac'] = 0                # % of LEs used for logic and registers
    result_dict['lelo_frac'] = 0                # % of LEs used for logic only
    result_dict['lero_frac'] = 0                # % of LEs used for registers only
    result_dict['nets_total'] = 0               # Total logical nets
    result_dict['nets_absorbed'] = 0            # Absorbed logical nets during clustering
    result_dict['nets_absorbed_frac'] = -1.0    # nets_absorbed / nets_total
    result_dict['mrcu'] = -1.0                  # max routing channel utilization
    
    result_dict['rcu_0.1'] = -1.0               # routing channel utilization at 0.0 - 0.1
    result_dict['rcu_0.2'] = -1.0               # routing channel utilization at 0.1 - 0.2
    result_dict['rcu_0.3'] = -1.0               # routing channel utilization at 0.2 - 0.3
    result_dict['rcu_0.4'] = -1.0               # routing channel utilization at 0.3 - 0.4
    result_dict['rcu_0.5'] = -1.0               # routing channel utilization at 0.4 - 0.5
    result_dict['rcu_0.6'] = -1.0               # routing channel utilization at 0.5 - 0.6
    result_dict['rcu_0.7'] = -1.0               # routing channel utilization at 0.6 - 0.7
    result_dict['rcu_0.8'] = -1.0               # routing channel utilization at 0.7 - 0.8
    result_dict['rcu_0.9'] = -1.0               # routing channel utilization at 0.8 - 0.9
    result_dict['rcu_1.0'] = -1.0               # routing channel utilization at 0.9 - 1.0
    

    # vpr output is not same as quartus, the status is at the end of the file, so we need to extract the block usage first and later extratc flow status
    vpr_out_path = os.path.join(path, 'vpr_stdout.log')
    # if not exit, then return
    if not os.path.exists(vpr_out_path):
        return result_dict

    f = open(vpr_out_path, 'r')
    for line in f:
        line = line.strip()
        # extract block usage
        if line.startswith('Pb types usage'):
            # this indicates the start of synthesis resource usage
            # we read maximum 50 lines or if a line is empty, then we stop

            # store the usage metrics into a tree structure
            def get_node(val):
                return {
                    'value': int(val),
                    'children': {}
                }
            
            tree = {}
            last_space = 0
            prev_key = None
            keys = []
            for i in range(50):
                line = f.readline()
                if line.strip() == '':
                    # reach the end of the block usage table
                    break
            
                key, val = [x.strip() for x in line.split(':')[:2]]
                left_spaces = len(line) - len(line.lstrip(' '))
                if left_spaces != last_space:
                    if prev_key is not None:
                        keys.append(prev_key) if left_spaces > last_space else keys.pop()
                        
                    last_space = left_spaces
                    prev_key = key

                node_dict = tree
                for k in keys:
                    node_dict = node_dict[k]['children']
                
                node_dict[key] = get_node(val)

            def traverse_tree(head, sub_keys):
                if len(head) == 0:
                    return 0
                
                ret = 0
                for k, v in head.items():
                    if k == sub_keys[0]:
                        if len(sub_keys) == 1:
                            ret += v['value']
                        else:
                            ret += traverse_tree(v['children'], sub_keys[1:])
                    else:
                        ret += traverse_tree(v['children'], sub_keys[:])

                return ret

            for key in extract_blocks_list:
                result_dict[key] = traverse_tree(tree, key.split('.'))

        # extract flow status
        if line.startswith('VPR succeeded'):
            result_dict['status'] = True

        # extract critical path delay and fmax
        if line.startswith('Final critical path delay'):
            l_colon = line.find(':')
            info_left = line[l_colon+1:].strip()
            parts = info_left.split()
            result_dict['cpd'] = float(parts[0])
            #Fmax will not be shown if CPD is NaN for any reason
            if len(parts) >= 4:
                result_dict['fmax'] = float(parts[3])

            if result_dict['cpd'] > 0 and result_dict['fmax'] < 0:
                # fail-safe: get Fmax from CPD if not shown in report
                result_dict['fmax'] = 1000 / (result_dict['cpd']) 

        # extract route channel width
        if line.startswith('Circuit successfully routed with a channel width factor of'):
            if line.endswith('.'):
                line = line[:-1]
            parts = line.split()
            result_dict['rcw'] = int(parts[-1])

        # extract areas
        if line.lstrip().startswith('Total logic block area'):
            # Logic area
            result_dict['area_le'] = float(line.split(':')[-1].strip())
        if line.lstrip().startswith('Total used logic block area'):
            # Logic area
            result_dict['area_le_used'] = float(line.split(':')[-1].strip())
        if line.lstrip().startswith('Total routing area'):
            # Routing area
            result_dict['area_r'] = float(line.split(',')[0].split(':')[-1].strip())
        
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

        # Nets
        if line.startswith('Absorbed logical nets'):
            abs_str, total_str = line.split(',')[0].strip('Absorbed logical nets ').split(' out of ')
            result_dict['nets_total'] = int(total_str)
            result_dict['nets_absorbed'] = int(abs_str)
            
        # Maxmimum routing channel utilization
        if line.startswith('Maximum routing channel utilization'):
            parts = line.split()
            result_dict['mrcu'] = float(parts[4])
            
            
        # histogram of routing channel utilization
        if line.startswith('Routing channel utilization histogram'):
            # read next 10 lines that indicate the routing channel utilization
            # notice the vpr.out seems something  wrong with the numbers
            # after 0.6, every is offset by one. see the vpr.out and you will understand
            for i in range(10):
                line = f.readline()
                parts = line.strip().replace('(', '').replace(')', '').replace(':', '').replace('%', '').split()
                # deal with the strange offset
                start_range = float(parts[1])
                if start_range > 0.6:
                    start_range -= 0.1
                end_range = start_range + 0.1 # instead of directly using the end range in the file, which contains 'inf', we use start_range + 0.1
                result_dict[f'rcu_{end_range:.1f}'] = float(parts[4]) / 100

        # Arithmetic modes usage (for DCC3 architectures)
        # Parses: "Arithmetic modes usage (ble5):" section
        # NOTE: Counter-intuitive naming in VPR!
        #   arithmetic_1chain : N  (ternary chain - 2 adders connected as ternary unit)
        #   arithmetic_2chains : M (simple chain - 2 independent/separate adder chains)
        if line.startswith('Arithmetic modes usage'):
            for i in range(5):  # Read up to 5 lines to find the modes
                line = f.readline().strip()
                if not line or not ':' in line:
                    break
                if line.startswith('arithmetic_1chain'):
                    parts = line.split(':')
                    result_dict['arithmetic_1chain'] = int(parts[1].strip())
                elif line.startswith('arithmetic_2chains'):
                    parts = line.split(':')
                    result_dict['arithmetic_2chains'] = int(parts[1].strip())

    f.close()

    # calculate wire length per grid
    if (result_dict['gridtotal'] != 0) and (result_dict['twl'] != 0):
        result_dict['wlpg'] = result_dict['twl'] / result_dict['gridtotal']

    # calculate total MWTA area
    if result_dict['area_r'] > 0 and result_dict['area_le'] > 0 and result_dict['area_le_used'] > 0:
        result_dict['area_total'] = result_dict['area_le'] + result_dict['area_r']
        result_dict['area_total_used'] = result_dict['area_le_used'] + result_dict['area_r']
    
    # Calculate LE ratios
    if result_dict['tle'] > 0:
        tle = result_dict['tle']
        if result_dict['lelr'] > 0:
            result_dict['lelr_frac'] = result_dict['lelr'] / tle
        if result_dict['lelo'] > 0:
            result_dict['lelo_frac'] = result_dict['lelo'] / tle
        if result_dict['lero'] > 0:
            result_dict['lero_frac'] = result_dict['lero'] / tle
    
    # Calculate net absorption ratio
    if result_dict['nets_total'] > 0 and result_dict['nets_absorbed'] >= 0:
        result_dict['nets_absorbed_frac'] = result_dict['nets_absorbed'] / result_dict['nets_total']

    return result_dict


def extract_fle_histogram(path='.', block_types=None) -> dict:
    """
    Extract FLE usage histogram from clustering_profile.echo file.

    Parses the clustering profile to count how many CLBs have each FLE utilization
    level (0-10 FLEs used per CLB).

    Args:
        path: Directory containing clustering_profile.echo (typically the 'temp' folder of a VTR run)
        block_types: List of block types to include (e.g., ['clb']).
                     If None, defaults to ['clb'] to exclude IO and memory blocks.

    Returns:
        Dictionary with:
        - 'fle_histogram': list of 11 counts [count_0, count_1, ..., count_10]
          where count_i = number of CLBs using exactly i FLEs
        - 'total_clbs': total number of CLBs analyzed
        - 'avg_fle_util': average FLE utilization (0.0-10.0)
        - 'fle_histogram_frac': fractional histogram (each count / total_clbs)
    """
    if block_types is None:
        block_types = ['clb']  # Default to only CLBs (exclude io, memory, etc.)

    result = {
        'fle_histogram': [0] * 11,  # Counts for 0-10 FLEs used
        'total_clbs': 0,
        'avg_fle_util': 0.0,
        'fle_histogram_frac': [0.0] * 11,
    }

    profile_path = os.path.join(path, 'clustering_profile.echo')
    if not os.path.exists(profile_path):
        return result

    fle_counts = []
    current_block_type = None

    with open(profile_path, 'r') as f:
        for line in f:
            line_stripped = line.strip()

            # Match CLB header lines like "CLB ID: 0 | Name: ... | Type: clb"
            if line_stripped.startswith('CLB ID:') and '| Type:' in line_stripped:
                # Extract the block type
                type_match = re.search(r'\|\s*Type:\s*(\w+)', line_stripped)
                if type_match:
                    current_block_type = type_match.group(1).lower()
                else:
                    current_block_type = None
                continue

            # Match lines like "FLE UTILIZATION: 10 / 10 (100.0%)"
            if line_stripped.startswith('FLE UTILIZATION:'):
                # Only count if the current block is of a type we care about
                if current_block_type is not None and current_block_type in block_types:
                    # Extract the used FLE count (first number)
                    match = re.search(r'FLE UTILIZATION:\s*(\d+)\s*/\s*(\d+)', line_stripped)
                    if match:
                        used_fles = int(match.group(1))
                        # Clamp to 0-10 range just in case
                        used_fles = max(0, min(10, used_fles))
                        fle_counts.append(used_fles)

    if not fle_counts:
        return result

    # Build histogram
    histogram = [0] * 11
    for count in fle_counts:
        histogram[count] += 1

    total_clbs = len(fle_counts)
    avg_util = sum(fle_counts) / total_clbs if total_clbs > 0 else 0.0
    histogram_frac = [h / total_clbs for h in histogram] if total_clbs > 0 else [0.0] * 11

    result['fle_histogram'] = histogram
    result['total_clbs'] = total_clbs
    result['avg_fle_util'] = avg_util
    result['fle_histogram_frac'] = histogram_frac

    return result


def extract_arithmetic_ble5_input_histogram(path='.') -> dict:
    """
    Extract histogram of input pin usage for arithmetic-mode BLE5s.

    Parses the clustering profile to count how many of the in[0..4] pins
    are used for each BLE5 whose mode contains "arithmetic".

    Args:
        path: Directory containing clustering_profile.echo (typically the 'temp' folder of a VTR run)

    Returns:
        Dictionary with:
        - 'input_histogram': list of 6 counts [count_0, count_1, ..., count_5]
          where count_i = number of arithmetic BLE5s using exactly i input pins (in[0..4])
        - 'total_arithmetic_ble5s': total number of arithmetic BLE5s analyzed
        - 'avg_input_util': average input pin utilization (0.0-5.0)
        - 'input_histogram_frac': fractional histogram (each count / total)
        - 'mode_breakdown': dict mapping mode name -> histogram for that mode
    """
    result = {
        'input_histogram': [0] * 6,  # Counts for 0-5 input pins used
        'total_arithmetic_ble5s': 0,
        'avg_input_util': 0.0,
        'input_histogram_frac': [0.0] * 6,
        'mode_breakdown': {},  # mode_name -> [0..5] histogram
    }

    profile_path = os.path.join(path, 'clustering_profile.echo')
    if not os.path.exists(profile_path):
        return result

    input_counts = []  # List of (mode_name, num_inputs_used)

    with open(profile_path, 'r') as f:
        current_mode = None
        in_pins_section = False
        current_in_pins_used = 0

        for line in f:
            line_stripped = line.strip()

            # Match BLE5 lines like "BLE5[0] mode=arithmetic" or "BLE5[1] mode=arithmetic_1chain"
            if 'BLE5[' in line and 'mode=' in line:
                # Save previous BLE5 if it was arithmetic
                if current_mode is not None and 'arithmetic' in current_mode:
                    input_counts.append((current_mode, current_in_pins_used))

                # Extract mode name
                match = re.search(r'mode=(\S+)', line_stripped)
                if match:
                    mode_name = match.group(1)
                    if 'arithmetic' in mode_name:
                        current_mode = mode_name
                        current_in_pins_used = 0
                        in_pins_section = False
                    else:
                        current_mode = None
                else:
                    current_mode = None
                continue

            # Check if we're entering the Pins section
            if current_mode is not None and line_stripped == 'Pins:':
                in_pins_section = True
                continue

            # Check if we're leaving the Pins section (new section or new BLE5/FLE)
            if in_pins_section and (line_stripped.startswith('Atoms:') or
                                    'BLE5[' in line or
                                    'FLE[' in line or
                                    line_stripped.startswith('MOLECULES') or
                                    line_stripped.startswith('ATOM PLACEMENTS') or
                                    line_stripped == ''):
                in_pins_section = False

            # Parse input pins (in[0] through in[4])
            if in_pins_section and current_mode is not None:
                # Match lines like "in[0] = 1 (atom.port[0])" or "in[0] = 0"
                pin_match = re.match(r'\s*in\[([0-4])\]\s*=\s*(\d+)', line_stripped)
                if pin_match:
                    pin_value = int(pin_match.group(2))
                    if pin_value > 0:
                        current_in_pins_used += 1

        # Don't forget the last BLE5
        if current_mode is not None and 'arithmetic' in current_mode:
            input_counts.append((current_mode, current_in_pins_used))

    if not input_counts:
        return result

    # Build overall histogram
    histogram = [0] * 6
    mode_histograms = {}  # mode_name -> [0..5] histogram

    for mode_name, count in input_counts:
        # Clamp to 0-5 range
        count = max(0, min(5, count))
        histogram[count] += 1

        # Track per-mode histogram
        if mode_name not in mode_histograms:
            mode_histograms[mode_name] = [0] * 6
        mode_histograms[mode_name][count] += 1

    total_ble5s = len(input_counts)
    total_inputs_used = sum(count for _, count in input_counts)
    avg_util = total_inputs_used / total_ble5s if total_ble5s > 0 else 0.0
    histogram_frac = [h / total_ble5s for h in histogram] if total_ble5s > 0 else [0.0] * 6

    result['input_histogram'] = histogram
    result['total_arithmetic_ble5s'] = total_ble5s
    result['avg_input_util'] = avg_util
    result['input_histogram_frac'] = histogram_frac
    result['mode_breakdown'] = mode_histograms

    return result


def extract_molecule_chain_stats(path='.') -> dict:
    """
    Extract chain and simple_chain molecule counts from pre_packing_molecules_and_patterns.echo.

    This function counts the number of 'chain' (ternary chain) and 'simple_chain' (independent
    carry chains) molecules, which is useful for analyzing how well synthesis maps to ternary
    adder architectures like DCC3.

    Args:
        path: Directory containing pre_packing_molecules_and_patterns.echo
              (typically the 'temp' folder of a VTR run)

    Returns:
        Dictionary with:
        - 'chain_molecules': count of chain (ternary) molecules
        - 'simple_chain_molecules': count of simple_chain molecules
        - 'total_chain_molecules': chain_molecules + simple_chain_molecules
        - 'chain_ratio': chain_molecules / total_chain_molecules (0 if no chains)
    """
    result = {
        'chain_molecules': 0,
        'simple_chain_molecules': 0,
        'total_chain_molecules': 0,
        'chain_ratio': 0.0,
    }

    echo_path = os.path.join(path, 'pre_packing_molecules_and_patterns.echo')
    if not os.path.exists(echo_path):
        return result

    chain_count = 0
    simple_chain_count = 0

    with open(echo_path, 'r') as f:
        for line in f:
            # Lines that start a new molecule look like: "molecule type: chain" or "molecule type: simple_chain"
            if line.startswith('molecule type:'):
                mol_type = line.split(':', 1)[1].strip()
                if mol_type == 'chain':
                    chain_count += 1
                elif mol_type == 'simple_chain':
                    simple_chain_count += 1

    total = chain_count + simple_chain_count
    result['chain_molecules'] = chain_count
    result['simple_chain_molecules'] = simple_chain_count
    result['total_chain_molecules'] = total
    result['chain_ratio'] = chain_count / total if total > 0 else 0.0

    return result
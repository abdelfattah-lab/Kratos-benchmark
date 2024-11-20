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
                val = traverse_tree(tree, key.split('.'))
                result_dict[key] = val if val > 0 else -1

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
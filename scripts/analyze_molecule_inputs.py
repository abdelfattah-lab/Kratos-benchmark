#!/usr/bin/env python3
"""
Analyze molecule patterns to categorize adder inputs.

For each adder in chain and simple_chain molecules, check what feeds pin a[0] and b[0]:
- Latch: signals from .latch definitions
- Adder: signals from .subckt adder (sumout/cout outputs)
- LUT/Names: signals from .names definitions
- Constant: gnd or vcc
- Unconn: unconnected pin (missing from echo file)

Usage:
    python analyze_molecule_inputs.py <temp_folder>
    python analyze_molecule_inputs.py /path/to/experiment/temp/

The script expects to find in the temp folder:
    - pre_packing_molecules_and_patterns.echo
    - design.pre-vpr.blif
"""

import re
import sys
from pathlib import Path
from collections import defaultdict


def parse_blif_net_types(blif_file):
    """
    Parse the BLIF file to build a mapping of net names to their driver types.

    Returns a dict: net_name -> type ('latch', 'adder', 'lut', 'constant', 'input')
    """
    net_types = {}

    # Constants are always available
    net_types['gnd'] = 'constant'
    net_types['vcc'] = 'constant'

    with open(blif_file, 'r') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Handle line continuations (lines ending with \)
        while line.endswith('\\') and i + 1 < len(lines):
            i += 1
            line = line[:-1] + ' ' + lines[i].strip()

        # Parse .latch statements
        # Format: .latch <input> <output> <type> <clk> <init>
        if line.startswith('.latch '):
            parts = line.split()
            if len(parts) >= 3:
                output_net = parts[2]  # Second token is the output
                net_types[output_net] = 'latch'

        # Parse .subckt adder statements
        # Format: .subckt adder b=... a=... cin=... sumout=... cout=...
        elif line.startswith('.subckt adder '):
            # Extract sumout and cout values
            sumout_match = re.search(r'sumout=(\S+)', line)
            cout_match = re.search(r'cout=(\S+)', line)
            if sumout_match:
                net_types[sumout_match.group(1)] = 'adder'
            if cout_match:
                net_types[cout_match.group(1)] = 'adder'

        # Parse .names statements (LUTs)
        # Format: .names <input1> <input2> ... <output>
        # The last token is the output
        elif line.startswith('.names '):
            parts = line.split()
            if len(parts) >= 2:
                output_net = parts[-1]  # Last token is the output
                net_types[output_net] = 'lut'

        # Parse .inputs (primary inputs)
        elif line.startswith('.inputs '):
            parts = line.split()[1:]  # Skip '.inputs'
            for net in parts:
                if net not in net_types:
                    net_types[net] = 'input'

        i += 1

    return net_types


def classify_source(net_name, net_types):
    """Classify the source of a signal using the BLIF net types mapping."""
    if net_name is None:
        return "unconn"

    if not net_name:
        return "unknown"

    # Check direct match
    if net_name in net_types:
        return net_types[net_name]

    # Handle explicit driver format from echo file: source.pin[0]
    # Extract net name if it has a pin suffix
    if '.' in net_name:
        base_name = net_name.rsplit('.', 1)[0]
        pin_suffix = net_name.rsplit('.', 1)[1] if '.' in net_name else ''

        # Check for explicit driver patterns
        if pin_suffix == 'out[0]':
            if base_name in ('gnd', 'vcc'):
                return 'constant'
            # Try looking up base_name in net_types (for .names outputs)
            if base_name in net_types:
                return net_types[base_name]
        elif pin_suffix == 'Q[0]':
            return 'latch'
        elif pin_suffix in ('sumout[0]', 'cout[0]'):
            return 'adder'

    # Fallback: check if net_name exists in mapping
    return net_types.get(net_name, 'unknown')


def parse_molecules(echo_file, net_types):
    """Parse the molecule echo file and extract adder input info."""

    with open(echo_file, 'r') as f:
        content = f.read()

    # Track statistics
    chain_stats = defaultdict(int)
    simple_chain_stats = defaultdict(int)

    # Track skipped adders for debugging
    skipped_reasons = defaultdict(int)
    total_adders_seen = 0

    # Track unknown nets for debugging (keep diverse set)
    unknown_nets = set()
    MAX_UNKNOWNS = 10

    # Split by molecule type
    molecules = re.split(r'\nmolecule type:', content)

    for mol in molecules:
        if not mol.strip():
            continue

        lines = mol.strip().split('\n')
        if not lines:
            continue

        mol_type = lines[0].strip()

        # Only process chain and simple_chain types
        if mol_type not in ['chain', 'simple_chain']:
            continue

        # Parse pattern indices
        current_index = None
        current_block = None
        pin_a_net = None
        pin_b_net = None
        has_pin_a = False
        has_pin_b = False
        is_adder = False

        for line in lines[1:]:
            # Check for pattern index
            pattern_match = re.match(r'\s+pattern index (\d+):', line)
            if pattern_match:
                # Save previous adder's info if valid
                if current_block and is_adder:
                    total_adders_seen += 1
                    # Only require pin_a to be present (pin_b can be unconn)
                    if has_pin_a:
                        a_class = classify_source(pin_a_net, net_types)
                        b_class = classify_source(pin_b_net if has_pin_b else None, net_types)
                        # Track unknowns for debugging
                        if a_class == 'unknown' and len(unknown_nets) < MAX_UNKNOWNS:
                            unknown_nets.add(pin_a_net)
                        if b_class == 'unknown' and len(unknown_nets) < MAX_UNKNOWNS:
                            unknown_nets.add(pin_b_net if has_pin_b else None)
                        key = tuple(sorted([a_class, b_class]))
                        if mol_type == 'chain':
                            chain_stats[key] += 1
                        elif mol_type == 'simple_chain':
                            simple_chain_stats[key] += 1
                    else:
                        skipped_reasons['no_pin_a'] += 1

                current_index = int(pattern_match.group(1))
                pin_a_net = None
                pin_b_net = None
                has_pin_a = False
                has_pin_b = False
                is_adder = False

                # Check if this pattern contains an adder
                if 'atom block' in line and 'empty' not in line:
                    # Check if it's an adder by looking for ADD in the name
                    if 'ADD' in line or 'add~' in line.lower():
                        is_adder = True
                    current_block = line
                else:
                    current_block = None
                    is_adder = False
                continue

            # Check for pin a[0] - try both formats
            # Format 1: -> pin a[0]: net <net_name> (sink <- <source>)
            # Format 2: -> pin a[0]: net <net_name> (sink)
            a_match = re.search(r'-> pin a\[0\]: net (\S+)', line)
            if a_match:
                has_pin_a = True
                net_name = a_match.group(1)
                # Check if there's an explicit source
                source_match = re.search(r'\(sink <- ([^)]+)\)', line)
                if source_match:
                    pin_a_net = source_match.group(1)
                else:
                    pin_a_net = net_name

            # Check for pin b[0]
            b_match = re.search(r'-> pin b\[0\]: net (\S+)', line)
            if b_match:
                has_pin_b = True
                net_name = b_match.group(1)
                source_match = re.search(r'\(sink <- ([^)]+)\)', line)
                if source_match:
                    pin_b_net = source_match.group(1)
                else:
                    pin_b_net = net_name

        # Don't forget the last adder
        if current_block and is_adder:
            total_adders_seen += 1
            if has_pin_a:
                a_class = classify_source(pin_a_net, net_types)
                b_class = classify_source(pin_b_net if has_pin_b else None, net_types)
                # Track unknowns for debugging
                if a_class == 'unknown' and len(unknown_nets) < MAX_UNKNOWNS:
                    unknown_nets.add(pin_a_net)
                if b_class == 'unknown' and len(unknown_nets) < MAX_UNKNOWNS:
                    unknown_nets.add(pin_b_net if has_pin_b else None)
                key = tuple(sorted([a_class, b_class]))
                if mol_type == 'chain':
                    chain_stats[key] += 1
                elif mol_type == 'simple_chain':
                    simple_chain_stats[key] += 1
            else:
                skipped_reasons['no_pin_a'] += 1

    return chain_stats, simple_chain_stats, total_adders_seen, skipped_reasons, unknown_nets


def print_stats(stats, name):
    """Print statistics in a readable format."""
    print(f"\n{'='*60}")
    print(f"{name} - Adder Input Statistics")
    print('='*60)

    # Calculate totals
    total = sum(stats.values())

    if total == 0:
        print("\nNo adders found.")
        return

    # Define pass-thru types (no LUT computation)
    pass_thru_types = {'latch', 'adder', 'constant', 'input', 'unconn'}

    # Categorize all combinations into three groups
    two_pass_thru = {}  # Both inputs are pass-thru
    one_lut = {}        # One LUT, one pass-thru
    two_lut = {}        # Both inputs are LUTs

    for key, count in stats.items():
        type_a, type_b = key
        a_is_pass = type_a in pass_thru_types
        b_is_pass = type_b in pass_thru_types
        a_is_lut = type_a == 'lut'
        b_is_lut = type_b == 'lut'

        if a_is_pass and b_is_pass:
            two_pass_thru[key] = count
        elif a_is_lut and b_is_lut:
            two_lut[key] = count
        elif (a_is_lut and b_is_pass) or (a_is_pass and b_is_lut):
            one_lut[key] = count
        else:
            # Unknown combinations - report separately
            two_pass_thru[key] = count

    total_two_pass = sum(two_pass_thru.values())
    total_one_lut = sum(one_lut.values())
    total_two_lut = sum(two_lut.values())

    print(f"\nTotal adders analyzed: {total}")

    # Category 1: Two pass-thru inputs
    print(f"\n[1] Two pass-thru inputs: {total_two_pass:5d} ({100*total_two_pass/total:.1f}%)")
    print("    (pass-thru = latch, adder, constant, unconn)")
    if two_pass_thru:
        # Group by subcategory
        by_latch = {k: v for k, v in two_pass_thru.items() if 'latch' in k and 'adder' not in k and 'constant' not in k and 'unconn' not in k}
        by_adder = {k: v for k, v in two_pass_thru.items() if 'adder' in k}
        by_const = {k: v for k, v in two_pass_thru.items() if 'constant' in k}
        by_unconn = {k: v for k, v in two_pass_thru.items() if 'unconn' in k}
        by_other = {k: v for k, v in two_pass_thru.items() if k not in by_latch and k not in by_adder and k not in by_const and k not in by_unconn}

        if by_latch:
            latch_total = sum(by_latch.values())
            print(f"    Latch-only: {latch_total} ({100*latch_total/total:.1f}%)")
            for key, count in sorted(by_latch.items(), key=lambda x: -x[1]):
                print(f"      {key[0]:12s} + {key[1]:12s}: {count:5d}")

        if by_adder:
            adder_total = sum(by_adder.values())
            print(f"    Involving adder: {adder_total} ({100*adder_total/total:.1f}%)")
            for key, count in sorted(by_adder.items(), key=lambda x: -x[1]):
                print(f"      {key[0]:12s} + {key[1]:12s}: {count:5d}")

        if by_const:
            const_total = sum(by_const.values())
            print(f"    Involving constant: {const_total} ({100*const_total/total:.1f}%)")
            for key, count in sorted(by_const.items(), key=lambda x: -x[1]):
                print(f"      {key[0]:12s} + {key[1]:12s}: {count:5d}")

        if by_unconn:
            unconn_total = sum(by_unconn.values())
            print(f"    Involving unconn: {unconn_total} ({100*unconn_total/total:.1f}%)")
            for key, count in sorted(by_unconn.items(), key=lambda x: -x[1]):
                print(f"      {key[0]:12s} + {key[1]:12s}: {count:5d}")

        if by_other:
            other_total = sum(by_other.values())
            print(f"    Other: {other_total} ({100*other_total/total:.1f}%)")
            for key, count in sorted(by_other.items(), key=lambda x: -x[1]):
                print(f"      {key[0]:12s} + {key[1]:12s}: {count:5d}")

    # Category 2: One LUT + one pass-thru
    print(f"\n[2] One LUT + one pass-thru: {total_one_lut:5d} ({100*total_one_lut/total:.1f}%)")
    if one_lut:
        for key, count in sorted(one_lut.items(), key=lambda x: -x[1]):
            print(f"      {key[0]:12s} + {key[1]:12s}: {count:5d} ({100*count/total:.1f}%)")

    # Category 3: Two LUTs
    print(f"\n[3] Two LUTs: {total_two_lut:5d} ({100*total_two_lut/total:.1f}%)")
    if two_lut:
        for key, count in sorted(two_lut.items(), key=lambda x: -x[1]):
            print(f"      {key[0]:12s} + {key[1]:12s}: {count:5d} ({100*count/total:.1f}%)")


def find_files(folder_path):
    """Find the required files in the given folder."""
    folder = Path(folder_path)

    # Check if path ends with temp/ or temp
    if folder.name != 'temp':
        # Maybe they passed the parent folder, check for temp/ subfolder
        temp_folder = folder / 'temp'
        if temp_folder.exists():
            folder = temp_folder

    echo_file = folder / 'pre_packing_molecules_and_patterns.echo'
    blif_file = folder / 'design.pre-vpr.blif'

    if not echo_file.exists():
        raise FileNotFoundError(f"Could not find pre_packing_molecules_and_patterns.echo in {folder}")

    if not blif_file.exists():
        raise FileNotFoundError(f"Could not find design.pre-vpr.blif in {folder}")

    return echo_file, blif_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_molecule_inputs.py <temp_folder>")
        print()
        print("Example:")
        print("  python analyze_molecule_inputs.py /path/to/experiment/temp/")
        print("  python analyze_molecule_inputs.py /path/to/experiment/  # will look for temp/ subfolder")
        sys.exit(1)

    folder_path = sys.argv[1]

    try:
        echo_file, blif_file = find_files(folder_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Analyzing:")
    print(f"  Echo file: {echo_file}")
    print(f"  BLIF file: {blif_file}")

    # Parse BLIF to get net types
    print("\nParsing BLIF file for net types...")
    net_types = parse_blif_net_types(str(blif_file))
    print(f"  Found {len(net_types)} net definitions")

    # Count by type
    type_counts = defaultdict(int)
    for net_type in net_types.values():
        type_counts[net_type] += 1
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")

    # Parse molecules
    chain_stats, simple_chain_stats, total_seen, skipped, unknown_nets = parse_molecules(str(echo_file), net_types)

    total_analyzed = sum(chain_stats.values()) + sum(simple_chain_stats.values())
    print(f"\nAdder coverage:")
    print(f"  Total adders in molecules: {total_seen}")
    print(f"  Total adders analyzed: {total_analyzed}")
    if skipped:
        print(f"  Skipped: {sum(skipped.values())}")
        for reason, count in skipped.items():
            print(f"    {reason}: {count}")

    # Print unknown nets for debugging
    if unknown_nets:
        print(f"\nUnknown nets (sample of up to 10):")
        for net in sorted(unknown_nets):
            if net is not None:
                print(f"  {net}")

    print_stats(chain_stats, "Chain Molecules (all indices)")
    print_stats(simple_chain_stats, "Simple Chain Molecules (all indices)")

    # Combined stats
    combined = defaultdict(int)
    for k, v in chain_stats.items():
        combined[k] += v
    for k, v in simple_chain_stats.items():
        combined[k] += v

    print_stats(combined, "Combined (Chain + Simple Chain)")


if __name__ == "__main__":
    main()

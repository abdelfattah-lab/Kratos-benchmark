""" 
Script to find how many pins are being used per ALM (for DD5, with all 12 ALM input pins) 
Usage: run script pointed at VPR output experiment root directory, optional arguments
include type of mean, zipfile name holding results, whether to ignore base or new results
"""

from lxml import etree
import numpy as np

import re
import zipfile
from pathlib import Path
import argparse
from tqdm.auto import tqdm

def extract_cin_s_tree(name: str):
    m_cin = re.search(r'(?:^|[_.-])cin\.([0-9]+)', name, re.IGNORECASE)
    cin = int(m_cin.group(1)) if m_cin else 0

    m_s = re.search(r'(?:^|[_.-])s\.([0-9]+(?:\.[0-9]+)?)', name, re.IGNORECASE)
    sparsity = float(m_s.group(1)) if m_s else float('nan')

    m_tree = re.search(r'vtr_[^-_]*?_c\.([A-Za-z0-9]+)', name, re.IGNORECASE)
    if m_tree:
        tree = m_tree.group(1).lower()
    else:
        m_tree2 = re.search(r'(wallace|dadda|cascade)', name, re.IGNORECASE)
        tree = m_tree2.group(1).lower() if m_tree2 else "unknown"

    return sparsity, tree, cin

def mean_accum(accum_data, iter_data, kind):
    if kind == "geometric":
        return accum_data * iter_data
    if kind == "harmonic":
        temp = iter_data.astype(float)
        return accum_data + np.divide(1.0, temp, out=np.zeros_like(temp), where=(temp != 0))
    return accum_data + iter_data  # else, arithmetic mean

def mean_final(accum_data, kind, num_mean):
    if num_mean <= 0:
        return accum_data
    if kind == "geometric":
        return np.power(accum_data, 1.0 / num_mean)
    if kind == "harmonic":
        return np.divide(num_mean, accum_data, out=np.zeros_like(accum_data), where=(accum_data != 0))
    return np.divide(accum_data, num_mean)  # else, arithmetic mean

def parse_design_net_alm_pin_hist(fileobj):
    hist = np.zeros(13, dtype=np.int64)
    n_alm_used = 0

    for event, elem in etree.iterparse(fileobj, events=("end",), tag="block"):
        inst = elem.get("instance", "")
        if inst.startswith("fle["):
            ports = {p.get("name"): (p.text or "").split()
                     for p in elem.xpath("./inputs/port")}

            pins_used = 0
            for tok in ports.get("in", []):
                if tok != "open":
                    pins_used += 1
            for tok in ports.get("in_direct", []):
                if tok != "open":
                    pins_used += 1

            if pins_used > 0:
                if pins_used > 12:
                    pins_used = 12
                hist[pins_used] += 1
                n_alm_used += 1

        elem.clear()

    return hist, n_alm_used

def find_design_net_member(zf: zipfile.ZipFile):
    for m in zf.namelist():
        if m.endswith("design.net"):
            return m
    return None

### Filter based on whether to take baseline or new results

_BASELINE_RE = re.compile(r"^baseline-\d+$", re.IGNORECASE)
_NEW_RE      = re.compile(r"^new-\d+$", re.IGNORECASE)

def is_excluded(exp_dir: Path, root: Path, ignore_mode: str) -> bool:
    """
    exp_dir is the folder that contains temp/ (i.e., exp_dir/temp exists).
    We exclude if any path component under root matches baseline-<digits> or new-<digits>
    depending on ignore_mode.
    """
    if ignore_mode == "none":
        return False

    try:
        rel_parts = exp_dir.relative_to(root).parts
    except ValueError:
        rel_parts = exp_dir.parts

    for part in rel_parts:
        if ignore_mode == "baseline" and _BASELINE_RE.match(part):
            return True
        if ignore_mode == "new" and _NEW_RE.match(part):
            return True

    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("experiments_root", help="Path to the experiment root containing subfolders")
    ap.add_argument("--zipname", default="largefile.zip", help="Zip file name inside each temp/ (default: largefile.zip)")
    ap.add_argument("--mean", choices=["arithmetic", "geometric", "harmonic"], default="arithmetic",
                    help="How to combine per-experiment histograms")
    ap.add_argument("--ignore", choices=["none", "baseline", "new"], default="none",
                    help="Exclude experiments under baseline-<seed> or new-<seed> subdirectories")
    ap.add_argument("--print-per-exp", action="store_true",
                    help="Print each experiment's histogram (otherwise only overall summary)")
    ap.add_argument("--include-zero", action="store_true",
                    help="Also print bin 0 (ALMs with 0 used pins). Normally 0 is not counted/printed.")
    args = ap.parse_args()

    root = Path(args.experiments_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)

    mean_kind = args.mean

    # Find any folder containing a "temp" dir; exp_dir is parent of temp/
    exp_dirs = sorted({p.parent for p in root.rglob("temp") if p.is_dir()}, key=lambda p: str(p))

    # Apply ignore filter
    exp_dirs = [d for d in exp_dirs if not is_excluded(d, root, args.ignore)]

    overall_hist = np.zeros(13, dtype=np.float64)
    if mean_kind == "geometric":
        overall_hist[:] = 1.0

    n_done = 0
    total_alms_counted = 0 
    n_alms_used = 0

    for exp_dir in tqdm(exp_dirs, total=len(exp_dirs), desc="experiments", unit="exp"):
        sparsity, tree, cin = extract_cin_s_tree(exp_dir.name)

        zip_path = exp_dir / "temp" / args.zipname
        if not zip_path.exists():
            cand = list((exp_dir / "temp").glob("*.zip"))
            if len(cand) == 1:
                zip_path = cand[0]
        if not zip_path.exists():
            continue

        try:
            with zipfile.ZipFile(zip_path) as zf:
                member = find_design_net_member(zf)
                if member is None:
                    continue

                with zf.open(member) as f:
                    hist_i, n_alms_i = parse_design_net_alm_pin_hist(f)

            n_done += 1
            total_alms_counted += n_alms_i
            overall_hist = mean_accum(overall_hist, hist_i.astype(np.float64), mean_kind)

            if args.print_per_exp:
                print(f"\n=== {exp_dir} ===")
                print(f"zip: {zip_path.name} | tree: {tree} | cin: {cin} | sparsity: {sparsity}")
                print(f"ALMs counted (pins_used>=1): {n_alms_i}")
                start_k = 0 if args.include_zero else 1
                for k in range(start_k, 13):
                    if hist_i[k] != 0:
                        print(f"  pins_used={k:2d}: {hist_i[k]}")

        except zipfile.BadZipFile:
            continue

    if n_done == 0:
        print("No valid experiments found after filtering (no temp/zip/design.net).")
        return

    overall_mean_hist = mean_final(overall_hist, mean_kind, n_done)

    print("\n==================== OVERALL ====================")
    print(f"Root: {root}")
    print(f"Ignore mode: {args.ignore}")
    print(f"Experiments included: {n_done}")
    print(f"Total ALMs counted across all experiments (pins_used>=1): {total_alms_counted}")
    print(f"Mean kind: {mean_kind}")

    print("\nMean histogram (bin k = mean #ALMs using exactly k pins):")
    start_k = 0 if args.include_zero else 1
    for k in range(start_k, 13):
        print(f"  k={k:2d}: {overall_mean_hist[k]}")

    print("\nAs array (index 0..12):")
    print(overall_mean_hist.tolist())

if __name__ == "__main__":
    main()

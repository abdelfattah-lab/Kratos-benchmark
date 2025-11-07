""" same functionality as alm_input_usage.py, but adapted for base Stratix-10 architecture 
    (BaseArchFactory) (obviously doesn't count the nonexistent extra pins) """

from lxml import etree
import numpy as np 
import matplotlib.pyplot as plt

import os
import sys
import re

from pathlib import Path
import argparse
import zipfile
from tqdm.auto import tqdm

def extract_cin_s_tree(name: str):
    # cin.N  (allow start, _, ., or - before 'cin.')
    m_cin = re.search(r'(?:^|[_.-])cin\.([0-9]+)', name, re.IGNORECASE)
    cin = int(m_cin.group(1)) if m_cin else 0

    # s.X  (float)  -- same separator logic as above
    m_s = re.search(r'(?:^|[_.-])s\.([0-9]+(?:\.[0-9]+)?)', name, re.IGNORECASE)
    sparsity = float(m_s.group(1)) if m_s else float('nan')

    # adder tree after ...vtr_*_c.<tree>
    m_tree = re.search(r'vtr_[^-_]*?_c\.([A-Za-z0-9]+)', name, re.IGNORECASE)
    if m_tree:
        tree = m_tree.group(1).lower()
    else:
        m_tree2 = re.search(r'(wallace|dadda|cascade)', name, re.IGNORECASE)
        tree = m_tree2.group(1).lower() if m_tree2 else "unknown"

    # return whatever you need; you were unpacking (sparsity, tree)
    return sparsity, tree

def save_basic_bar(output_path,data,tree=None,special_title=None):
    axis_labels = ["A","B","C","D","E","F","G","H"]
    plt.bar(axis_labels,data)
    plt.xlabel("Pins")
    plt.ylabel("Frequency")
    plt.title("Frequency of Each Pin's Use")
    if tree != None:
        plt.suptitle("tree type: " + str(tree))
    if special_title != None:
        plt.title(special_title)
    plt.savefig(output_path / "alm_pin_usage.png")
    plt.close()

def save_2d_conditional(output_path, conditional_prob,tree=None, special_title=None):
    
    #conditional_prob = conditional_prob.T
    
    labels = ["A","B","C","D","E","F","G","H"]

    fig, ax = plt.subplots(figsize=(6,5))
    im = ax.imshow(conditional_prob, vmin=0, vmax=1, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(8))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_yticks(range(8))
    ax.set_yticklabels(labels)
    ax.set_xlabel("... probability that pin S is used"); ax.set_ylabel("given pin R is used...")
    ax.set_title("Pin Usage Conditional Probability")
    if tree != None:
        plt.suptitle("tree type: " + str(tree))
    if special_title != None:
        ax.set_title(special_title)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="P(S|R)")
    plt.tight_layout()
    plt.savefig(output_path / "conditional_alm_pin_usage.png")
    plt.close()

def save_avg_other(output_path, data, tree=None,special_title=None):
    axis_labels = ["A","B","C","D","E","F","G","H"]
    plt.bar(axis_labels,data)
    plt.xlabel("Pin")
    plt.ylabel("Average # of Pins Used")
    plt.title("Average Number of Pins Used When Each Pin Is Used")
    if tree != None:
        plt.suptitle("tree type: " + str(tree))
    if special_title != None:
        plt.title(special_title)
    plt.savefig(output_path / "other_pin_usage.png")
    plt.close()    

def mean_accum(accum_data,iter_data,kind):
    """ accumulate stage of specified mean """

    if kind == "geometric":
        return accum_data * iter_data
    if kind == "harmonic":
        temp = iter_data.astype(float)
        return accum_data + np.divide(1.0, temp, out=np.zeros_like(temp), where=(temp != 0))
    else:
        return accum_data + iter_data

def mean_final(accum_data,kind, num_mean):
    """ final step of specified mean, num_mean is the number of items in the mean """

    if kind == "geometric":
        return np.power(accum_data, 1.0/num_mean)
    if kind == "harmonic":
        return np.divide(num_mean, accum_data, out=np.zeros_like(accum_data), where=(accum_data != 0))
    else:
        return np.divide(accum_data, num_mean)

def parse_design_net(file):
    """ special cond counts by index:
        0: Z1Z2Z3Z4 1: Z1Z3 2: Z2Z4 
        3: Z1Z2 4: Z3Z4 5: Z1Z4 6: Z2Z3   """

    # initialize counts

    total_counts = np.zeros(8, dtype=np.int64)
    cond_counts  = np.zeros((8, 8), dtype=np.int64)
    other_pin_usage_counts = np.zeros(8, dtype=np.int64)

    # Parse XML
    
    for event, elem in etree.iterparse(file, events=("end",), tag="block"):
        inst = elem.get("instance", "")
        if inst.startswith("fle["):
            
            in_use = np.zeros(8, dtype=np.int64)
            
            # Get the two input port lists (missing ports default to empty)
            ports = {p.get("name"): (p.text or "").split()
                    for p in elem.xpath("./inputs/port")}
            
            # A-H pins
            for i, tok in enumerate(ports.get("in", [])):
                if tok != "open":
                    in_use[i] = 1
        
            total_counts += in_use
            cond_counts  += np.outer(in_use, in_use)
            other_pin_usage_counts += (np.sum(in_use) - 1) * in_use
        
        elem.clear()
    
    avg_other_pin_usage = np.divide(other_pin_usage_counts,total_counts, 
        out=np.zeros_like(total_counts, dtype=float),where=total_counts > 0)
    
    conditional_prob = cond_counts / np.maximum(total_counts, 1)[:, None]
    conditional_prob[total_counts == 0, :] = 0
    
    return total_counts, conditional_prob, avg_other_pin_usage

# Get paths of folders, get design.net out of zip files
ap = argparse.ArgumentParser()
ap.add_argument("experiments_root", help="Path to the experiment root containing subfolders")
ap.add_argument("--mode", choices=["all","basic_bar","2D_conditional","avg_other"], default="all")
ap.add_argument("--mean", choices=["arithmetic","geometric","harmonic"], default="arithmetic")
ap.add_argument("--zipname", default="largefile.zip")
args = ap.parse_args()
mean = args.mean

root = Path(args.experiments_root).expanduser().resolve()
if not root.exists():
    raise FileNotFoundError(root)

# Calculate total averages
overall_total_counts = np.zeros(8, dtype=np.float64)
overall_cond_prob  = np.zeros((8, 8), dtype=np.float64)
overall_avg_others = np.zeros(8, dtype=np.float64)
if mean == "geometric":
    overall_total_counts = np.ones(8, dtype=np.float64)
    overall_cond_prob  = np.ones((8, 8), dtype=np.float64)
    overall_avg_others = np.ones(8, dtype=np.float64)

n_done = 0

# Repeat for each subexperiment folder under given experiment root
exp_dirs = sorted([d for d in root.iterdir() if d.is_dir()])
for exp_dir in tqdm(exp_dirs, total=len(exp_dirs), desc="experiments", unit="exp"):
    sparsity, tree = extract_cin_s_tree(exp_dir.name)
    zip_path = exp_dir / "temp" / args.zipname
    if not zip_path.exists():
        # fallback: any single zip in temp/
        cand = list((exp_dir / "temp").glob("*.zip"))
        if len(cand) == 1: zip_path = cand[0]
    if not zip_path.exists():
        print(f"[skip] no zip in {exp_dir}/temp")
        continue

    try:
        with zipfile.ZipFile(zip_path) as zf:
            # find design.net anywhere inside
            member = next((m for m in zf.namelist() if m.endswith("design.net")), None)
            if member is None:
                print(f"[skip] design.net not found in {zip_path}")
                continue

            # parse from stream
            with zf.open(member) as f:
                (total_counts, conditional_prob, avg_others) = parse_design_net(f)

            # outputs next to the experiment folder (adjust if you prefer elsewhere)
            outdir = exp_dir

            if args.mode in ("basic_bar","all"):
                save_basic_bar(outdir, total_counts,tree)
                overall_total_counts = mean_accum(overall_total_counts, total_counts, mean)

            if args.mode in ("2D_conditional","all"):
                save_2d_conditional(outdir, conditional_prob, tree)
                overall_cond_prob = mean_accum(overall_cond_prob, conditional_prob, mean)

            if args.mode in ("avg_other","all"):
                save_avg_other(outdir, avg_others, tree)
                overall_avg_others = mean_accum(overall_avg_others, avg_others, mean)

        n_done += 1

    except zipfile.BadZipFile:
        print(f"[skip] bad zip: {zip_path}")

# Do final step of mean (division/root)

overall_total_counts = mean_final(overall_total_counts, mean, n_done)
overall_cond_prob = mean_final(overall_cond_prob, mean, n_done)
overall_avg_others = mean_final(overall_avg_others, mean, n_done)

# Set up overall data mean and directory to hold graphs

mean_pin_usage = root / "mean_pin_usage"
mean_pin_usage.mkdir(parents=True, exist_ok=True)

if args.mode in ("basic_bar","all"):
    save_basic_bar(mean_pin_usage, overall_total_counts,special_title="Base Arch - Mean Pin Usage Counts")

if args.mode in ("2D_conditional","all"):
    save_2d_conditional(mean_pin_usage, overall_cond_prob,special_title="Base Arch - Mean Pin Usage Conditional Probability")

if args.mode in ("avg_other","all"):
    save_avg_other(mean_pin_usage, overall_avg_others,special_title="Base Arch - Mean Other Pins Used")

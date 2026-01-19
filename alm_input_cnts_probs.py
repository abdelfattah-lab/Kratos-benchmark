"""
Script to look through look through VPR output zipfiles and extract various conditional probabilities
"""

from lxml import etree
import numpy as np
import matplotlib.pyplot as plt

import re
from pathlib import Path
import argparse
import zipfile
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

    return sparsity, tree

def save_basic_bar(output_path, data, tree=None, special_title=None):
    axis_labels = ["A","B","C","D","E","F","G","H","Z1","Z2","Z3","Z4"]
    plt.bar(axis_labels, data)
    plt.xlabel("Pins")
    plt.ylabel("Frequency")
    plt.title("Frequency of Each Pin's Use")
    if tree is not None:
        plt.suptitle("tree type: " + str(tree))
    if special_title is not None:
        plt.title(special_title)
    plt.savefig(output_path / "alm_pin_usage.png")
    plt.close()

def save_basic_bar_spec(output_path, data, tree=None, special_title=None):
    axis_labels = ["all","Z1,Z3","Z2,Z4","Z1,Z2","Z3,Z4","Z1,Z4","Z2,Z3"]
    plt.bar(axis_labels, data)
    plt.xlabel("Special Z Pin Combos")
    plt.ylabel("Frequency")
    plt.title("Frequency of Each Special Z Combo's Use")
    if tree is not None:
        plt.suptitle("tree type: " + str(tree))
    if special_title is not None:
        plt.title(special_title)
    plt.savefig(output_path / "z_combo_usage.png")
    plt.close()

def save_2d_conditional(output_path, conditional_prob, tree=None, special_title=None):
    labels = ["A","B","C","D","E","F","G","H","Z1","Z2","Z3","Z4"]
    fig, ax = plt.subplots(figsize=(6,5))
    im = ax.imshow(conditional_prob, vmin=0, vmax=1, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(12))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_yticks(range(12))
    ax.set_yticklabels(labels)
    ax.set_xlabel("... probability that pin S is used"); ax.set_ylabel("given pin R is used...")
    ax.set_title("Pin Usage Conditional Probability")
    if tree is not None:
        plt.suptitle("tree type: " + str(tree))
    if special_title is not None:
        ax.set_title(special_title)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="P(S|R)")
    plt.tight_layout()
    plt.savefig(output_path / "conditional_alm_pin_usage.png")
    plt.close()

def save_spec_2d_cond(output_path, conditional_prob, tree=None, special_title=None):
    labels_x = ["A","B","C","D","E","F","G","H"]
    labels_y = ["all","Z1,Z3","Z2,Z4","Z1,Z2","Z3,Z4","Z1,Z4","Z2,Z3"]

    fig, ax = plt.subplots(figsize=(6,5))
    im = ax.imshow(conditional_prob, vmin=0, vmax=1, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(8))
    ax.set_xticklabels(labels_x, rotation=0)
    ax.set_yticks(range(7))
    ax.set_yticklabels(labels_y)
    ax.set_xlabel("... probability that pin S is used"); ax.set_ylabel("given pins R are used...")
    ax.set_title("Pin Usage Conditional Probability - Detailed Z Combos")
    if tree is not None:
        plt.suptitle("tree type: " + str(tree))
    if special_title is not None:
        ax.set_title(special_title)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="P(S|R)")
    plt.tight_layout()
    plt.savefig(output_path / "spec_cond_alm_pin_usage.png")
    plt.close()

def save_avg_other(output_path, data, tree=None, special_title=None):
    axis_labels = ["A","B","C","D","E","F","G","H","Z1","Z2","Z3","Z4"]
    plt.bar(axis_labels, data)
    plt.xlabel("Pin")
    plt.ylabel("Average # of Pins Used")
    plt.title("Average Number of Pins Used When Each Pin Is Used")
    if tree is not None:
        plt.suptitle("tree type: " + str(tree))
    if special_title is not None:
        plt.title(special_title)
    plt.savefig(output_path / "other_pin_usage.png")
    plt.close()

def mean_accum(accum_data, iter_data, kind):
    if kind == "geometric":
        return accum_data * iter_data
    if kind == "harmonic":
        temp = iter_data.astype(float)
        return accum_data + np.divide(1.0, temp, out=np.zeros_like(temp), where=(temp != 0))
    return accum_data + iter_data  # arithmetic

def mean_final(accum_data, kind, num_mean):
    if num_mean <= 0:
        return accum_data
    if kind == "geometric":
        return np.power(accum_data, 1.0/num_mean)
    if kind == "harmonic":
        return np.divide(num_mean, accum_data, out=np.zeros_like(accum_data), where=(accum_data != 0))
    return np.divide(accum_data, num_mean)  # arithmetic

def parse_design_net(file):
    total_counts = np.zeros(12, dtype=np.int64)
    cond_counts  = np.zeros((12, 12), dtype=np.int64)
    special_total_counts = np.zeros(7, dtype=np.int64)
    special_cond_counts = np.zeros((7,8), dtype=np.int64)
    other_pin_usage_counts = np.zeros(12, dtype=np.int64)

    n_alms_used = 0  # NEW: count ALMs with >=1 used pin

    for event, elem in etree.iterparse(file, events=("end",), tag="block"):
        inst = elem.get("instance", "")
        if inst.startswith("fle["):
            in_use = np.zeros(12, dtype=np.int64)

            ports = {p.get("name"): (p.text or "").split()
                     for p in elem.xpath("./inputs/port")}

            # A-H pins
            for i, tok in enumerate(ports.get("in", [])):
                if tok != "open":
                    in_use[i] = 1

            # Z1-Z4 pins
            for i, tok in enumerate(ports.get("in_direct", [])):
                if tok != "open":
                    in_use[i + 8] = 1

            if np.sum(in_use) > 0:
                n_alms_used += 1

            # special inputs
            if (in_use[8] * in_use[9] * in_use[11] * in_use[10] == 1):
                special_cond_counts[0] += in_use[0:8]
                special_total_counts[0] += 1
            if (in_use[8] * in_use[10] == 1):
                special_cond_counts[1] += in_use[0:8]
                special_total_counts[1] += 1
            if (in_use[9] * in_use[11] == 1):
                special_cond_counts[2] += in_use[0:8]
                special_total_counts[2] += 1
            if (in_use[8] * in_use[9] == 1):
                special_cond_counts[3] += in_use[0:8]
                special_total_counts[3] += 1
            if (in_use[10] * in_use[11] == 1):
                special_cond_counts[4] += in_use[0:8]
                special_total_counts[4] += 1
            if (in_use[8] * in_use[11] == 1):
                special_cond_counts[5] += in_use[0:8]
                special_total_counts[5] += 1
            if (in_use[9] * in_use[10] == 1):
                special_cond_counts[6] += in_use[0:8]
                special_total_counts[6] += 1

            total_counts += in_use
            cond_counts  += np.outer(in_use, in_use)
            other_pin_usage_counts += (np.sum(in_use) - 1) * in_use

        elem.clear()

    avg_other_pin_usage = np.divide(
        other_pin_usage_counts, total_counts,
        out=np.zeros_like(total_counts, dtype=float),
        where=total_counts > 0
    )

    conditional_prob = cond_counts / np.maximum(total_counts, 1)[:, None]
    conditional_prob[total_counts == 0, :] = 0

    special_cond_prob = special_cond_counts / np.maximum(special_total_counts, 1)[:, None]
    special_cond_prob[special_total_counts == 0, :] = 0

    # NEW: return n_alms_used too
    return total_counts, special_total_counts, conditional_prob, special_cond_prob, avg_other_pin_usage, n_alms_used

# -----------------------------------------------------------------------------
# baseline/new filtering (directory-name based)
# -----------------------------------------------------------------------------
_BASELINE_RE = re.compile(r"^baseline-\d+$", re.IGNORECASE)
_NEW_RE      = re.compile(r"^new-\d+$", re.IGNORECASE)

def is_excluded(exp_dir: Path, root: Path, ignore_mode: str) -> bool:
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

# -----------------------------------------------------------------------------
# Args
# -----------------------------------------------------------------------------
ap = argparse.ArgumentParser()
ap.add_argument("experiments_root", help="Path to the experiment root containing subfolders")
ap.add_argument("--mode", choices=["all","basic_bar","2D_conditional","avg_other"], default="all")
ap.add_argument("--mean", choices=["arithmetic","geometric","harmonic"], default="arithmetic")
ap.add_argument("--zipname", default="largefile.zip")
ap.add_argument("--ignore", choices=["none","baseline","new"], default="none",
                help="Exclude experiments under baseline-<seed> or new-<seed> subdirectories")
ap.add_argument("--eps", type=float, default=1e-12,
                help="Clamp epsilon for geometric/harmonic means when normalizing (default: 1e-12)")
args = ap.parse_args()
mean = args.mean
eps = float(args.eps)

root = Path(args.experiments_root).expanduser().resolve()
if not root.exists():
    raise FileNotFoundError(root)

# Accumulators (these are means of *normalized* quantities)
overall_total = np.zeros(12, dtype=np.float64)        # mean fraction of ALMs using each pin
overall_cond_prob  = np.zeros((12, 12), dtype=np.float64)
overall_avg_others = np.zeros(12, dtype=np.float64)
overall_spec_cond_prob = np.zeros((7,8), dtype=np.float64)
overall_special = np.zeros(7, dtype=np.float64)       # mean rate per ALM for each special combo

if mean == "geometric":
    overall_total[:] = 1.0
    overall_cond_prob[:] = 1.0
    overall_avg_others[:] = 1.0
    overall_spec_cond_prob[:] = 1.0
    overall_special[:] = 1.0  # IMPORTANT: for geometric mean, use ones not zeros

n_done = 0

# Find exp dirs, filter baseline/new
exp_dirs = sorted({p.parent for p in root.rglob("temp") if p.is_dir()}, key=lambda p: str(p))
exp_dirs = [d for d in exp_dirs if not is_excluded(d, root, args.ignore)]

for exp_dir in tqdm(exp_dirs, total=len(exp_dirs), desc="experiments", unit="exp"):
    sparsity, tree = extract_cin_s_tree(exp_dir.name)
    zip_path = exp_dir / "temp" / args.zipname
    if not zip_path.exists():
        cand = list((exp_dir / "temp").glob("*.zip"))
        if len(cand) == 1:
            zip_path = cand[0]
    if not zip_path.exists():
        print(f"[skip] no zip in {exp_dir}/temp")
        continue

    try:
        with zipfile.ZipFile(zip_path) as zf:
            member = next((m for m in zf.namelist() if m.endswith("design.net")), None)
            if member is None:
                print(f"[skip] design.net not found in {zip_path}")
                continue

            with zf.open(member) as f:
                (total_counts, special_total_counts,
                 conditional_prob, special_cond_prob, avg_others, n_alms_used) = parse_design_net(f)

            # If there are no used ALMs, this experiment can't contribute normalized rates
            if n_alms_used == 0:
                print(f"[skip] no used ALMs (fle inputs all open?) in {zip_path}")
                continue

            # -------------------------
            # NORMALIZATION (key change)
            # -------------------------
            total_frac = total_counts.astype(np.float64) / float(n_alms_used)
            special_rate = special_total_counts.astype(np.float64) / float(n_alms_used)

            # If using geometric/harmonic mean, clamp away from 0 to avoid issues
            if mean in ("geometric", "harmonic"):
                total_frac = np.clip(total_frac, eps, 1.0)
                special_rate = np.clip(special_rate, eps, 1.0)

            outdir = exp_dir

            if args.mode in ("basic_bar","all"):
                # Plot per-experiment normalized rates (optional, but consistent)
                save_basic_bar(outdir, total_frac, tree)
                overall_total = mean_accum(overall_total, total_frac, mean)

                save_basic_bar_spec(outdir, special_rate, tree)
                overall_special = mean_accum(overall_special, special_rate, mean)

            if args.mode in ("2D_conditional","all"):
                # Already per-experiment probabilities; average directly
                if mean in ("geometric", "harmonic"):
                    conditional_prob = np.clip(conditional_prob.astype(np.float64), eps, 1.0)
                    special_cond_prob = np.clip(special_cond_prob.astype(np.float64), eps, 1.0)

                save_2d_conditional(outdir, conditional_prob, tree)
                overall_cond_prob = mean_accum(overall_cond_prob, conditional_prob, mean)

                save_spec_2d_cond(outdir, special_cond_prob, tree)
                overall_spec_cond_prob = mean_accum(overall_spec_cond_prob, special_cond_prob, mean)

            if args.mode in ("avg_other","all"):
                # Already per-experiment averages; average directly
                if mean in ("geometric", "harmonic"):
                    avg_others = np.clip(avg_others.astype(np.float64), eps, 1.0)

                save_avg_other(outdir, avg_others, tree)
                overall_avg_others = mean_accum(overall_avg_others, avg_others, mean)

        n_done += 1

    except zipfile.BadZipFile:
        print(f"[skip] bad zip: {zip_path}")

# Final step of mean
overall_total = mean_final(overall_total, mean, n_done)
overall_cond_prob = mean_final(overall_cond_prob, mean, n_done)
overall_avg_others = mean_final(overall_avg_others, mean, n_done)
overall_spec_cond_prob = mean_final(overall_spec_cond_prob, mean, n_done)
overall_special = mean_final(overall_special, mean, n_done)

# Output directory for mean graphs
mean_pin_usage = root / "mean_pin_usage"
mean_pin_usage.mkdir(parents=True, exist_ok=True)

if args.mode in ("basic_bar","all"):
    save_basic_bar(mean_pin_usage, overall_total, special_title="Mean Pin Usage (Fraction of ALMs)")
    save_basic_bar_spec(mean_pin_usage, overall_special,
                        special_title="Mean Special Z Combo Rate (per ALM)")

if args.mode in ("2D_conditional","all"):
    save_2d_conditional(mean_pin_usage, overall_cond_prob,
                        special_title="Mean Pin Usage Conditional Probability")
    save_spec_2d_cond(mean_pin_usage, overall_spec_cond_prob,
                      special_title="Mean Pin Usage Conditional Probability - Special Z Combos")

if args.mode in ("avg_other","all"):
    save_avg_other(mean_pin_usage, overall_avg_others, special_title="Mean Other Pins Used")

# -----------------------------------------------------------------------------
# Print mean overall pin usage (normalized)
# -----------------------------------------------------------------------------
print("\n==================== MEAN OVERALL PIN USAGE ====================")
print(f"experiments_root: {root}")
print(f"ignore: {args.ignore} | mean: {mean} | n_done: {n_done}")
print("NOTE: values are FRACTION of used ALMs that use each pin (i.e., per-experiment normalized)")

pin_labels = ["A","B","C","D","E","F","G","H","Z1","Z2","Z3","Z4"]
print("\nMean fraction of ALMs using each pin:")
for lab, val in zip(pin_labels, overall_total):
    print(f"  {lab:>2s}: {val:.6f}   ({100.0*val:.3f}%)")

print("\nAs array (fractions):")
print(overall_total.tolist())
print("\nAs array (percent):")
print((overall_total * 100.0).tolist())

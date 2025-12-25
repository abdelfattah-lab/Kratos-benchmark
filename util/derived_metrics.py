"""
DataFrame modifiers to apply derived metrics.
"""

import pandas as pd

def apply_adp_used(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "adp_used" as "area_total_used" * "cpd"
    """
    
    # sanity checks
    assert 'area_total_used' in df.columns
    assert 'cpd' in df.columns

    df['adp_used'] = df['area_total_used'] * df['cpd']
    return df

def apply_adp_fle(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "adp_fle" as "area_fle" * "cpd"
    """
    
    # sanity checks
    assert 'area_fle' in df.columns
    assert 'cpd' in df.columns

    df['adp_fle'] = df['area_fle'] * df['cpd']
    return df
 
def apply_clb_avg_util(df: pd.DataFrame, fle_per_clb: int = 10) -> pd.DataFrame:
    """
    Returns "clb_avg_util" as "fle" / ("clb" * fle_per_clb)
    """
    
    # sanity checks
    assert 'clb' in df.columns
    assert 'fle' in df.columns

    df['clb_avg_util'] = df['fle'] / df['clb'] / fle_per_clb
    return df

def apply_lut5_to_adder_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "lut5/adder" as "lut5" / "adder"
    """
    
    # sanity checks
    assert 'lut5' in df.columns
    assert 'adder' in df.columns

    df['lut5/adder'] = 0.0
    df.loc[(df['lut5'] > 0) & (df['adder'] > 0), 'lut5/adder'] = df['lut5'] / df['adder']
    return df

def apply_lut5_concurrency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "lut5_concurrency" as "concurrent_lut5s" / "lut5"
    Use only with impl.arch.stratix_10.lut_skip.LUTSkipArchFactory for non-zero columns.
    """
    df['lut5_concurrency'] = 0.0
    
    # sanity checks
    if not 'concurrent_lut5s' in df.columns or not 'lut5' in df.columns:
        return df

    df.loc[(df['lut5'] > 0) & (df['concurrent_lut5s'] > 0), 'lut5_concurrency'] = df['concurrent_lut5s'] / df['lut5']
    return df

def apply_lut6_to_adder_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "lut6/adder" as "lut6" / "adder"
    """
    
    # sanity checks
    assert 'lut6' in df.columns
    assert 'adder' in df.columns

    df['lut6/adder'] = 0.0
    df.loc[(df['lut6'] > 0) & (df['adder'] > 0), 'lut6/adder'] = df['lut6'] / df['adder']
    return df

def apply_lut6_concurrency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "lut6_concurrency" as "concurrent_lut6s" / "lut6"
    Use only with impl.arch.stratix_10.lut_skip.LUTSkipArchFactory for non-zero columns.
    """
    df['lut6_concurrency'] = 0.0
    
    # sanity checks
    if not 'concurrent_lut6s' in df.columns or not 'lut6' in df.columns:
        return df

    df.loc[(df['lut6'] > 0) & (df['concurrent_lut6s'] > 0), 'lut6_concurrency'] = df['concurrent_lut6s'] / df['lut6']
    return df


def apply_lut56_to_adder_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "lut56/adder" as ("lut5" + "lut6") / "adder"
    """
    
    # sanity checks
    assert 'lut5' in df.columns
    assert 'lut6' in df.columns
    assert 'adder' in df.columns

    df['lut56/adder'] = 0.0
    df.loc[(df['lut5'] + df['lut6'] > 0) & (df['adder'] > 0), 'lut56/adder'] = (df['lut5'] + df['lut6']) / df['adder']
    return df

def apply_lut56_concurrency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "lut56_concurrency" as ("concurrent_lut5s" + "concurrent_lut6s") / ("lut5" + "lut6")
    Use only with impl.arch.stratix_10.lut_skip.LUTSkipArchFactory for non-zero columns.
    """
    df['lut56_concurrency'] = 0.0
    
    # sanity checks
    if not 'concurrent_lut5s' in df.columns or not 'concurrent_lut6s' in df.columns or not 'lut5' in df.columns or not 'lut6' in df.columns:
        return df

    df.loc[(df['lut5'] + df['lut6'] > 0) & (df['concurrent_lut5s'] >= 0) & (df['concurrent_lut6s'] >= 0), 'lut56_concurrency'] = (df['concurrent_lut5s'] + df['concurrent_lut6s']) / (df['lut5'] + df['lut6'])
    return df

def apply_adder_avg_util(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "adder_avg_util" as "adder" / ("fle" * 2)
    """

    # sanity checks
    assert 'adder' in df.columns
    assert 'fle' in df.columns
    
    df['adder_avg_util'] = 0.0
    df.loc[(df['adder'] > 0) & (df['fle'] > 0), 'adder_avg_util'] = df['adder'] / df['fle'] / 2
    return df

def apply_area_fle(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns "area_fle" as "fle" * "per_fle_area"
    """

    # sanity checks
    assert 'fle' in df.columns
    assert 'per_fle_area' in df.columns
    df['area_fle'] = 0.0
    df.loc[(df['fle'] > 0) & (df['per_fle_area'] > 0), 'area_fle'] = df['fle'] * df['per_fle_area']
    return df

def dcc1_gather_fle(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 'fle' column. If 'fle' already has values, keep them.
    Otherwise, sum 'fle1' + 'fle2' (for dcc1 architecture).
    """
    # If 'fle' column exists and has non-zero values, keep them
    if 'fle' in df.columns and (df['fle'] > 0).any():
        return df

    # Otherwise, compute from fle1 + fle2 (for dcc1 architecture)
    if 'fle1' in df.columns and 'fle2' in df.columns:
        if 'fle' not in df.columns:
            df['fle'] = 0.0
        df.loc[(df['fle1'] > 0) | (df['fle2'] > 0), 'fle'] = df['fle1'] + df['fle2']

    return df
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

    df['lut5/adder'] = df['lut5'] / df['adder']
    return df
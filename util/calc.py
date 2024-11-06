import math
from pandas import Series, DataFrame
from typing import Literal, Callable

def get_portrait_square(n: int) -> tuple[int, int]:
    """
    Returns an approximate (rows, columns) that is as "squarish" as possible that is guaranteed to fit n (i.e., width * height >= n).
    """
    # find "squarish" layout
    side1 = math.floor(math.sqrt(n))
    side2 = math.ceil(n / float(side1))

    # favor portrait layout
    return max(side1, side2), min(side1, side2)

def normalize_df(df: DataFrame, norm_type: Literal['min-max', 'mean'] = 'mean', cols: list[any] = None, min_max_vals: tuple[float, float] = None) -> None:
    """
    Normalizes specified columns of the DataFrame in-place.

    Optional arguments:
    * norm_type:'min-max'/'mean', type of normalization to apply.
    * cols:list[any], list of columns to apply normalization to. If None, then entire DataFrame is normalized. Default: None
    * min_max_vals:(min:float, max:float), minimum and maximum values to clamp to (i.e., normalization will be min-max). If None, then depends on norm_type. Default: None
    """
    extracted = df if cols is None else df[cols]
    
    if min_max_vals is not None:
        min_val, max_val = min_max_vals
        if min_val > max_val:
            raise ValueError(f"Minimum value {min_val} provided is larger than maximum value {max_val}!")
        
        diff = max_val - min_val
        extracted = min_val + diff * (extracted-extracted.min())/(extracted.max()-extracted.min())
    elif norm_type == 'min-max':
        extracted = (extracted-extracted.min())/(extracted.max()-extracted.min())
    elif norm_type == 'mean':
        extracted = (extracted-extracted.mean())/(extracted.std())
    else:
        raise ValueError("norm_type must be 'min-max' or 'mean'!")
    
    df.update(extracted)

def merge_op(
        parent: DataFrame, 
        child: DataFrame, 
        col_op: Callable[[Series, Series], Series],
        merge_on: list[str],
        ignore: list[str] = [],
    ) -> DataFrame:
    """
    Perform a merge on certain columns, then perform a specified operation on the remaining columns.

    Required arguments:
    * parent:DataFrame, parent to merge into.
    * child:DataFrame, child to be merged into parent.
    * col_op: (Series, Series) -> Series, operation to perform on remaining columns.
    * merge_on: columns on which to merge child into parent.

    Optional arguments:
    * ignore: columns on which no operation should be performed, i.e., the parent retains its value and the child is discarded. Default: empty list
    """
    # merge both dataframes together
    suffix = '_<m>'
    merged = parent.merge(child, on=merge_on, suffixes=('', suffix))

    # perform operation
    rem_cols = parent.columns.intersection(child.columns).drop(merge_on)
    suffixed_cols = []
    for col in rem_cols:
        suffixed_col = f"{col}{suffix}"
        suffixed_cols.append(suffixed_col)

        if col in ignore:
            continue
        merged[col] = col_op(merged[col], merged[suffixed_col])

    # drop remaining columns
    return merged.drop(columns=suffixed_cols)
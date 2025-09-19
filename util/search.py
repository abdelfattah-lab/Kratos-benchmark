"""
General search functions.
"""
import pandas as pd
import os

def query_df(df: pd.DataFrame, search_kwargs: dict[str, any]) -> pd.DataFrame | None:
    """
    Search a DataFrame for row(s) that match the provided column: values in search_kwargs.

    Required arguments:
    * df: DataFrame, DataFrame to search
    * search_kwargs: dict[str, any], column: value pairs to query.

    @return DataFrame if results are found, else return None.
    """
    # Generate query
    query_str_segments = []
    for col, val in search_kwargs.items():
        if isinstance(val, str):
            val = f'"{val}"'
        query_str_segments.append(f'`{col}`=={val}')
    query_str = ' & '.join(query_str_segments)
    
    # Make query
    result = None
    try:
        result = df.query(query_str)
    except:
        return None
    
    return None if result.empty else result

def find_first_file_with_suffix(dir: str, suffix: str) -> str | None:
    """
    Returns absolute path of the first file in the directory with the required suffix, or None if no file is found.

    Required arguments:
    * dir: str, directory to search.
    * suffix: str, suffix to use.
    """
    # sanity check
    if not os.path.exists(dir):
        raise ValueError(f"{dir} does not exist!")
    
    for filename in os.listdir(dir):
        if filename.endswith(suffix):
            return os.path.join(dir, filename)
    
    return None
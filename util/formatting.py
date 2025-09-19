"""
Convenience functions for formatting into strings.
"""

from io import StringIO

def gen_time_elapsed(seconds: float, dp: int = 3) -> str:
    """
    Returns a string of hours, minutes, seconds from given seconds.

    Optional arguments:
    * dp:int, decimal places to round seconds to.
    """
    mins = int(seconds // 60)
    hrs = int(mins // 60)
    days = int(hrs // 24)

    seconds -= mins * 60
    mins -= hrs * 60
    hrs -= days * 24

    ret = f"{round(seconds, ndigits=dp)} second(s)"
    if mins > 0:
        ret = f"{mins} minute(s), {ret}"
    if hrs > 0:
        ret = f"{hrs} hour(s), {ret}"
    if days > 0:
        ret = f"{days} day(s), {ret}"
    
    return ret

def pretty(d: dict, indent=0, to_string=False) -> str:
    """
    Pretty-print a dictionary.

    Optional arguments:
    * indent:int, base indent, default 0
    * to_string:bool, True: returns a pretty-printed string; False: prints directly to console, default False
    """

    file = StringIO() if to_string else None

    for key, value in d.items():
        print('\t' * indent + str(key), end='', file=file)
        if isinstance(value, dict):
            print(file=file)
            pretty(value, indent+1)
        else:
            print(f": {value}", file=file)

    if to_string:
        ret = file.getvalue()
        file.close()
        return ret

    return None
import os
from math import ceil

def gen_verilog_random_hex_constant(n: int) -> str:
    """
    Generates n-bit hexadecimal constant for Verilog, i.e., n'h...
    """
    # sanity checks
    assert n > 0

    gen_bytes = ceil(n / 8) # number of bytes to generate
    extra_bits = 8 * gen_bytes - n # extra bits to trim off the front

    hex_str = os.urandom(gen_bytes).hex()
    if extra_bits >= 4:
        # drop first hex character
        hex_str = hex_str[1:]
        extra_bits -= 4
    if extra_bits > 0:
        # AND mask and keep remaining bits
        c = hex_str[0]
        cur_val = int(c) if c.isdigit() else 10 + ord(c) - ord('a')
        mask = 2**(4-extra_bits) - 1
        hex_str = hex(mask & cur_val)[2] + hex_str[1:]
    
    # return constant
    return f"{n}'h{hex_str}"
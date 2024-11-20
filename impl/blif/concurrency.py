from structure.blif import BlifDesign
from random import randint
from datetime import datetime as dt
from math import ceil

DEFAULTS = {
    'adder_count': 100,
    'lut5_adder_ratio': 1.0,
}

# Basic template for this BlifMaker.
TEMPLATE = """# Written by impl.blif.concurrency.Concurrent5LUTAdderBlifMaker on {datetime}

.model conc_{adder_count}_{lut5_count}_model

.inputs global_cin {adder_chain_inputs} {lut5_chain_inputs}
.outputs global_cout {adder_chain_outputs} {lut5_chain_outputs}

# Adder chain
{adder_chain}

# 5-LUT chain
{lut5_chain}

.end 



# adder model

.model adder

.inputs a b cin 
.outputs cout sumout 
.blackbox 

.end 
"""

class Concurrent5LUTAdderBlifDesign(BlifDesign):
    """
    Make a N-adder chain and M 5-LUT chain in parallel.
    5-LUT chain is done w the following in groups of 5:
    1. Use 5 inputs, shared across all 5-LUTs.
    2. Randomize LUT truth table.
    3. Use 5 outputs as inputs for the next group.
    """
    def get_name(self, adder_count: int, lut5_adder_ratio: float, **kwargs):
        return f"conc-blif_N.{adder_count}_r.{lut5_adder_ratio:.3f}"

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
        return self.verify_required_keys(DEFAULTS, [], params)
    
    def _gen_adder_chain(self, adder_count: int) -> dict[str, str]:
        # keep trackers
        last_cin = 'global_cin'
        inputs = []
        outputs = []
        subckts = []

        for i in range(adder_count):
            # add inputs
            adder_a = f"adder_a~{i}"
            adder_b = f"adder_b~{i}"
            inputs.append(adder_a)
            inputs.append(adder_b)

            # add output
            adder_sumout = f"adder_sumout~{i}"
            outputs.append(adder_sumout)

            # make cout
            adder_cout = f"adder_cout~{i}" if i < adder_count - 1 else "global_cout"
            
            # make subckt
            subckt = f".subckt adder a={adder_a} b={adder_b} cin={last_cin} cout={adder_cout} sumout={adder_sumout}"
            subckts.append(subckt)

            # assign next cin
            last_cin = adder_cout

        return dict(
            adder_chain_inputs=" ".join(inputs),
            adder_chain_outputs=" ".join(outputs),
            adder_chain="\n\n".join(subckts),
        )
    
    def _gen_lut5_random_covers(self) -> str:
        COVER_BITS = ['0', '1', '-']
        covers = []
        used_input_covers = []

        # Generate 2-3 covers
        for _ in range(randint(2, 3)):
            while True:
                cover = ""
                for __ in range(5):
                    cover += COVER_BITS[randint(0, 2)]
                
                if not cover in used_input_covers:
                    break
            
            used_input_covers.append(cover)
            cover += " " + str(randint(0, 1))
            covers.append(cover)

        return "\n".join(covers)

    def _gen_lut5_chain(self, lut5_count: int) -> dict[str]:
        in_prefix = "lut5_in"
        first_ins = None
        last_outs = []
        lut5s = []
        groups = ceil(lut5_count / 5)

        for i in range(groups):
            group_count = min(5, lut5_count - i*5)
            inputs = " ".join([f"{in_prefix}{i}~{x}" for x in range(5)])
            if first_ins is None:
                first_ins = inputs
            out_prefix = f"{in_prefix}{i+1}"

            last_outs = []
            for j in range(group_count):
                output = f"{out_prefix}~{j}"
                lut5 = f".names {inputs} {output}\n{self._gen_lut5_random_covers()}"
                lut5s.append(lut5)

                if i == groups-1:
                    last_outs.append(output)
        
        return dict(
            lut5_chain_inputs=first_ins,
            lut5_chain_outputs=" ".join(last_outs),
            lut5_chain="\n\n".join(lut5s),
        )

    def gen_blif(self, adder_count: int, lut5_adder_ratio: float, **kwargs) -> str:
        """
        Generate .blif file in a string.

        Required arguments:
        * adder_count: int, number of adders in the chain.
        * lut5_adder_ratio: float, desired lut5 / adder ratio. e.g., a value of 1.5 means 3 5-LUTs for every 2 adders.
        """

        # sanity checks
        if adder_count <= 0:
            raise ValueError("Require at least 1 adder!")
        if lut5_adder_ratio <= 0:
            raise ValueError("Require strictly positive lut5_adder_ratio!")
        
        # Get 5-LUTs required.
        lut5_count = round(adder_count * lut5_adder_ratio)

        # Fill in template.
        return TEMPLATE.format(
            datetime=dt.now().isoformat(timespec='seconds'),
            adder_count=adder_count,
            lut5_count=lut5_count,
            **self._gen_lut5_chain(lut5_count),
            **self._gen_adder_chain(adder_count),
        )
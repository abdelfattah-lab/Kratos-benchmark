from flow_general import *

settings = {
    'data_width': 8,
    'row_num': 8,
    'col_num': 8,
    'length': 8,
    'sparsity': 0.5,
}

q = VTRRunner(flow_gemmt_fu_util, settings)
q.run(dry_run=False, clean=False)
q.wait()
print(q.get_result())

`ifndef __CALC_LOG_V__
`define __CALC_LOG_V__

function automatic integer clog_base(input integer x, input integer base);
    integer result;
    result = 0;
    // Increment result until base^result is greater than or equal to x
    while (x > 1) begin : clog_block
        x = (x + base - 1) / base; // Integer divide, effectively ceil(x / base)
        result++;
    end
    return result;
endfunction

`endif
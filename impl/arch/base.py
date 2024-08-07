from structure.arch import ArchFactory
from structure.util import ParamsChecker
from itertools import combinations
from collections import Counter

TEMPLATE = '''<!-- Comments are removed to save file size -->
<architecture>

  <models>
    <model name="multiply">
      <input_ports>
        <port name="a" combinational_sink_ports="out"/>
        <port name="b" combinational_sink_ports="out"/>
      </input_ports>
      <output_ports>
        <port name="out"/>
      </output_ports>
    </model>
    <model name="single_port_ram">
      <input_ports>
        <port name="we" clock="clk"/>
        <!-- control -->
        <port name="addr" clock="clk"/>
        <!-- address lines -->
        <port name="data" clock="clk"/>
        <!-- data lines can be broken down into smaller bit widths minimum size 1 -->
        <port name="clk" is_clock="1"/>
        <!-- memories are often clocked -->
      </input_ports>
      <output_ports>
        <port name="out" clock="clk"/>
        <!-- output can be broken down into smaller bit widths minimum size 1 -->
      </output_ports>
    </model>
    <model name="dual_port_ram">
      <input_ports>
        <port name="we1" clock="clk"/>
        <!-- write enable -->
        <port name="we2" clock="clk"/>
        <!-- write enable -->
        <port name="addr1" clock="clk"/>
        <!-- address lines -->
        <port name="addr2" clock="clk"/>
        <!-- address lines -->
        <port name="data1" clock="clk"/>
        <!-- data lines can be broken down into smaller bit widths minimum size 1 -->
        <port name="data2" clock="clk"/>
        <!-- data lines can be broken down into smaller bit widths minimum size 1 -->
        <port name="clk" is_clock="1"/>
        <!-- memories are often clocked -->
      </input_ports>
      <output_ports>
        <port name="out1" clock="clk"/>
        <!-- output can be broken down into smaller bit widths minimum size 1 -->
        <port name="out2" clock="clk"/>
        <!-- output can be broken down into smaller bit widths minimum size 1 -->
      </output_ports>
    </model>
    <model name="adder">
      <input_ports>
        <port name="a" combinational_sink_ports="cout sumout"/>
        <port name="b" combinational_sink_ports="cout sumout"/>
        <port name="cin" combinational_sink_ports="cout sumout"/>
      </input_ports>
      <output_ports>
        <port name="cout"/>
        <port name="sumout"/>
      </output_ports>
    </model>
  </models>
  <tiles>
    <tile name="io" area="0">
      <sub_tile name="io" capacity="8">
        <equivalent_sites>
          <site pb_type="io" pin_mapping="direct"/>
        </equivalent_sites>
        <input name="outpad" num_pins="1"/>
        <output name="inpad" num_pins="1"/>
        <clock name="clock" num_pins="1"/>
        <fc in_type="frac" in_val="0.15" out_type="frac" out_val="0.10"/>
        <pinlocations pattern="custom">
          <loc side="left">io.outpad io.inpad io.clock</loc>
          <loc side="top">io.outpad io.inpad io.clock</loc>
          <loc side="right">io.outpad io.inpad io.clock</loc>
          <loc side="bottom">io.outpad io.inpad io.clock</loc>
        </pinlocations>
      </sub_tile>
    </tile>
    <tile name="clb" area="53894">
      <sub_tile name="clb">
        <equivalent_sites>
          <site pb_type="clb" pin_mapping="direct"/>
        </equivalent_sites>
        <input name="I1" num_pins="{num_pins_I1}" equivalent="full"/>
        <input name="I2" num_pins="{num_pins_I2}" equivalent="full"/>
        <input name="I3" num_pins="{num_pins_I3}" equivalent="full"/>
        <input name="I4" num_pins="{num_pins_I4}" equivalent="full"/>
        <input name="cin" num_pins="1"/>
        <output name="O" num_pins="20" equivalent="none"/>
        <output name="cout" num_pins="1"/>
        <clock name="clk" num_pins="1"/>
        <fc in_type="frac" in_val="0.15" out_type="frac" out_val="0.10">
          <fc_override port_name="cin" fc_type="frac" fc_val="0"/>
          <fc_override port_name="cout" fc_type="frac" fc_val="0"/>
        </fc>
        <pinlocations pattern="spread"/>
      </sub_tile>
    </tile>
    <tile name="mult_36" height="4" area="396000">
      <sub_tile name="mult_36">
        <equivalent_sites>
          <site pb_type="mult_36" pin_mapping="direct"/>
        </equivalent_sites>
        <input name="a" num_pins="36"/>
        <input name="b" num_pins="36"/>
        <output name="out" num_pins="72"/>
        <fc in_type="frac" in_val="0.15" out_type="frac" out_val="0.10"/>
        <pinlocations pattern="spread"/>
      </sub_tile>
    </tile>
    <tile name="memory" height="6" area="548000">
      <sub_tile name="memory">
        <equivalent_sites>
          <site pb_type="memory" pin_mapping="direct"/>
        </equivalent_sites>
        <input name="addr1" num_pins="15"/>
        <input name="addr2" num_pins="15"/>
        <input name="data" num_pins="64"/>
        <input name="we1" num_pins="1"/>
        <input name="we2" num_pins="1"/>
        <output name="out" num_pins="64"/>
        <clock name="clk" num_pins="1"/>
        <fc in_type="frac" in_val="0.15" out_type="frac" out_val="0.10"/>
        <pinlocations pattern="spread"/>
      </sub_tile>
    </tile>
  </tiles>
  <!-- ODIN II specific config ends -->
  <!-- Physical descriptions begin -->
  <layout>
    <auto_layout aspect_ratio="1.0">
      <!--Perimeter of 'io' blocks with 'EMPTY' blocks at corners-->
      <perimeter type="io" priority="100"/>
      <corners type="EMPTY" priority="101"/>
      <!--Fill with 'clb'-->
      <fill type="clb" priority="10"/>
      <!--Column of 'mult_36' with 'EMPTY' blocks wherever a 'mult_36' does not fit. Vertical offset by 1 for perimeter.-->
      <col type="mult_36" startx="6" starty="1" repeatx="16" priority="20"/>
      <col type="EMPTY"   startx="6" starty="1" repeatx="16" priority="19"/>
      <!--Column of 'memory' with 'EMPTY' blocks wherever a 'memory' does not fit. Vertical offset by 1 for perimeter.-->
      <col type="memory" startx="2" starty="1" repeatx="16" priority="20"/>
      <col type="EMPTY" startx="2"  starty="1" repeatx="16" priority="19"/>
    </auto_layout>
  </layout>
  <device>
    <!-- VB & JL: Using Ian Kuon's transistor sizing and drive strength data for routing, at 40 nm. Ian used BPTM 
			     models. We are modifying the delay values however, to include metal C and R, which allows more architecture
			     experimentation. We are also modifying the relative resistance of PMOS to be 1.8x that of NMOS
			     (vs. Ian's 3x) as 1.8x lines up with Jeff G's data from a 45 nm process (and is more typical of 
			     45 nm in general). I'm upping the Rmin_nmos from Ian's just over 6k to nearly 9k, and dropping 
			     RminW_pmos from 18k to 16k to hit this 1.8x ratio, while keeping the delays of buffers approximately
			     lined up with Stratix IV. 
			     We are using Jeff G.'s capacitance data for 45 nm (in tech/ptm_45nm).
			     Jeff's tables list C in for transistors with widths in multiples of the minimum feature size (45 nm).
			     The minimum contactable transistor is 2.5 * 45 nm, so I need to multiply drive strength sizes in this file
	                     by 2.5x when looking up in Jeff's tables.
			     The delay values are lined up with Stratix IV, which has an architecture similar to this
			     proposed FPGA, and which is also 40 nm 
			     C_ipin_cblock: input capacitance of a track buffer, which VPR assumes is a single-stage
			     4x minimum drive strength buffer. -->
    <sizing R_minW_nmos="8926" R_minW_pmos="16067"/>
    <!-- The grid_logic_tile_area below will be used for all blocks that do not explicitly set their own (non-routing)
     	  area; set to 0 since we explicitly set the area of all blocks currently in this architecture file.
	    -->
    <area grid_logic_tile_area="0"/>
    <chan_width_distr>
      <x distr="uniform" peak="1.000000"/>
      <y distr="uniform" peak="1.000000"/>
    </chan_width_distr>
    <switch_block type="wilton" fs="3"/>
    <connection_block input_switch_name="ipin_cblock"/>
  </device>
  <switchlist>
    <!-- VB: the mux_trans_size and buf_size data below is in minimum width transistor *areas*, assuming the purple
           book area formula. This means the mux transistors are about 5x minimum drive strength.
           We assume the first stage of the buffer is 3x min drive strength to be reasonable given the large 
           mux transistors, and this gives a reasonable stage ratio of a bit over 5x to the second stage. We assume
           the n and p transistors in the first stage are equal-sized to lower the buffer trip point, since it's fed
           by a pass transistor mux. We can then reverse engineer the buffer second stage to hit the specified 
           buf_size (really buffer area) - 16.2x minimum drive nmos and 1.8*16.2 = 29.2x minimum drive.
           I then took the data from Jeff G.'s PTM modeling of 45 nm to get the Cin (gate of first stage) and Cout 
           (diff of second stage) listed below.  Jeff's models are in tech/ptm_45nm, and are in min feature multiples.
           The minimum contactable transistor is 2.5 * 45 nm, so I need to multiply the drive strength sizes above by 
           2.5x when looking up in Jeff's tables.
           Finally, we choose a switch delay (58 ps) that leads to length 4 wires having a delay equal to that of SIV of 126 ps.
           This also leads to the switch being 46% of the total wire delay, which is reasonable. -->
    <switch type="mux" name="0" R="551" Cin=".77e-15" Cout="4e-15" Tdel="58e-12" mux_trans_size="2.630740" buf_size="27.645901"/>
    <!--switch ipin_cblock resistance set to yeild for 4x minimum drive strength buffer-->
    <switch type="mux" name="ipin_cblock" R="2231.5" Cout="0." Cin="1.47e-15" Tdel="7.247000e-11" mux_trans_size="1.222260" buf_size="auto"/>
  </switchlist>
  <segmentlist>
    <!--- VB & JL: using ITRS metal stack data, 96 nm half pitch wires, which are intermediate metal width/space.  
             With the 96 nm half pitch, such wires would take 60 um of height, vs. a 90 nm high (approximated as square) Stratix IV tile so this seems
             reasonable. Using a tile length of 90 nm, corresponding to the length of a Stratix IV tile if it were square. -->
    <segment freq="1.000000" length="4" type="unidir" Rmetal="101" Cmetal="22.5e-15">
      <mux name="0"/>
      <sb type="pattern">1 1 1 1 1</sb>
      <cb type="pattern">1 1 1 1</cb>
    </segment>
  </segmentlist>
  <directlist>
    <direct name="adder_carry" from_pin="clb.cout" to_pin="clb.cin" x_offset="0" y_offset="-1" z_offset="0"/>
  </directlist>
  <complexblocklist>
    <!-- Define I/O pads begin -->
    <!-- Capacity is a unique property of I/Os, it is the maximum number of I/Os that can be placed at the same (X,Y) location on the FPGA -->
    <!-- Not sure of the area of an I/O (varies widely), and it's not relevant to the design of the FPGA core, so we're setting it to 0. -->
    <pb_type name="io">
      <input name="outpad" num_pins="1"/>
      <output name="inpad" num_pins="1"/>
      <clock name="clock" num_pins="1"/>
      <!-- IOs can operate as either inputs or outputs.
	     Delays below come from Ian Kuon. They are small, so they should be interpreted as
	     the delays to and from registers in the I/O (and generally I/Os are registered 
	     today and that is when you timing analyze them.
	     -->
      <mode name="inpad">
        <pb_type name="inpad" blif_model=".input" num_pb="1">
          <output name="inpad" num_pins="1"/>
        </pb_type>
        <interconnect>
          <direct name="inpad" input="inpad.inpad" output="io.inpad">
            <delay_constant max="4.243e-11" in_port="inpad.inpad" out_port="io.inpad"/>
          </direct>
        </interconnect>
      </mode>
      <mode name="outpad">
        <pb_type name="outpad" blif_model=".output" num_pb="1">
          <input name="outpad" num_pins="1"/>
        </pb_type>
        <interconnect>
          <direct name="outpad" input="io.outpad" output="outpad.outpad">
            <delay_constant max="1.394e-11" in_port="io.outpad" out_port="outpad.outpad"/>
          </direct>
        </interconnect>
      </mode>
      <!-- Every input pin is driven by 15% of the tracks in a channel, every output pin is driven by 10% of the tracks in a channel -->
      <!-- IOs go on the periphery of the FPGA, for consistency, 
          make it physically equivalent on all sides so that only one definition of I/Os is needed.
          If I do not make a physically equivalent definition, then I need to define 4 different I/Os, one for each side of the FPGA
        -->
      <!-- Place I/Os on the sides of the FPGA -->
      <power method="ignore"/>
    </pb_type>
    <!-- Define I/O pads ends -->
    <!-- Define general purpose logic block (CLB) begin -->
    <!--- Area calculation: Total Stratix IV tile area is about 8100 um^2, and a minimum width transistor 
	   area is 60 L^2 yields a tile area of 84375 MWTAs.
	   Routing at W=300 is 30481 MWTAs, leaving us with a total of 53000 MWTAs for logic block area 
	   This means that only 37% of our area is in the general routing, and 63% is inside the logic
	   block. Note that the crossbar / local interconnect is considered part of the logic block
	   area in this analysis. That is a lower proportion of of routing area than most academics
	   assume, but note that the total routing area really includes the crossbar, which would push
	   routing area up significantly, we estimate into the ~70% range. 
	   -->
    <pb_type name="clb">
      <input name="I1" num_pins="{num_pins_I1}" equivalent="full"/>
      <input name="I2" num_pins="{num_pins_I2}" equivalent="full"/>
      <input name="I3" num_pins="{num_pins_I3}" equivalent="full"/>
      <input name="I4" num_pins="{num_pins_I4}" equivalent="full"/>
      <input name="cin" num_pins="1"/>
      <output name="O" num_pins="20" equivalent="none"/>
      <output name="cout" num_pins="1"/>
      <clock name="clk" num_pins="1"/>
      <!-- Describe fracturable logic element.  
             Each fracturable logic element has a 6-LUT that can alternatively operate as two 5-LUTs with shared inputs. 
             The outputs of the fracturable logic element can be optionally registered
        -->
      <pb_type name="fle" num_pb="10">
        <input name="in" num_pins="8"/>
        <input name="cin" num_pins="1"/>
        <output name="out" num_pins="2"/>
        <output name="cout" num_pins="1"/>
        <clock name="clk" num_pins="1"/>
        <mode name="{n2_lutS}" disable_packing="False">
          <pb_type name="{lutSinter}" num_pb="1">
            <input name="in" num_pins="8"/>
            <input name="cin" num_pins="1"/>
            <output name="out" num_pins="2"/>
            <output name="cout" num_pins="1"/>
            <clock name="clk" num_pins="1"/>
            <pb_type name="{bleS}" num_pb="2">
              <input name="in" num_pins="{num_pins_lutS}"/>
              <input name="cin" num_pins="1"/>
              <output name="out" num_pins="1"/>
              <output name="cout" num_pins="1"/>
              <clock name="clk" num_pins="1"/>
              <mode name="{blutS}">
                <pb_type name="{flutS}" num_pb="1">
                  <input name="in" num_pins="{num_pins_lutS}"/>
                  <output name="out" num_pins="1"/>
                  <clock name="clk" num_pins="1"/>
                  <!-- Regular LUT mode -->
                  <pb_type name="{lutS}" blif_model=".names" num_pb="1" class="lut">
                    <input name="in" num_pins="{num_pins_lutS}" port_class="lut_in"/>
                    <output name="out" num_pins="1" port_class="lut_out"/>
                    <!-- LUT timing using delay matrix -->
                    <!-- These are the physical delay inputs on a Stratix IV LUT but because VPR cannot do LUT rebalancing,
                           we instead take the average of these numbers to get more stable results
                        82e-12
                        173e-12
                        261e-12
                        263e-12
                        398e-12
                        -->
                    <delay_matrix type="max" in_port="{lutS}.in" out_port="{lutS}.out">
{lutS_delat_mat}
                      </delay_matrix>
                  </pb_type>
                  <pb_type name="ff" blif_model=".latch" num_pb="1" class="flipflop">
                    <input name="D" num_pins="1" port_class="D"/>
                    <output name="Q" num_pins="1" port_class="Q"/>
                    <clock name="clk" num_pins="1" port_class="clock"/>
                    <T_setup value="66e-12" port="ff.D" clock="clk"/>
                    <T_clock_to_Q max="124e-12" port="ff.Q" clock="clk"/>
                  </pb_type>
                  <interconnect>
                    <direct name="direct1" input="{flutS}.in" output="{lutS}.in"/>
                    <direct name="direct2" input="{lutS}.out" output="ff.D">
                      <pack_pattern name="{bleS}" in_port="{lutS}.out" out_port="ff.D"/>
                    </direct>
                    <direct name="direct3" input="{flutS}.clk" output="ff.clk"/>
                    <mux name="mux1" input="ff.Q {lutS}.out" output="{flutS}.out">
                      <delay_constant max="25e-12" in_port="{lutS}.out" out_port="{flutS}.out"/>
                      <delay_constant max="45e-12" in_port="ff.Q" out_port="{flutS}.out"/>
                    </mux>
                  </interconnect>
                </pb_type>
                <interconnect>
                  <direct name="direct1" input="{bleS}.in" output="{flutS}.in"/>
                  <direct name="direct2" input="{bleS}.clk" output="{flutS}.clk"/>
                  <direct name="direct3" input="{flutS}.out" output="{bleS}.out"/>
                </interconnect>
              </mode>
              <mode name="arithmetic">
                <pb_type name="arithmetic" num_pb="1">
                  <input name="in" num_pins="{arithmetic_num_pins}"/>
                  <input name="cin" num_pins="1"/>
                  <output name="out" num_pins="1"/>
                  <output name="cout" num_pins="1"/>
                  <clock name="clk" num_pins="1"/>
                  <!-- Special dual-LUT mode that drives adder only -->
                  <pb_type name="adder_lut" blif_model=".names" num_pb="2" class="lut">
                    <input name="in" num_pins="{arithmetic_num_pins}" port_class="lut_in"/>
                    <output name="out" num_pins="1" port_class="lut_out"/>
                    <!-- LUT timing using delay matrix -->
                    <!-- These are the physical delay inputs on a Stratix IV LUT but because VPR cannot do LUT rebalancing,
                             we instead take the average of these numbers to get more stable results
                        82e-12
                        173e-12
                        261e-12
                        263e-12
                        -->
                    <delay_matrix type="max" in_port="adder_lut.in" out_port="adder_lut.out">
{arith_lut_delat_mat}
                      </delay_matrix>
                  </pb_type>
                  <pb_type name="adder" blif_model=".subckt adder" num_pb="1">
                    <input name="a" num_pins="1"/>
                    <input name="b" num_pins="1"/>
                    <input name="cin" num_pins="1"/>
                    <output name="cout" num_pins="1"/>
                    <output name="sumout" num_pins="1"/>
                    <delay_constant max="0.3e-9" in_port="adder.a" out_port="adder.sumout"/>
                    <delay_constant max="0.3e-9" in_port="adder.b" out_port="adder.sumout"/>
                    <delay_constant max="0.3e-9" in_port="adder.cin" out_port="adder.sumout"/>
                    <delay_constant max="0.3e-9" in_port="adder.a" out_port="adder.cout"/>
                    <delay_constant max="0.3e-9" in_port="adder.b" out_port="adder.cout"/>
                    <delay_constant max="0.01e-9" in_port="adder.cin" out_port="adder.cout"/>
                  </pb_type>
                  <pb_type name="ff" blif_model=".latch" num_pb="1" class="flipflop">
                    <input name="D" num_pins="1" port_class="D"/>
                    <output name="Q" num_pins="1" port_class="Q"/>
                    <clock name="clk" num_pins="1" port_class="clock"/>
                    <T_setup value="66e-12" port="ff.D" clock="clk"/>
                    <T_clock_to_Q max="124e-12" port="ff.Q" clock="clk"/>
                  </pb_type>
                  <interconnect>
                    <direct name="clock" input="arithmetic.clk" output="ff.clk"/>
                    <direct name="lut_in1" input="arithmetic.in[{arithmetic_pin_index}]" output="adder_lut[0:0].in[{arithmetic_pin_index}]"/>
                    <direct name="lut_in2" input="arithmetic.in[{arithmetic_pin_index}]" output="adder_lut[1:1].in[{arithmetic_pin_index}]"/>
                    <direct name="lut_to_add1" input="adder_lut[0:0].out" output="adder.a">
                      </direct>
                    <direct name="lut_to_add2" input="adder_lut[1:1].out" output="adder.b">
                      </direct>
                    <direct name="add_to_ff" input="adder.sumout" output="ff.D">
                      <pack_pattern name="chain" in_port="adder.sumout" out_port="ff.D"/>
                    </direct>
                    <direct name="carry_in" input="arithmetic.cin" output="adder.cin">
                      <pack_pattern name="chain" in_port="arithmetic.cin" out_port="adder.cin"/>
                    </direct>
                    <direct name="carry_out" input="adder.cout" output="arithmetic.cout">
                      <pack_pattern name="chain" in_port="adder.cout" out_port="arithmetic.cout"/>
                    </direct>
                    <mux name="sumout" input="ff.Q adder.sumout" output="arithmetic.out">
                      <delay_constant max="25e-12" in_port="adder.sumout" out_port="arithmetic.out"/>
                      <delay_constant max="45e-12" in_port="ff.Q" out_port="arithmetic.out"/>
                    </mux>
                  </interconnect>
                </pb_type>
                <interconnect>
                  <direct name="direct1" input="{bleS}.in[{arithmetic_pin_index}]" output="arithmetic.in"/>
                  <direct name="carry_in" input="{bleS}.cin" output="arithmetic.cin">
                    <pack_pattern name="chain" in_port="{bleS}.cin" out_port="arithmetic.cin"/>
                  </direct>
                  <direct name="carry_out" input="arithmetic.cout" output="{bleS}.cout">
                    <pack_pattern name="chain" in_port="arithmetic.cout" out_port="{bleS}.cout"/>
                  </direct>
                  <direct name="direct2" input="{bleS}.clk" output="arithmetic.clk"/>
                  <direct name="direct3" input="arithmetic.out" output="{bleS}.out"/>
                </interconnect>
              </mode>
            </pb_type>
            <interconnect>
              <direct name="direct1" input="{lutSinter}.in[{lutSinter_to_ble_pin_1}]" output="{bleS}[0:0].in"/>
              <direct name="direct2" input="{lutSinter}.in[{lutSinter_to_ble_pin_2}]" output="{bleS}[1:1].in"/>
              <direct name="direct3" input="{bleS}[1:0].out" output="{lutSinter}.out"/>
              <direct name="carry_in" input="{lutSinter}.cin" output="{bleS}[0:0].cin">
                <pack_pattern name="chain" in_port="{lutSinter}.cin" out_port="{bleS}[0:0].cin"/>
              </direct>
              <direct name="carry_out" input="{bleS}[1:1].cout" output="{lutSinter}.cout">
                <pack_pattern name="chain" in_port="{bleS}[1:1].cout" out_port="{lutSinter}.cout"/>
              </direct>
              <direct name="carry_link" input="{bleS}[0:0].cout" output="{bleS}[1:1].cin">
                <pack_pattern name="chain" in_port="{bleS}[0:0].cout" out_port="{bleS}[1:1].cout"/>
              </direct>
              <complete name="complete1" input="{lutSinter}.clk" output="{bleS}[1:0].clk"/>
            </interconnect>
          </pb_type>
          <interconnect>
            <direct name="direct1" input="fle.in" output="{lutSinter}.in"/>
            <direct name="direct2" input="{lutSinter}.out" output="fle.out"/>
            <direct name="direct3" input="fle.clk" output="{lutSinter}.clk"/>
            <direct name="carry_in" input="fle.cin" output="{lutSinter}.cin">
              <pack_pattern name="chain" in_port="fle.cin" out_port="{lutSinter}.cin"/>
            </direct>
            <direct name="carry_out" input="{lutSinter}.cout" output="fle.cout">
              <pack_pattern name="chain" in_port="{lutSinter}.cout" out_port="fle.cout"/>
            </direct>
          </interconnect>
        </mode>
        <!-- n2_lut5 -->
        <mode name="{n1_lutL}" disable_packing="False">
          <pb_type name="{bleL}" num_pb="1">
            <input name="in" num_pins="{num_pins_lutL}"/>
            <output name="out" num_pins="1"/>
            <clock name="clk" num_pins="1"/>
            <pb_type name="{lutL}" blif_model=".names" num_pb="1" class="lut">
              <input name="in" num_pins="{num_pins_lutL}" port_class="lut_in"/>
              <output name="out" num_pins="1" port_class="lut_out"/>
              <!-- LUT timing using delay matrix -->
              <!-- These are the physical delay inputs on a Stratix IV LUT but because VPR cannot do LUT rebalancing,
                       we instead take the average of these numbers to get more stable results
                  82e-12
                  173e-12
                  261e-12
                  263e-12
                  398e-12
                  397e-12
                  -->
              <delay_matrix type="max" in_port="{lutL}.in" out_port="{lutL}.out">
{lutL_delat_mat}
                </delay_matrix>
            </pb_type>
            <pb_type name="ff" blif_model=".latch" num_pb="1" class="flipflop">
              <input name="D" num_pins="1" port_class="D"/>
              <output name="Q" num_pins="1" port_class="Q"/>
              <clock name="clk" num_pins="1" port_class="clock"/>
              <T_setup value="66e-12" port="ff.D" clock="clk"/>
              <T_clock_to_Q max="124e-12" port="ff.Q" clock="clk"/>
            </pb_type>
            <interconnect>
              <direct name="direct1" input="{bleL}.in" output="{lutL}[0:0].in"/>
              <direct name="direct2" input="{lutL}.out" output="ff.D">
                <pack_pattern name="{bleL}" in_port="{lutL}.out" out_port="ff.D"/>
              </direct>
              <direct name="direct3" input="{bleL}.clk" output="ff.clk"/>
              <mux name="mux1" input="ff.Q {lutL}.out" output="{bleL}.out">
                <delay_constant max="25e-12" in_port="{lutL}.out" out_port="{bleL}.out"/>
                <delay_constant max="45e-12" in_port="ff.Q" out_port="{bleL}.out"/>
              </mux>
            </interconnect>
          </pb_type>
          <interconnect>
            <direct name="direct1" input="fle.in[{fle_to_bleL_pin_index}]" output="{bleL}.in"/>
            <direct name="direct2" input="{bleL}.out" output="fle.out[0:0]"/>
            <direct name="direct3" input="fle.clk" output="{bleL}.clk"/>
          </interconnect>
        </mode>
        <!-- {n1_lutL} -->
      </pb_type>
      <interconnect>
        <!-- We use a 50% depop crossbar built using small full xbars to get sets of logically equivalent pins at inputs of CLB 
           The delays below come from Stratix IV. the delay through a connection block
           input mux + the crossbar in Stratix IV is 167 ps. We already have a 72 ps 
           delay on the connection block input mux (modeled by Ian Kuon), so the remaining
           delay within the crossbar is 95 ps. 
           The delays of cluster feedbacks in Stratix IV is 100 ps, when driven by a LUT.
           Since all our outputs LUT outputs go to a BLE output, and have a delay of 
           25 ps to do so, we subtract 25 ps from the 100 ps delay of a feedback
           to get the part that should be marked on the crossbar.	 -->
        <!-- 50% sparsely populated local routing -->
        <complete name="lutA" input="clb.I4 clb.I3 {feedback_xbA}" output="fle[9:0].in[0:0]">
          <delay_constant max="95e-12" in_port="clb.I4" out_port="fle.in[0:0]"/>
          <delay_constant max="95e-12" in_port="clb.I3" out_port="fle.in[0:0]"/>
{delay_constant_xbA}
        </complete>
        <complete name="lutB" input="clb.I3 clb.I2 {feedback_xbB}" output="fle[9:0].in[1:1]">
          <delay_constant max="95e-12" in_port="clb.I3" out_port="fle.in[1:1]"/>
          <delay_constant max="95e-12" in_port="clb.I2" out_port="fle.in[1:1]"/>
{delay_constant_xbB}
        </complete>
        <complete name="lutC" input="clb.I2 clb.I1 {feedback_xbC}" output="fle[9:0].in[2:2]">
          <delay_constant max="95e-12" in_port="clb.I2" out_port="fle.in[2:2]"/>
          <delay_constant max="95e-12" in_port="clb.I1" out_port="fle.in[2:2]"/>
{delay_constant_xbC}
        </complete>
        <complete name="lutD" input="clb.I4 clb.I2 {feedback_xbD}" output="fle[9:0].in[3:3]">
          <delay_constant max="95e-12" in_port="clb.I4" out_port="fle.in[3:3]"/>
          <delay_constant max="95e-12" in_port="clb.I2" out_port="fle.in[3:3]"/>
{delay_constant_xbD}
        </complete>
        <complete name="lutE" input="clb.I3 clb.I1 {feedback_xbE}" output="fle[9:0].in[4:4]">
          <delay_constant max="95e-12" in_port="clb.I3" out_port="fle.in[4:4]"/>
          <delay_constant max="95e-12" in_port="clb.I1" out_port="fle.in[4:4]"/>
{delay_constant_xbE}
        </complete>
        <complete name="lutF" input="clb.I4 clb.I1 {feedback_xbF}" output="fle[9:0].in[5:5]">
          <delay_constant max="95e-12" in_port="clb.I4" out_port="fle.in[5:5]"/>
          <delay_constant max="95e-12" in_port="clb.I1" out_port="fle.in[5:5]"/>
{delay_constant_xbF}
        </complete>
        <complete name="lutG" input="clb.I4 clb.I3 {feedback_xbG}" output="fle[9:0].in[6:6]">
          <delay_constant max="95e-12" in_port="clb.I4" out_port="fle.in[6:6]"/>
          <delay_constant max="95e-12" in_port="clb.I3" out_port="fle.in[6:6]"/>
{delay_constant_xbG}
        </complete>
        <complete name="lutH" input="clb.I3 clb.I2 {feedback_xbH}" output="fle[9:0].in[7:7]">
          <delay_constant max="95e-12" in_port="clb.I3" out_port="fle.in[7:7]"/>
          <delay_constant max="95e-12" in_port="clb.I2" out_port="fle.in[7:7]"/>
{delay_constant_xbH}
        </complete>
        <complete name="clks" input="clb.clk" output="fle[9:0].clk">
          </complete>
        <!-- This way of specifying direct connection to clb outputs is important because this architecture uses automatic spreading of opins.  
                 By grouping to output pins in this fashion, if a logic block is completely filled by 6-LUTs, 
                 then the outputs those 6-LUTs take get evenly distributed across all four sides of the CLB instead of clumped on two sides (which is what happens with a more
                 naive specification).
          -->
        <direct name="clbouts1" input="fle[9:0].out[0:0]" output="clb.O[9:0]"/>
        <direct name="clbouts2" input="fle[9:0].out[1:1]" output="clb.O[19:10]"/>
        <!-- Carry chain links -->
        <direct name="carry_in" input="clb.cin" output="fle[0:0].cin">
          <!-- Put all inter-block carry chain delay on this one edge -->
          <delay_constant max="0.16e-9" in_port="clb.cin" out_port="fle[0:0].cin"/>
          <pack_pattern name="chain" in_port="clb.cin" out_port="fle[0:0].cin"/>
        </direct>
        <direct name="carry_out" input="fle[9:9].cout" output="clb.cout">
          <pack_pattern name="chain" in_port="fle[9:9].cout" out_port="clb.cout"/>
        </direct>
        <direct name="carry_link" input="fle[8:0].cout" output="fle[9:1].cin">
          <pack_pattern name="chain" in_port="fle[8:0].cout" out_port="fle[9:1].cin"/>
        </direct>
      </interconnect>
    </pb_type>
    <!-- Define general purpose logic block (CLB) ends -->
    <!-- Define fracturable multiplier begin -->
    <!-- This multiplier can operate as a 36x36 multiplier that can fracture to two 18x18 multipliers each of which can further fracture to two 9x9 multipliers 
	   For delay modelling, the 36x36 DSP multiplier in Stratix IV has a delay of 1.523 ns + 1.93 ns
	    = 3.45 ns. The 18x18 mode doesn't need to sum four 18x18 multipliers, so it is a bit
	   faster: 1.523 ns for the multiplier, and 1.09 ns for the multiplier output block.
	    For the input and output interconnect delays, unlike Stratix IV, we don't
	   have any routing/logic flexibility (crossbars) at the inputs.  There is some output muxing
	   in Stratix IV and this architecture to select which multiplier outputs should go out (e.g.
	   9x9 outputs, 18x18 or 36x36) so those are very close between the two architectures. 
	   We take the conservative (slightly pessimistic)
           approach modelling the input as the same as the Stratix IV input delay and the output delay the same as the Stratix IV DSP out delay.
		   
	   We estimate block area by using the published Stratix III data (which is architecturally identical to Stratix IV)
	      (H. Wong, V. Betz and J. Rose, "Comparing FPGA vs. Custom CMOS and the Impact on Processor Microarchitecture", FPGA 2011) of 0.2623 
		  mm^2 and scaling from 65 to 40 nm to obtain 0.0993 mm^2. That area is for a DSP block with approximately 2x the functionality of 
		  the block we use (can implement two 36x36 multiplies instead of our 1, eight 18x18 multiplies instead of our 4, etc.). Hence we 
		  divide the area by 2 to obtain 0.0497 mm^2. One minimum-width transistor units = 60 L^2 (where L = 40 nm), so is 518,000 MWTUS. 
		  That area includes routing and the connection block input muxes.  Our DSP block is four 
		  rows high, and hence includes four horizontal routing channel segments and four vertical ones, which is 4x the routing of a logic 
		  block (single tile). It also includes 3.6x the outputs of a logic block, and 1.8x the inputs. Hence a slight overestimate of the routing
		  area associated with our DSP block is four times that of a logic tile, where the routing area of a logic tile was calculated above (at W = 300)
		  as 30481 MWTAs. Hence the (core, non-routing) area our DSP block is approximately 518,000 - 4 * 30,481 = 396,000 MWTUs.
      -->
    <pb_type name="mult_36">
      <input name="a" num_pins="36"/>
      <input name="b" num_pins="36"/>
      <output name="out" num_pins="72"/>
      <mode name="two_divisible_mult_18x18">
        <pb_type name="divisible_mult_18x18" num_pb="2">
          <input name="a" num_pins="18"/>
          <input name="b" num_pins="18"/>
          <output name="out" num_pins="36"/>
          <!-- Model 9x9 delay and 18x18 delay as the same.  9x9 could be faster, but in Stratix IV
	          isn't, presumably because the multiplier layout is really optimized for 18x18.
		      -->
          <mode name="two_mult_9x9">
            <pb_type name="mult_9x9_slice" num_pb="2">
              <input name="A_cfg" num_pins="9"/>
              <input name="B_cfg" num_pins="9"/>
              <output name="OUT_cfg" num_pins="18"/>
              <pb_type name="mult_9x9" blif_model=".subckt multiply" num_pb="1">
                <input name="a" num_pins="9"/>
                <input name="b" num_pins="9"/>
                <output name="out" num_pins="18"/>
                <delay_constant max="1.523e-9" in_port="mult_9x9.a" out_port="mult_9x9.out"/>
                <delay_constant max="1.523e-9" in_port="mult_9x9.b" out_port="mult_9x9.out"/>
              </pb_type>
              <interconnect>
                <direct name="a2a" input="mult_9x9_slice.A_cfg" output="mult_9x9.a">
                </direct>
                <direct name="b2b" input="mult_9x9_slice.B_cfg" output="mult_9x9.b">
                </direct>
                <direct name="out2out" input="mult_9x9.out" output="mult_9x9_slice.OUT_cfg">
                </direct>
              </interconnect>
              <power method="pin-toggle">
                <port name="A_cfg" energy_per_toggle="1.45e-12"/>
                <port name="B_cfg" energy_per_toggle="1.45e-12"/>
                <static_power power_per_instance="0.0"/>
              </power>
            </pb_type>
            <interconnect>
              <direct name="a2a" input="divisible_mult_18x18.a" output="mult_9x9_slice[1:0].A_cfg">
              </direct>
              <direct name="b2b" input="divisible_mult_18x18.b" output="mult_9x9_slice[1:0].B_cfg">
              </direct>
              <direct name="out2out" input="mult_9x9_slice[1:0].OUT_cfg" output="divisible_mult_18x18.out">
              </direct>
            </interconnect>
          </mode>
          <mode name="mult_18x18">
            <pb_type name="mult_18x18_slice" num_pb="1">
              <input name="A_cfg" num_pins="18"/>
              <input name="B_cfg" num_pins="18"/>
              <output name="OUT_cfg" num_pins="36"/>
              <pb_type name="mult_18x18" blif_model=".subckt multiply" num_pb="1">
                <input name="a" num_pins="18"/>
                <input name="b" num_pins="18"/>
                <output name="out" num_pins="36"/>
                <delay_constant max="1.523e-9" in_port="mult_18x18.a" out_port="mult_18x18.out"/>
                <delay_constant max="1.523e-9" in_port="mult_18x18.b" out_port="mult_18x18.out"/>
              </pb_type>
              <interconnect>
                <direct name="a2a" input="mult_18x18_slice.A_cfg" output="mult_18x18.a">
                </direct>
                <direct name="b2b" input="mult_18x18_slice.B_cfg" output="mult_18x18.b">
                </direct>
                <direct name="out2out" input="mult_18x18.out" output="mult_18x18_slice.OUT_cfg">
                </direct>
              </interconnect>
              <power method="pin-toggle">
                <port name="A_cfg" energy_per_toggle="1.09e-12"/>
                <port name="B_cfg" energy_per_toggle="1.09e-12"/>
                <static_power power_per_instance="0.0"/>
              </power>
            </pb_type>
            <interconnect>
              <direct name="a2a" input="divisible_mult_18x18.a" output="mult_18x18_slice.A_cfg">
              </direct>
              <direct name="b2b" input="divisible_mult_18x18.b" output="mult_18x18_slice.B_cfg">
              </direct>
              <direct name="out2out" input="mult_18x18_slice.OUT_cfg" output="divisible_mult_18x18.out">
              </direct>
            </interconnect>
          </mode>
          <power method="sum-of-children"/>
        </pb_type>
        <interconnect>
          <!-- Stratix IV input delay of 207ps is conservative for this architecture because this architecture does not have an input crossbar in the multiplier. 
		   Subtract 72.5 ps delay, which is already in the connection block input mux, leading
              -->
          <direct name="a2a" input="mult_36.a" output="divisible_mult_18x18[1:0].a">
            <delay_constant max="134e-12" in_port="mult_36.a" out_port="divisible_mult_18x18[1:0].a"/>
          </direct>
          <direct name="b2b" input="mult_36.b" output="divisible_mult_18x18[1:0].b">
            <delay_constant max="134e-12" in_port="mult_36.b" out_port="divisible_mult_18x18[1:0].b"/>
          </direct>
          <direct name="out2out" input="divisible_mult_18x18[1:0].out" output="mult_36.out">
            <delay_constant max="1.09e-9" in_port="divisible_mult_18x18[1:0].out" out_port="mult_36.out"/>
          </direct>
        </interconnect>
      </mode>
      <mode name="mult_36x36">
        <pb_type name="mult_36x36_slice" num_pb="1">
          <input name="A_cfg" num_pins="36"/>
          <input name="B_cfg" num_pins="36"/>
          <output name="OUT_cfg" num_pins="72"/>
          <pb_type name="mult_36x36" blif_model=".subckt multiply" num_pb="1">
            <input name="a" num_pins="36"/>
            <input name="b" num_pins="36"/>
            <output name="out" num_pins="72"/>
            <delay_constant max="1.523e-9" in_port="mult_36x36.a" out_port="mult_36x36.out"/>
            <delay_constant max="1.523e-9" in_port="mult_36x36.b" out_port="mult_36x36.out"/>
          </pb_type>
          <interconnect>
            <direct name="a2a" input="mult_36x36_slice.A_cfg" output="mult_36x36.a">
            </direct>
            <direct name="b2b" input="mult_36x36_slice.B_cfg" output="mult_36x36.b">
            </direct>
            <direct name="out2out" input="mult_36x36.out" output="mult_36x36_slice.OUT_cfg">
            </direct>
          </interconnect>
          <power method="pin-toggle">
            <port name="A_cfg" energy_per_toggle="2.13e-12"/>
            <port name="B_cfg" energy_per_toggle="2.13e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <!-- Stratix IV input delay of 207ps is conservative for this architecture because this architecture does not have an input crossbar in the multiplier. 
		   Subtract 72.5 ps delay, which is already in the connection block input mux, leading
		   to a 134 ps delay.
              -->
          <direct name="a2a" input="mult_36.a" output="mult_36x36_slice.A_cfg">
            <delay_constant max="134e-12" in_port="mult_36.a" out_port="mult_36x36_slice.A_cfg"/>
          </direct>
          <direct name="b2b" input="mult_36.b" output="mult_36x36_slice.B_cfg">
            <delay_constant max="134e-12" in_port="mult_36.b" out_port="mult_36x36_slice.B_cfg"/>
          </direct>
          <direct name="out2out" input="mult_36x36_slice.OUT_cfg" output="mult_36.out">
            <delay_constant max="1.93e-9" in_port="mult_36x36_slice.OUT_cfg" out_port="mult_36.out"/>
          </direct>
        </interconnect>
      </mode>
      <!-- Place this multiplier block every 8 columns from (and including) the sixth column -->
      <power method="sum-of-children"/>
    </pb_type>
    <!-- Define fracturable multiplier end -->
    <!-- Define fracturable memory begin -->
    <!-- 32 Kb Memory that can operate from 512x64 to 32Kx1 for single-port mode and 1024x32 to 32Kx1 for dual-port mode.  
           Area and delay based off Stratix IV 9K and 144K memories (delay from linear interpolation, Tsu(483 ps, 636 ps) Tco(1084ps, 1969ps)).  
           Input delay = 204ps (from Stratix IV LAB line) - 72ps (this architecture does not lump connection box delay in internal delay)
           Output delay = M9K buffer 50ps
		   
		   Area is obtained by appropriately scaling and adjusting the published Stratix III (which is architecturally identical to Stratix IV)
		   data from H. Wong, V. Betz and J. Rose, "Comparing FPGA vs. Custom CMOS and the Impact on Processor Microarchitecture", FPGA 2011.
		   Linearly interpolating (by bit count) between the M9k and M144k areas to obtain an M32k (our RAM size) point yields a 65 nm area of
		   of 0.153 mm^2. Interpolating based on port count between the RAMs would instead yield an area of 0.209 mm^2 for our 32 kB RAM; since 
		   bit count accounts for more area than ports for a RAM this size we choose the bit count interpolation; however, since the port interpolation
		   is not radically different this also gives us confidence that interpolating based on bits is OK, but slightly underpredicts area.
		   Scaling to 40 nm^2 yields .0579 mm^2, and converting to MWTUs at 60 L^2 / MWTU yields 604,000 MWTUs. This includes routing. A Stratix IV
		   M9K RAM is one row high and hence has one routing tile (one horizonal and one vertical routing segment area). An M144k RAM has 8 such tiles.
		   Linearly interpolating on
		   bits to 32 kb yields 2.2 routing tiles incorporated in the area number above. The inter-block routing represents 30% of the area of a logic 
		   tile according to D. Lewis et al, "Architectural Enhancements in Stratix V," FPGA 2013. Hence we should subtract 0.3 * 2.2 * 84,375 MWTUs to
		   obtain a RAM core area (not including inter-block routing) of 548,000 MWTU areas for our 32 kb RAM in a 40 nm process.
      -->
    <pb_type name="memory">
      <input name="addr1" num_pins="15"/>
      <input name="addr2" num_pins="15"/>
      <input name="data" num_pins="64"/>
      <input name="we1" num_pins="1"/>
      <input name="we2" num_pins="1"/>
      <output name="out" num_pins="64"/>
      <clock name="clk" num_pins="1"/>
      <!-- Specify single port mode first -->
      <mode name="mem_512x64_sp">
        <pb_type name="mem_512x64_sp" blif_model=".subckt single_port_ram" class="memory" num_pb="1">
          <input name="addr" num_pins="9" port_class="address"/>
          <input name="data" num_pins="64" port_class="data_in"/>
          <input name="we" num_pins="1" port_class="write_en"/>
          <output name="out" num_pins="64" port_class="data_out"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_512x64_sp.addr" clock="clk"/>
          <T_setup value="509e-12" port="mem_512x64_sp.data" clock="clk"/>
          <T_setup value="509e-12" port="mem_512x64_sp.we" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_512x64_sp.out" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="9.0e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[8:0]" output="mem_512x64_sp.addr">
            <delay_constant max="132e-12" in_port="memory.addr1[8:0]" out_port="mem_512x64_sp.addr"/>
          </direct>
          <direct name="data1" input="memory.data[63:0]" output="mem_512x64_sp.data">
            <delay_constant max="132e-12" in_port="memory.data[63:0]" out_port="mem_512x64_sp.data"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_512x64_sp.we">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_512x64_sp.we"/>
          </direct>
          <direct name="dataout1" input="mem_512x64_sp.out" output="memory.out[63:0]">
            <delay_constant max="40e-12" in_port="mem_512x64_sp.out" out_port="memory.out[63:0]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_512x64_sp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_1024x32_sp">
        <pb_type name="mem_1024x32_sp" blif_model=".subckt single_port_ram" class="memory" num_pb="1">
          <input name="addr" num_pins="10" port_class="address"/>
          <input name="data" num_pins="32" port_class="data_in"/>
          <input name="we" num_pins="1" port_class="write_en"/>
          <output name="out" num_pins="32" port_class="data_out"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_1024x32_sp.addr" clock="clk"/>
          <T_setup value="509e-12" port="mem_1024x32_sp.data" clock="clk"/>
          <T_setup value="509e-12" port="mem_1024x32_sp.we" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_1024x32_sp.out" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="9.0e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[9:0]" output="mem_1024x32_sp.addr">
            <delay_constant max="132e-12" in_port="memory.addr1[9:0]" out_port="mem_1024x32_sp.addr"/>
          </direct>
          <direct name="data1" input="memory.data[31:0]" output="mem_1024x32_sp.data">
            <delay_constant max="132e-12" in_port="memory.data[31:0]" out_port="mem_1024x32_sp.data"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_1024x32_sp.we">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_1024x32_sp.we"/>
          </direct>
          <direct name="dataout1" input="mem_1024x32_sp.out" output="memory.out[31:0]">
            <delay_constant max="40e-12" in_port="mem_1024x32_sp.out" out_port="memory.out[31:0]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_1024x32_sp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_2048x16_sp">
        <pb_type name="mem_2048x16_sp" blif_model=".subckt single_port_ram" class="memory" num_pb="1">
          <input name="addr" num_pins="11" port_class="address"/>
          <input name="data" num_pins="16" port_class="data_in"/>
          <input name="we" num_pins="1" port_class="write_en"/>
          <output name="out" num_pins="16" port_class="data_out"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_2048x16_sp.addr" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x16_sp.data" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x16_sp.we" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_2048x16_sp.out" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="9.0e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[10:0]" output="mem_2048x16_sp.addr">
            <delay_constant max="132e-12" in_port="memory.addr1[10:0]" out_port="mem_2048x16_sp.addr"/>
          </direct>
          <direct name="data1" input="memory.data[15:0]" output="mem_2048x16_sp.data">
            <delay_constant max="132e-12" in_port="memory.data[15:0]" out_port="mem_2048x16_sp.data"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_2048x16_sp.we">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_2048x16_sp.we"/>
          </direct>
          <direct name="dataout1" input="mem_2048x16_sp.out" output="memory.out[15:0]">
            <delay_constant max="40e-12" in_port="mem_2048x16_sp.out" out_port="memory.out[15:0]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_2048x16_sp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_4096x8_sp">
        <pb_type name="mem_4096x8_sp" blif_model=".subckt single_port_ram" class="memory" num_pb="1">
          <input name="addr" num_pins="12" port_class="address"/>
          <input name="data" num_pins="8" port_class="data_in"/>
          <input name="we" num_pins="1" port_class="write_en"/>
          <output name="out" num_pins="8" port_class="data_out"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_4096x8_sp.addr" clock="clk"/>
          <T_setup value="509e-12" port="mem_4096x8_sp.data" clock="clk"/>
          <T_setup value="509e-12" port="mem_4096x8_sp.we" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_4096x8_sp.out" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="9.0e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[11:0]" output="mem_4096x8_sp.addr">
            <delay_constant max="132e-12" in_port="memory.addr1[11:0]" out_port="mem_4096x8_sp.addr"/>
          </direct>
          <direct name="data1" input="memory.data[7:0]" output="mem_4096x8_sp.data">
            <delay_constant max="132e-12" in_port="memory.data[7:0]" out_port="mem_4096x8_sp.data"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_4096x8_sp.we">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_4096x8_sp.we"/>
          </direct>
          <direct name="dataout1" input="mem_4096x8_sp.out" output="memory.out[7:0]">
            <delay_constant max="40e-12" in_port="mem_4096x8_sp.out" out_port="memory.out[7:0]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_4096x8_sp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_8192x4_sp">
        <pb_type name="mem_8192x4_sp" blif_model=".subckt single_port_ram" class="memory" num_pb="1">
          <input name="addr" num_pins="13" port_class="address"/>
          <input name="data" num_pins="4" port_class="data_in"/>
          <input name="we" num_pins="1" port_class="write_en"/>
          <output name="out" num_pins="4" port_class="data_out"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_8192x4_sp.addr" clock="clk"/>
          <T_setup value="509e-12" port="mem_8192x4_sp.data" clock="clk"/>
          <T_setup value="509e-12" port="mem_8192x4_sp.we" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_8192x4_sp.out" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="9.0e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[12:0]" output="mem_8192x4_sp.addr">
            <delay_constant max="132e-12" in_port="memory.addr1[12:0]" out_port="mem_8192x4_sp.addr"/>
          </direct>
          <direct name="data1" input="memory.data[3:0]" output="mem_8192x4_sp.data">
            <delay_constant max="132e-12" in_port="memory.data[3:0]" out_port="mem_8192x4_sp.data"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_8192x4_sp.we">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_8192x4_sp.we"/>
          </direct>
          <direct name="dataout1" input="mem_8192x4_sp.out" output="memory.out[3:0]">
            <delay_constant max="40e-12" in_port="mem_8192x4_sp.out" out_port="memory.out[3:0]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_8192x4_sp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_16384x2_sp">
        <pb_type name="mem_16384x2_sp" blif_model=".subckt single_port_ram" class="memory" num_pb="1">
          <input name="addr" num_pins="14" port_class="address"/>
          <input name="data" num_pins="2" port_class="data_in"/>
          <input name="we" num_pins="1" port_class="write_en"/>
          <output name="out" num_pins="2" port_class="data_out"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_16384x2_sp.addr" clock="clk"/>
          <T_setup value="509e-12" port="mem_16384x2_sp.data" clock="clk"/>
          <T_setup value="509e-12" port="mem_16384x2_sp.we" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_16384x2_sp.out" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="9.0e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[13:0]" output="mem_16384x2_sp.addr">
            <delay_constant max="132e-12" in_port="memory.addr1[13:0]" out_port="mem_16384x2_sp.addr"/>
          </direct>
          <direct name="data1" input="memory.data[1:0]" output="mem_16384x2_sp.data">
            <delay_constant max="132e-12" in_port="memory.data[1:0]" out_port="mem_16384x2_sp.data"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_16384x2_sp.we">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_16384x2_sp.we"/>
          </direct>
          <direct name="dataout1" input="mem_16384x2_sp.out" output="memory.out[1:0]">
            <delay_constant max="40e-12" in_port="mem_16384x2_sp.out" out_port="memory.out[1:0]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_16384x2_sp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_32768x1_sp">
        <pb_type name="mem_32768x1_sp" blif_model=".subckt single_port_ram" class="memory" num_pb="1">
          <input name="addr" num_pins="15" port_class="address"/>
          <input name="data" num_pins="1" port_class="data_in"/>
          <input name="we" num_pins="1" port_class="write_en"/>
          <output name="out" num_pins="1" port_class="data_out"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_32768x1_sp.addr" clock="clk"/>
          <T_setup value="509e-12" port="mem_32768x1_sp.data" clock="clk"/>
          <T_setup value="509e-12" port="mem_32768x1_sp.we" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_32768x1_sp.out" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="9.0e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[14:0]" output="mem_32768x1_sp.addr">
            <delay_constant max="132e-12" in_port="memory.addr1[14:0]" out_port="mem_32768x1_sp.addr"/>
          </direct>
          <direct name="data1" input="memory.data[0:0]" output="mem_32768x1_sp.data">
            <delay_constant max="132e-12" in_port="memory.data[0:0]" out_port="mem_32768x1_sp.data"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_32768x1_sp.we">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_32768x1_sp.we"/>
          </direct>
          <direct name="dataout1" input="mem_32768x1_sp.out" output="memory.out[0:0]">
            <delay_constant max="40e-12" in_port="mem_32768x1_sp.out" out_port="memory.out[0:0]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_32768x1_sp.clk">
          </direct>
        </interconnect>
      </mode>
      <!-- Specify true dual port mode next -->
      <mode name="mem_1024x32_dp">
        <pb_type name="mem_1024x32_dp" blif_model=".subckt dual_port_ram" class="memory" num_pb="1">
          <input name="addr1" num_pins="10" port_class="address1"/>
          <input name="addr2" num_pins="10" port_class="address2"/>
          <input name="data1" num_pins="32" port_class="data_in1"/>
          <input name="data2" num_pins="32" port_class="data_in2"/>
          <input name="we1" num_pins="1" port_class="write_en1"/>
          <input name="we2" num_pins="1" port_class="write_en2"/>
          <output name="out1" num_pins="32" port_class="data_out1"/>
          <output name="out2" num_pins="32" port_class="data_out2"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_1024x32_dp.addr1" clock="clk"/>
          <T_setup value="509e-12" port="mem_1024x32_dp.data1" clock="clk"/>
          <T_setup value="509e-12" port="mem_1024x32_dp.we1" clock="clk"/>
          <T_setup value="509e-12" port="mem_1024x32_dp.addr2" clock="clk"/>
          <T_setup value="509e-12" port="mem_1024x32_dp.data2" clock="clk"/>
          <T_setup value="509e-12" port="mem_1024x32_dp.we2" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_1024x32_dp.out1" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_1024x32_dp.out2" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="17.9e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[9:0]" output="mem_1024x32_dp.addr1">
            <delay_constant max="132e-12" in_port="memory.addr1[9:0]" out_port="mem_1024x32_dp.addr1"/>
          </direct>
          <direct name="address2" input="memory.addr2[9:0]" output="mem_1024x32_dp.addr2">
            <delay_constant max="132e-12" in_port="memory.addr2[9:0]" out_port="mem_1024x32_dp.addr2"/>
          </direct>
          <direct name="data1" input="memory.data[31:0]" output="mem_1024x32_dp.data1">
            <delay_constant max="132e-12" in_port="memory.data[31:0]" out_port="mem_1024x32_dp.data1"/>
          </direct>
          <direct name="data2" input="memory.data[63:32]" output="mem_1024x32_dp.data2">
            <delay_constant max="132e-12" in_port="memory.data[63:32]" out_port="mem_1024x32_dp.data2"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_1024x32_dp.we1">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_1024x32_dp.we1"/>
          </direct>
          <direct name="writeen2" input="memory.we2" output="mem_1024x32_dp.we2">
            <delay_constant max="132e-12" in_port="memory.we2" out_port="mem_1024x32_dp.we2"/>
          </direct>
          <direct name="dataout1" input="mem_1024x32_dp.out1" output="memory.out[31:0]">
            <delay_constant max="40e-12" in_port="mem_1024x32_dp.out1" out_port="memory.out[31:0]"/>
          </direct>
          <direct name="dataout2" input="mem_1024x32_dp.out2" output="memory.out[63:32]">
            <delay_constant max="40e-12" in_port="mem_1024x32_dp.out2" out_port="memory.out[63:32]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_1024x32_dp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_2048x16_dp">
        <pb_type name="mem_2048x16_dp" blif_model=".subckt dual_port_ram" class="memory" num_pb="1">
          <input name="addr1" num_pins="11" port_class="address1"/>
          <input name="addr2" num_pins="11" port_class="address2"/>
          <input name="data1" num_pins="16" port_class="data_in1"/>
          <input name="data2" num_pins="16" port_class="data_in2"/>
          <input name="we1" num_pins="1" port_class="write_en1"/>
          <input name="we2" num_pins="1" port_class="write_en2"/>
          <output name="out1" num_pins="16" port_class="data_out1"/>
          <output name="out2" num_pins="16" port_class="data_out2"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_2048x16_dp.addr1" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x16_dp.data1" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x16_dp.we1" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x16_dp.addr2" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x16_dp.data2" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x16_dp.we2" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_2048x16_dp.out1" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_2048x16_dp.out2" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="17.9e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[10:0]" output="mem_2048x16_dp.addr1">
            <delay_constant max="132e-12" in_port="memory.addr1[10:0]" out_port="mem_2048x16_dp.addr1"/>
          </direct>
          <direct name="address2" input="memory.addr2[10:0]" output="mem_2048x16_dp.addr2">
            <delay_constant max="132e-12" in_port="memory.addr2[10:0]" out_port="mem_2048x16_dp.addr2"/>
          </direct>
          <direct name="data1" input="memory.data[15:0]" output="mem_2048x16_dp.data1">
            <delay_constant max="132e-12" in_port="memory.data[15:0]" out_port="mem_2048x16_dp.data1"/>
          </direct>
          <direct name="data2" input="memory.data[31:16]" output="mem_2048x16_dp.data2">
            <delay_constant max="132e-12" in_port="memory.data[31:16]" out_port="mem_2048x16_dp.data2"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_2048x16_dp.we1">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_2048x16_dp.we1"/>
          </direct>
          <direct name="writeen2" input="memory.we2" output="mem_2048x16_dp.we2">
            <delay_constant max="132e-12" in_port="memory.we2" out_port="mem_2048x16_dp.we2"/>
          </direct>
          <direct name="dataout1" input="mem_2048x16_dp.out1" output="memory.out[15:0]">
            <delay_constant max="40e-12" in_port="mem_2048x16_dp.out1" out_port="memory.out[15:0]"/>
          </direct>
          <direct name="dataout2" input="mem_2048x16_dp.out2" output="memory.out[31:16]">
            <delay_constant max="40e-12" in_port="mem_2048x16_dp.out2" out_port="memory.out[31:16]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_2048x16_dp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_2048x8_dp">
        <pb_type name="mem_2048x8_dp" blif_model=".subckt dual_port_ram" class="memory" num_pb="1">
          <input name="addr1" num_pins="12" port_class="address1"/>
          <input name="addr2" num_pins="12" port_class="address2"/>
          <input name="data1" num_pins="8" port_class="data_in1"/>
          <input name="data2" num_pins="8" port_class="data_in2"/>
          <input name="we1" num_pins="1" port_class="write_en1"/>
          <input name="we2" num_pins="1" port_class="write_en2"/>
          <output name="out1" num_pins="8" port_class="data_out1"/>
          <output name="out2" num_pins="8" port_class="data_out2"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_2048x8_dp.addr1" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x8_dp.data1" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x8_dp.we1" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x8_dp.addr2" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x8_dp.data2" clock="clk"/>
          <T_setup value="509e-12" port="mem_2048x8_dp.we2" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_2048x8_dp.out1" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_2048x8_dp.out2" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="17.9e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[11:0]" output="mem_2048x8_dp.addr1">
            <delay_constant max="132e-12" in_port="memory.addr1[11:0]" out_port="mem_2048x8_dp.addr1"/>
          </direct>
          <direct name="address2" input="memory.addr2[11:0]" output="mem_2048x8_dp.addr2">
            <delay_constant max="132e-12" in_port="memory.addr2[11:0]" out_port="mem_2048x8_dp.addr2"/>
          </direct>
          <direct name="data1" input="memory.data[7:0]" output="mem_2048x8_dp.data1">
            <delay_constant max="132e-12" in_port="memory.data[7:0]" out_port="mem_2048x8_dp.data1"/>
          </direct>
          <direct name="data2" input="memory.data[15:8]" output="mem_2048x8_dp.data2">
            <delay_constant max="132e-12" in_port="memory.data[15:8]" out_port="mem_2048x8_dp.data2"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_2048x8_dp.we1">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_2048x8_dp.we1"/>
          </direct>
          <direct name="writeen2" input="memory.we2" output="mem_2048x8_dp.we2">
            <delay_constant max="132e-12" in_port="memory.we2" out_port="mem_2048x8_dp.we2"/>
          </direct>
          <direct name="dataout1" input="mem_2048x8_dp.out1" output="memory.out[7:0]">
            <delay_constant max="40e-12" in_port="mem_2048x8_dp.out1" out_port="memory.out[7:0]"/>
          </direct>
          <direct name="dataout2" input="mem_2048x8_dp.out2" output="memory.out[15:8]">
            <delay_constant max="40e-12" in_port="mem_2048x8_dp.out2" out_port="memory.out[15:8]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_2048x8_dp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_8192x4_dp">
        <pb_type name="mem_8192x4_dp" blif_model=".subckt dual_port_ram" class="memory" num_pb="1">
          <input name="addr1" num_pins="13" port_class="address1"/>
          <input name="addr2" num_pins="13" port_class="address2"/>
          <input name="data1" num_pins="4" port_class="data_in1"/>
          <input name="data2" num_pins="4" port_class="data_in2"/>
          <input name="we1" num_pins="1" port_class="write_en1"/>
          <input name="we2" num_pins="1" port_class="write_en2"/>
          <output name="out1" num_pins="4" port_class="data_out1"/>
          <output name="out2" num_pins="4" port_class="data_out2"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_8192x4_dp.addr1" clock="clk"/>
          <T_setup value="509e-12" port="mem_8192x4_dp.data1" clock="clk"/>
          <T_setup value="509e-12" port="mem_8192x4_dp.we1" clock="clk"/>
          <T_setup value="509e-12" port="mem_8192x4_dp.addr2" clock="clk"/>
          <T_setup value="509e-12" port="mem_8192x4_dp.data2" clock="clk"/>
          <T_setup value="509e-12" port="mem_8192x4_dp.we2" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_8192x4_dp.out1" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_8192x4_dp.out2" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="17.9e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[12:0]" output="mem_8192x4_dp.addr1">
            <delay_constant max="132e-12" in_port="memory.addr1[12:0]" out_port="mem_8192x4_dp.addr1"/>
          </direct>
          <direct name="address2" input="memory.addr2[12:0]" output="mem_8192x4_dp.addr2">
            <delay_constant max="132e-12" in_port="memory.addr2[12:0]" out_port="mem_8192x4_dp.addr2"/>
          </direct>
          <direct name="data1" input="memory.data[3:0]" output="mem_8192x4_dp.data1">
            <delay_constant max="132e-12" in_port="memory.data[3:0]" out_port="mem_8192x4_dp.data1"/>
          </direct>
          <direct name="data2" input="memory.data[7:4]" output="mem_8192x4_dp.data2">
            <delay_constant max="132e-12" in_port="memory.data[7:4]" out_port="mem_8192x4_dp.data2"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_8192x4_dp.we1">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_8192x4_dp.we1"/>
          </direct>
          <direct name="writeen2" input="memory.we2" output="mem_8192x4_dp.we2">
            <delay_constant max="132e-12" in_port="memory.we2" out_port="mem_8192x4_dp.we2"/>
          </direct>
          <direct name="dataout1" input="mem_8192x4_dp.out1" output="memory.out[3:0]">
            <delay_constant max="40e-12" in_port="mem_8192x4_dp.out1" out_port="memory.out[3:0]"/>
          </direct>
          <direct name="dataout2" input="mem_8192x4_dp.out2" output="memory.out[7:4]">
            <delay_constant max="40e-12" in_port="mem_8192x4_dp.out2" out_port="memory.out[7:4]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_8192x4_dp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_16384x2_dp">
        <pb_type name="mem_16384x2_dp" blif_model=".subckt dual_port_ram" class="memory" num_pb="1">
          <input name="addr1" num_pins="14" port_class="address1"/>
          <input name="addr2" num_pins="14" port_class="address2"/>
          <input name="data1" num_pins="2" port_class="data_in1"/>
          <input name="data2" num_pins="2" port_class="data_in2"/>
          <input name="we1" num_pins="1" port_class="write_en1"/>
          <input name="we2" num_pins="1" port_class="write_en2"/>
          <output name="out1" num_pins="2" port_class="data_out1"/>
          <output name="out2" num_pins="2" port_class="data_out2"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_16384x2_dp.addr1" clock="clk"/>
          <T_setup value="509e-12" port="mem_16384x2_dp.data1" clock="clk"/>
          <T_setup value="509e-12" port="mem_16384x2_dp.we1" clock="clk"/>
          <T_setup value="509e-12" port="mem_16384x2_dp.addr2" clock="clk"/>
          <T_setup value="509e-12" port="mem_16384x2_dp.data2" clock="clk"/>
          <T_setup value="509e-12" port="mem_16384x2_dp.we2" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_16384x2_dp.out1" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_16384x2_dp.out2" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="17.9e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[13:0]" output="mem_16384x2_dp.addr1">
            <delay_constant max="132e-12" in_port="memory.addr1[13:0]" out_port="mem_16384x2_dp.addr1"/>
          </direct>
          <direct name="address2" input="memory.addr2[13:0]" output="mem_16384x2_dp.addr2">
            <delay_constant max="132e-12" in_port="memory.addr2[13:0]" out_port="mem_16384x2_dp.addr2"/>
          </direct>
          <direct name="data1" input="memory.data[1:0]" output="mem_16384x2_dp.data1">
            <delay_constant max="132e-12" in_port="memory.data[1:0]" out_port="mem_16384x2_dp.data1"/>
          </direct>
          <direct name="data2" input="memory.data[3:2]" output="mem_16384x2_dp.data2">
            <delay_constant max="132e-12" in_port="memory.data[3:2]" out_port="mem_16384x2_dp.data2"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_16384x2_dp.we1">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_16384x2_dp.we1"/>
          </direct>
          <direct name="writeen2" input="memory.we2" output="mem_16384x2_dp.we2">
            <delay_constant max="132e-12" in_port="memory.we2" out_port="mem_16384x2_dp.we2"/>
          </direct>
          <direct name="dataout1" input="mem_16384x2_dp.out1" output="memory.out[1:0]">
            <delay_constant max="40e-12" in_port="mem_16384x2_dp.out1" out_port="memory.out[1:0]"/>
          </direct>
          <direct name="dataout2" input="mem_16384x2_dp.out2" output="memory.out[3:2]">
            <delay_constant max="40e-12" in_port="mem_16384x2_dp.out2" out_port="memory.out[3:2]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_16384x2_dp.clk">
          </direct>
        </interconnect>
      </mode>
      <mode name="mem_32768x1_dp">
        <pb_type name="mem_32768x1_dp" blif_model=".subckt dual_port_ram" class="memory" num_pb="1">
          <input name="addr1" num_pins="15" port_class="address1"/>
          <input name="addr2" num_pins="15" port_class="address2"/>
          <input name="data1" num_pins="1" port_class="data_in1"/>
          <input name="data2" num_pins="1" port_class="data_in2"/>
          <input name="we1" num_pins="1" port_class="write_en1"/>
          <input name="we2" num_pins="1" port_class="write_en2"/>
          <output name="out1" num_pins="1" port_class="data_out1"/>
          <output name="out2" num_pins="1" port_class="data_out2"/>
          <clock name="clk" num_pins="1" port_class="clock"/>
          <T_setup value="509e-12" port="mem_32768x1_dp.addr1" clock="clk"/>
          <T_setup value="509e-12" port="mem_32768x1_dp.data1" clock="clk"/>
          <T_setup value="509e-12" port="mem_32768x1_dp.we1" clock="clk"/>
          <T_setup value="509e-12" port="mem_32768x1_dp.addr2" clock="clk"/>
          <T_setup value="509e-12" port="mem_32768x1_dp.data2" clock="clk"/>
          <T_setup value="509e-12" port="mem_32768x1_dp.we2" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_32768x1_dp.out1" clock="clk"/>
          <T_clock_to_Q max="1.234e-9" port="mem_32768x1_dp.out2" clock="clk"/>
          <power method="pin-toggle">
            <port name="clk" energy_per_toggle="17.9e-12"/>
            <static_power power_per_instance="0.0"/>
          </power>
        </pb_type>
        <interconnect>
          <direct name="address1" input="memory.addr1[14:0]" output="mem_32768x1_dp.addr1">
            <delay_constant max="132e-12" in_port="memory.addr1[14:0]" out_port="mem_32768x1_dp.addr1"/>
          </direct>
          <direct name="address2" input="memory.addr2[14:0]" output="mem_32768x1_dp.addr2">
            <delay_constant max="132e-12" in_port="memory.addr2[14:0]" out_port="mem_32768x1_dp.addr2"/>
          </direct>
          <direct name="data1" input="memory.data[0:0]" output="mem_32768x1_dp.data1">
            <delay_constant max="132e-12" in_port="memory.data[0:0]" out_port="mem_32768x1_dp.data1"/>
          </direct>
          <direct name="data2" input="memory.data[1:1]" output="mem_32768x1_dp.data2">
            <delay_constant max="132e-12" in_port="memory.data[1:1]" out_port="mem_32768x1_dp.data2"/>
          </direct>
          <direct name="writeen1" input="memory.we1" output="mem_32768x1_dp.we1">
            <delay_constant max="132e-12" in_port="memory.we1" out_port="mem_32768x1_dp.we1"/>
          </direct>
          <direct name="writeen2" input="memory.we2" output="mem_32768x1_dp.we2">
            <delay_constant max="132e-12" in_port="memory.we2" out_port="mem_32768x1_dp.we2"/>
          </direct>
          <direct name="dataout1" input="mem_32768x1_dp.out1" output="memory.out[0:0]">
            <delay_constant max="40e-12" in_port="mem_32768x1_dp.out1" out_port="memory.out[0:0]"/>
          </direct>
          <direct name="dataout2" input="mem_32768x1_dp.out2" output="memory.out[1:1]">
            <delay_constant max="40e-12" in_port="mem_32768x1_dp.out2" out_port="memory.out[1:1]"/>
          </direct>
          <direct name="clk" input="memory.clk" output="mem_32768x1_dp.clk">
          </direct>
        </interconnect>
      </mode>
      <!-- Every input pin is driven by 15% of the tracks in a channel, every output pin is driven by 10% of the tracks in a channel -->
      <!-- Place this memory block every 8 columns from (and including) the second column -->
      <power method="sum-of-children"/>
    </pb_type>
    <!-- Define fracturable memory end -->
  </complexblocklist>
  <power>
    <local_interconnect C_wire="2.5e-10"/>
    <mux_transistor_size mux_transistor_size="3"/>
    <FF_size FF_size="4"/>
    <LUT_transistor_size LUT_transistor_size="4"/>
  </power>
  <clocks>
    <clock buffer_size="auto" C_wire="2.5e-10"/>
  </clocks>
</architecture>
'''


def distribute_pins(total_pins, pins_per_group, group_num):
    all_combinations = list(combinations(range(total_pins), pins_per_group))

    # If the number of all possible combinations is less than group_num, return all of them
    if len(all_combinations) <= group_num:
        return all_combinations

    # Initialize a list to hold the final groups
    final_groups = []

    # Initialize a counter to keep track of how many times each pin has been used
    pin_usage = Counter()

    # While we haven't yet created the desired number of groups
    while len(final_groups) < group_num:
        # Find the pin that has been used the least
        least_used_pin = min(pin_usage, key=lambda pin: (pin_usage[pin], pin), default=0)

        # Initialize a variable to keep track of the best group so far
        best_group = None
        best_group_usage = float('inf')

        # For each possible combination
        for combination in all_combinations:
            # If this combination contains the least used pin
            if least_used_pin in combination:
                # Calculate the total usage of this combination
                group_usage = sum(pin_usage[pin] for pin in combination)
                # If this combination is better than the best so far, update the best so far
                if group_usage < best_group_usage:
                    best_group = combination
                    best_group_usage = group_usage

        # Add the best group to the final groups
        final_groups.append(list(best_group))
        # Update the pin usage counter
        pin_usage.update(best_group)
        # Remove the used combination from the list of all combinations
        all_combinations.remove(best_group)

    return final_groups

"""
configurable parameters, all integer
*CLB_pins_per_group = 13
*num_feedback_ble = 5
*lut_size = 6
- lut_size_small = lut_size - 1
- lut_size_large = lut_size
*adder size is not supported yet

# create xml parameters
"""
def generate_arch(CLB_pins_per_group: int, num_feedback_ble: int, lut_size: int) -> str:
    config_dict = {}
    lut_size_small = lut_size - 1
    lut_size_large = lut_size

    # CLB input
    config_dict['num_pins_I1'] = CLB_pins_per_group
    config_dict['num_pins_I2'] = CLB_pins_per_group
    config_dict['num_pins_I3'] = CLB_pins_per_group
    config_dict['num_pins_I4'] = CLB_pins_per_group
    # small lut
    config_dict['n2_lutS'] = 'n2_lut' + str(lut_size_small)
    config_dict['lutSinter'] = 'lut' + str(lut_size_small) + 'inter'
    config_dict['bleS'] = 'ble' + str(lut_size_small)
    config_dict['num_pins_lutS'] = lut_size_small
    config_dict['flutS'] = 'flut' + str(lut_size_small)
    config_dict['lutS'] = 'lut' + str(lut_size_small)
    config_dict['blutS'] = 'blut' + str(lut_size_small)
    config_dict['lutS_delat_mat'] = '\n'.join(['235e-12'] * lut_size_small)
    config_dict['lutSinter_to_ble_pin_1'] = str(lut_size_small-1) + ':0'
    config_dict['lutSinter_to_ble_pin_2'] = '7:' + str(8-lut_size_small)
    # arithmetic

    config_dict['arithmetic_num_pins'] = str(min(4, lut_size_small))
    config_dict['arithmetic_pin_index'] = str(min(4, lut_size_small)-1) + ':0'
    config_dict['arith_lut_delat_mat'] = '\n'.join(['195e-12'] * min(4, lut_size_small))

    # large lut
    config_dict['n1_lutL'] = 'n1_lut' + str(lut_size_large)
    config_dict['bleL'] = 'ble' + str(lut_size_large)
    config_dict['num_pins_lutL'] = lut_size_large
    config_dict['lutL'] = 'lut' + str(lut_size_large)
    config_dict['lutL_delat_mat'] = '\n'.join(['261e-12'] * lut_size_large)
    config_dict['fle_to_bleL_pin_index'] = str(lut_size_large-1) + ':0'
    # feedback
    index_ = 'ABCDEFGH'
    feedback_group_pin_index = distribute_pins(10, num_feedback_ble, 8)
    for i in range(8):
        config_dict[f'feedback_xb{index_[i]}'] = ' '.join([f'fle[{x}:{x}].out' for x in feedback_group_pin_index[i]])
        config_dict[f'delay_constant_xb{index_[i]}'] = '\n'.join([f'<delay_constant max="75e-12" in_port="fle[{x}:{x}].out" out_port="fle.in[{i}:{i}]"/>' for x in feedback_group_pin_index[i]])

    out = TEMPLATE.format(**config_dict)
    return out


# Specify the parameters and their default values for this architecture here.
DEFAULTS = {
    'CLB_pins_per_group': 13,
    'num_feedback_ble': 5,
    'lut_size': 6
}

class BaseArchFactory(ArchFactory, ParamsChecker):
    """
    Baseline FPGA as specified in the Kratos paper.
    Has a Stratix-IV-like architecture using 40 nm technology.
    """

    def verify_params(self, params: dict[str, any]) -> dict[str, any]:
      return self.autofill_defaults(DEFAULTS, params)
    
    def get_name(self, CLB_pins_per_group: int, num_feedback_ble: int, lut_size: int, **kwargs) -> str:
      return f"clb.{CLB_pins_per_group}_ble.{num_feedback_ble}_lut.{lut_size}"

    def get_arch(self, **kwargs) -> str:
      """
      Concrete implementation of ArchFactory for Baseline FPGA.
      Required arguments as per DEFAULTS.
      """
      return generate_arch(**kwargs)
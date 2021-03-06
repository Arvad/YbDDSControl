
library ieee;
use ieee.std_logic_1164.all;
--USE ieee.std_logic_arith.all;
use ieee.numeric_std.all;
USE work.all;

entity DDS_RIKEN is
  port(
    clk_dds : in std_logic; -- clock in from DDS divided clock
	 clk_in0: in std_logic; --clock in from local oscillator of 25 MHz

    -- LED driver ---
	 LED_CLK: OUT STD_LOGIC;
	 LED_SDI: OUT STD_LOGIC_VECTOR (0 DOWNTO 0);
	 LED_LE: OUT STD_LOGIC;
	 LED_OE: OUT STD_LOGIC;
	 
	 -- DDS comminucation port --
	 dds_port: out std_logic_vector (31 downto 0);
	 dds_master_reset: out std_logic;
	 dds_osk: out std_logic;
	 dds_io_update: out std_logic;
	 dds_drover: in std_logic;
	 dds_drhold: out std_logic;
	 dds_drctl: out std_logic;
	 
	 -- function pins for dds --
	 f_pin: out std_logic_vector (3 downto 0);
	 --profile select pins--
	 ps: out std_logic_vector (2 downto 0);
	 
	 -- pulser bus --
	 dds_bus_in: in std_LOGIC_vector(31 downto 0);
	 dds_bus_out: out std_LOGIC_vector(7 downto 0);
	 tx_enable: out std_LOGIC_vector(1 downto 0);
	 
	 
	 -- DAC control pin --
	 
	 dac_out : out std_LOGIC_VECTOR (13 downto 0);
	 dac_wr_pin: out std_logic;
	 
	 -- external trigger --
	 
	 external_trigger : in std_logic;
	 
	 
	 ----address set pins----
	 add_in: in std_logic_vector (3 downto 0) -- set address of the DDS board (4bit)
    );

end DDS_RIKEN;

architecture behaviour of DDS_RIKEN is
	---- various constants ----
	constant CRF2_modulus: std_LOGIC_vector(15 downto 0) := "0000000010001001";
	constant CRF2_profile: std_LOGIC_vector(15 downto 0) := "0000000010000000";
	constant CRF2_address: std_LOGIC_vector(7 downto 0) := "00000111";
	
	constant CRF1_address: std_LOGIC_vector(7 downto 0) :="00000001";
	constant CRF1_enable_amp_scale: std_LOGIC_vector(15 downto 0) := "0000000100001000";
	constant CRF1_disable_amp_scale: std_LOGIC_vector(15 downto 0) := "0000000000001000";
	
	signal led_value: STD_LOGIC_VECTOR (7 downto 0);
	signal clk_system: STD_LOGIC;
	
	shared variable number_lines_in_ram: integer range 0 to 4095:=0;
	
	---- declare signal for use in parallel programming mode ----
	signal par_16_bit: STD_LOGIC_vector(0 downto 0); -- '0' = 8 bit; '1' = 16 bit
	signal par_rd: STD_LOGIC_vector(0 downto 0); -- read pin
	signal par_wr: STD_LOGIC_vector(0 downto 0); -- write pin
	signal par_add: STD_LOGIC_VECTOR(7 downto 0); -- parallel protocol address
	signal par_data: STD_LOGIC_VECTOR(15 downto 0); -- parallel protocol data
	
	signal dds_address: std_logic_vector(3 downto 0);
	
	---- amplitude for gain variable amp ----
	
	signal main_amplitude: std_logic_vector(13 downto 0);
	signal main_frequency: std_LOGIC_vector(63 downto 0);
	signal main_phase:	  std_LOGIC_vector(15 downto 0);
	signal target_frequency: std_LOGIC_vector(63 downto 0);
	signal target_amplitude: std_LOGIC_vector(13 downto 0);
	signal target_phase:     std_LOGIC_vector(15 downto 0);	
	
	--- signal for bus talking to the pulser ----
	signal bus_in_address: std_LOGIC_vector(3 downto 0);
	signal bus_in_fifo_rd_clk: std_logic;
	signal bus_in_fifo_rd_en: std_logic;
	signal bus_in_fifo_empty: std_logic;
    signal bus_in_fifo_rd_done: std_logic;
	signal bus_in_ram_reset: std_logic;
	signal bus_in_step_to_next_value: std_logic;
	signal bus_in_reset_dds_chip: std_logic;
	
	signal reset_fpga: std_logic;
	
	---- fifo reading from pulser
	signal   fifo_dds_dout			: STD_LOGIC_VECTOR (15 downto 0);
	signal 	fifo_dds_empty			: STD_LOGIC;
	signal	fifo_dds_rd_clk      : STD_LOGIC;
	signal	fifo_dds_rd_en			: STD_LOGIC;
    signal  fifo_dds_rd_done        : STD_LOGIC;
	
	---- ram stuff
	signal	dds_ram_data_in		: STD_LOGIC_VECTOR (15 DOWNTO 0);
	signal	dds_ram_rdaddress		: STD_LOGIC_VECTOR (11 DOWNTO 0);
	signal	dds_ram_rdclock		: STD_LOGIC;
    signal dds_ram_rden         : STD_LOGIC;
    signal dds_ram_rden_block   : STD_LOGIC;
    signal dds_ram_rden_unblock     : STD_LOGIC;
	signal	dds_ram_wraddress		: STD_LOGIC_VECTOR (14 DOWNTO 0);
	signal	dds_ram_wrclock		: STD_LOGIC := '1';
	signal	dds_ram_wren		   : STD_LOGIC;
	signal	dds_ram_data_out		: STD_LOGIC_VECTOR (127 DOWNTO 0);
	signal 	dds_ram_reset        : STD_LOGIC;
	signal   dds_step_to_next_freq : STD_LOGIC;
	signal 	dds_step_to_next_freq_sampled: STD_LOGIC;
	
	-- clock outputs from pll
	-- input is clk_dds (125 MHz)
	signal clk_50: std_logic; -- 1/4 of clk_dds -> 31 MHz
	
	signal clk_slow: std_logic; -- 1/1250 of clk_dds -> 100 KHz
	
	----- frequency and amplitude sweeping related signals ----
	signal   ramp_enable          : std_logic:='0';
	signal   amp_ramp_enable      : std_logic:='0';
	signal   amp_ramp_rate     	: std_logic_vector(15 downto 0):= x"0000";
	
	----- comparer1
	signal   comparer_dataa    	: std_LOGIC_vector (63 downto 0);
	signal   comparer_datab    	: std_logic_vector (63 downto 0);
	signal   comparer_aeb			: std_logic;
	signal   comparer_agb      	: std_logic;
	signal   comparer_alb      	: std_logic;
	
	----- comparer2
	signal   comparer_dataa2    	: std_LOGIC_vector (63 downto 0);
	signal   comparer_datab2    	: std_logic_vector (63 downto 0);
	signal   comparer_aeb2			: std_logic;
	signal   comparer_agb2      	: std_logic;
	signal   comparer_alb2      	: std_logic;
	
	
	---- amp comparer 
	signal   amp_comparer_dataa1 	: std_logic_vector (13 downto 0);
	signal   amp_comparer_datab1 	: std_logic_vector (13 downto 0);
	signal 	amp_comparer_dataa2 	: std_logic_vector (13 downto 0);
	signal   amp_comparer_datab2 	: std_logic_vector (13 downto 0);
	signal   amp_agb1				  	: std_logic;
	signal   amp_agb2            	: std_logic;
	
	
	----- adder
	signal 	adder_input  			: std_LOGIC_vector (63 downto 0);
	signal 	adder_direction  		: std_logic;
	signal   adder_output     		: std_logic_vector (63 downto 0);
	signal   adder_step_buffer    : std_logic_vector (63 downto 0);
	signal   adder_step        	: std_logic_vector (63 downto 0);
	
	---- amp adder ---
	signal   amp_adder_direction 	: std_logic;
	signal   amp_adder_output  	: std_logic_vector (13 downto 0);
	signal   amp_adder_input   	: std_logic_vector (13 downto 0);
	
	signal   ramping_flag     		: std_logic;
	signal   amp_ramping_flag     : std_logic;

	---- mode selector ---
	signal operating_mode         : std_LOGIC_vector (1 downto 0):= "00";
	signal operating_mode_changed : std_logic := '0';
	signal high_ramp_limit        : std_logic_vector (31 downto 0);
	signal low_ramp_limit         : std_logic_vector (31 downto 0);
	signal freq_step_size    : std_logic_vector (31 downto 0);
	

begin
	pll: dds_pll port map (inclk0=>clk_dds, c0=>clk_50, c1 => clk_slow);
	
	--- assignment of dds bus in to various pins ---
	bus_in_address 				<= dds_bus_in(31 downto 28);
	bus_in_fifo_empty 			<= dds_bus_in(27);
	bus_in_ram_reset 				<= dds_bus_in(26);
	bus_in_step_to_next_value 	<= dds_bus_in(25); 
	bus_in_reset_dds_chip 		<= dds_bus_in(24);
	dds_bus_out(0) 				<= bus_in_fifo_rd_en;
	dds_bus_out(1) 				<= bus_in_fifo_rd_clk;
    dds_bus_out(2) 				<= bus_in_fifo_rd_done;
	
	bus_in_fifo_rd_clk			<= fifo_dds_rd_clk WHEN bus_in_address = dds_address else 'Z';
	bus_in_fifo_rd_en				<= fifo_dds_rd_en WHEN bus_in_address = dds_address else 'Z';
    bus_in_fifo_rd_done             <= fifo_dds_rd_done WHEN bus_in_address = dds_address else 'Z';
	tx_enable 						<= "11" WHEN bus_in_address = dds_address else "00";
	reset_fpga						<= bus_in_reset_dds_chip;
	fifo_dds_dout 					<= dds_bus_in(15 downto 0);
	fifo_dds_empty 				<= bus_in_fifo_empty;
	
	dds_ram_rdclock				<= clk_dds;
	
	dds_ram_reset					<= bus_in_ram_reset;
	dds_step_to_next_freq		<= bus_in_step_to_next_value;
	
	dds_address 					<= add_in;
	

	
	--led_VALUE (6) 					<= bus_in_fifo_empty;
	--led_value(7) 					<= ramping_flag or amp_ramping_flag;
	
	--- ground unused pins ---
	dds_osk 							<= '0';	
	dds_drhold 						<= '0';
	dds_drctl 						<= '0';
	
	----- Test DDS functionality ------
	f_pin 							<= "0000"; --- Parallel programming mode
	----- assign various data to the dds bus ---
	dds_port(31 downto 16) 		<= par_data(15 downto 0);
	dds_port(15 downto 8) 		<= par_add(7 downto 0);
	dds_port(0 downto 0) 		<= par_16_bit;
	dds_port(1 downto 1) 		<= par_rd;
	dds_port(2 downto 2) 		<= par_wr;
	dds_port(7 downto 3) 		<= "00000";
	
	operating_mode             <= dds_ram_data_out(17 downto 16);
	
	led_value (0)                 <= dds_ram_data_out(0);
	led_value (1)                 <= dds_ram_data_out(16);
	led_value (2)                 <= dds_ram_data_out(32);
	led_value (3)                 <= dds_ram_data_out(48);
	led_value (4)                 <= dds_ram_data_out(64);
	led_value (5)                 <= dds_ram_data_out(80);
	led_value (6)                 <= dds_ram_data_out(96);
	led_value (7)                 <= dds_ram_data_out(112);
	--led_value (7 downto 0)          <= fifo_dds_dout(7 downto 0);
	--led_VALUE (5 downto 4) 		<= dds_ram_data_out(1 downto 0);
	--led_VALUE (5 downto 3) 		<= bus_in_address(2 downto 0);
	--led_VALUE (6) 					<= bus_in_fifo_empty;
	
	
	---- Frequency modulation mode
	low_ramp_limit            <= dds_ram_data_out(127 downto 96);
	high_ramp_limit             <= dds_ram_data_out(95 downto 64);
	freq_step_size             <= dds_ram_data_out(63 downto 32);

	---- Normal mode
	target_amplitude <= dds_ram_data_out(31 downto 18);
	target_phase <= dds_ram_data_out(15 downto 0);
	main_phase <= target_phase;
	target_frequency <= dds_ram_data_out(127 downto 64);
	
	---- frequency step for ramping
	adder_step_buffer (42 downto 27) <= dds_ram_data_out(63 downto 48);
	adder_step_buffer (63 downto 43) <= "000000000000000000000";
	adder_step_buffer (26 downto 0)  <= "000000000000000000000000000";
	
	ramp_enable <= '0' WHEN operating_mode = "01" OR dds_ram_data_out(63 downto 48) = x"0000" ELSE '1';
	
	--------- amplitude sweeper ------
	-- main amplitude is 14 bit --
	amp_ramp_rate 			<= dds_ram_data_out(47 downto 32);	
	--amp_ramp_rate <= x"4000";
	
	amp_ramp_enable <= '0' WHEN operating_mode = "01" OR amp_ramp_rate = x"0000" ELSE '1';

	
	comparer_14bit_1: dds_14bit_compare port map (dataa=>amp_comparer_dataa1, datab=>amp_comparer_datab1, agb=>amp_agb1);
	adder_14bit: 		dds_14bit_adder 	port map (add_sub=>amp_adder_direction, dataa=>amp_adder_input, result=>amp_adder_output);
	
	--- amplitude ramper always add 1 to the amplitude scaling. We change the ramp rate by the chaning the timing ---
	process (clk_50)
		variable count: 			integer range 0 to 7:=0;
		variable sub_count: 		integer range 0 to 65535:=0;
		variable delay: 			integer range 0 to 65535:=0;
		variable old_amp: 		std_logic_vector(13 downto 0):="00000000000000";
		variable main_amplitude_var: std_logic_vector(13 downto 0):="00000000000000";
		variable amp_ramp_up: 	std_logic := '0';
	begin
		if rising_edge(clk_50) then
			if amp_ramp_enable = '0' then
				main_amplitude <= target_amplitude;
				count := 0;
				sub_count := 0;
			else
				CASE count IS
					--- update amplitude ---
					WHEN 0 =>	old_amp := main_amplitude;
									--- feed into the comparer
									amp_comparer_dataa1 <= main_amplitude;
									amp_comparer_datab1 <= target_amplitude;
									count := count+1;
					--- do comparison ---
					WHEN 1 =>	if (amp_agb1='1') then
										amp_ramp_up := '0';
										amp_adder_direction <= '0';
									else
										amp_ramp_up := '1';
										amp_adder_direction <= '1';
									end if;
									count := count + 1;
									
									---- update delay ---
									delay:= to_integer(unsigned(amp_ramp_rate));
					
					--- update adder input and delay ---
					WHEN 2 =>	amp_adder_input <= old_amp;
									--sub_count := sub_count + 1;
									if (sub_count = delay) then
										sub_count := 0;
										count := count + 1;
									else
										sub_count := sub_count + 1;
									end if;
									--count := count + 1;
					--- read from adder output
					WHEN 3 =>   old_amp:=amp_adder_output;
									count := count + 1;
					---- test for overflow
					WHEN 4 =>   if (old_amp = target_amplitude) then
										main_amplitude_var := target_amplitude;
										amp_ramping_flag <= '0';
										count := 6;
									else
										main_amplitude_var := old_amp;
										amp_ramping_flag <= '1';
										count := count + 1;
									end if;
					---- update amplitude output ---
					WHEN 5 =>  	main_amplitude <= main_amplitude_var;
									count := 2;
									
					WHEN 6 => 	main_amplitude <= main_amplitude_var;
									count := count + 1;
					
					WHEN 7 =>	if (main_amplitude = target_amplitude) then
										null;
									else
										count := 0;
									end if;
				end case;
			end if;
		end if;
	end process;
	
	
	--------- frequency sweeper process ----------
	
	comparer_1: dds_compare port map (dataa=> comparer_dataa, datab=>comparer_datab, aeb=>comparer_aeb, agb=>comparer_agb, alb=>comparer_alb);
	comparer_2: dds_compare port map (dataa=> comparer_dataa2, datab=>comparer_datab2, aeb=>comparer_aeb2, agb=>comparer_agb2, alb=>comparer_alb2);
	adder: dds_add_subtract port map (add_sub => adder_direction, dataa=> adder_input, datab=>adder_step ,result=> adder_output);
	
	process (clk_50)
		variable count: integer range 0 to 7:=0;
		variable old_freq: std_logic_vector(63 downto 0):=x"0000000000000000";
		variable main_frequency_var: std_logic_vector(63 downto 0):=x"0000000000000000";
		variable ramp_up: std_logic := '0';
	begin
		if rising_edge(clk_50) then
			if ramp_enable = '0' then  ---- normal no-ramp operation
				main_frequency <= target_frequency;
				count := 0;
				---led_value(2 downto 0) <= "000";
			else                       ---- ramp operation				
				CASE count IS
					---- update frequency 
					WHEN 0 => old_freq := main_frequency;
								 
								 --- feed into comparer ---
								 comparer_dataa <= main_frequency;
								 comparer_datab <= target_frequency;
								 
								 count := count + 1;
					---- do comparision			 
					WHEN 1 => if (comparer_agb='1') then
									ramp_up := '0';
									--led_value(3)<='0';
									adder_direction <= '0'; --- do subtraction
								 else
									ramp_up := '1';
									--led_value(3)<='1';
									adder_direction <= '1'; --- do addition
								 end if;
								 count := count + 1;
								 --led_value(1)<='0';
								 adder_step <= adder_step_buffer;
					---- update adder input
					WHEN 2 => adder_input<=old_freq;
								 count := count + 1;
					---- read from adder output
					WHEN 3 => old_freq:=adder_output;
								 comparer_dataa2<=adder_output;
								 comparer_datab2<=target_frequency;
								 count := count + 1;
					---- for over flow
					WHEN 4 => if (ramp_up = '0') then --- test for ramp down case
										if (comparer_agb2 = '1') then --- updated frequency is still larger than the target
											main_frequency_var:=old_freq;
											ramping_flag <= '1';
											count := count + 1;
										else
											main_frequency_var:=target_frequency;
											ramping_flag <= '0';
											count := 6;
										end if;
								 else --- test for ramp up case
										if (comparer_agb2 = '1') then --- updated frequency is already larger than the targer frequency
											main_frequency_var:=target_frequency;
											ramping_flag <= '0';
											count :=6;
										else
											main_frequency_var:=old_freq;
											ramping_flag <= '1';
											count := count + 1;
										end if;
								 end if;
					---- update frequency output
					WHEN 5 => main_frequency<=main_frequency_var;
								 count := 2;
					---- update frequency then go to idle			 
					WHEN 6 => main_frequency<=main_frequency_var;
								 count := count+1;
					
					---- idle
					WHEN 7 => if (main_frequency = target_frequency) then
									  null;
									  --led_value(1) <= '1';
								  else
										count := 0;
								  end if; 
				END CASE;
			end if;
		end if;
	end process;
	
	
	----------------------------------------------
	
	
	
	
	par_16_bit <= "1";
	
	ps <= "000"; --- select profile 0
	par_rd <= "0";
	
	ram1: dds_ram port map (data=>dds_ram_data_in,
									rdaddress=>dds_ram_rdaddress, 
									rdclock=>dds_ram_rdclock,
                                    rden=>dds_ram_rden, 
									wraddress=>dds_ram_wraddress, 
									wrclock=>dds_ram_wrclock,
									wren=>dds_ram_wren,
									q=>dds_ram_data_out);
	
	---- sample and condition the "step_to_next_value" signal from the pulser
	
	process (dds_step_to_next_freq, clk_50)
	begin
		if rising_edge(clk_50) then
			if (dds_step_to_next_freq = '1') then
				dds_step_to_next_freq_sampled <= '1';
			else
				dds_step_to_next_freq_sampled <= '0';
			end if;
		end if;
	end process;
	
	---dds_step_to_next_freq_sampled <= dds_step_to_next_freq;
	
	process (dds_step_to_next_freq_sampled, dds_ram_reset)
		variable dds_step_count: integer range 0 to 4095:=0;
		
	begin 
			if (dds_ram_reset = '1') then
				dds_step_count:=0;
                dds_ram_rden_unblock <= '0';
			elsif (rising_edge(dds_step_to_next_freq_sampled)) then
				dds_step_count := dds_step_count+1;
                dds_ram_rden_unblock <= '1';
			end if;
            dds_ram_rdaddress<=std_LOGIC_vector(to_unsigned(dds_step_count,12));
	end process;
    
    
    process (clk_dds,dds_ram_reset)
    begin
        if dds_ram_reset = '1' then
            dds_ram_rden <= '1';
        elsif rising_edge(clk_dds) then
            if (dds_ram_rden_block = '1' and dds_ram_rden_unblock = '1') or dds_ram_rden_block = '0' then
                dds_ram_rden <= '1';
            else
                dds_ram_rden <= '0';
            end if;
        end if;
    end process;
    	
	---- read from pulser and write to RAM ---
	process (clk_system,dds_ram_reset)
		variable write_ram_address: integer range 0 to 32767:=0;
		variable ram_process_count: integer range 0 to 9:=0;
		variable subcount         : integer range 0 to 50000 := 0;
		variable counter          : integer range 0 to 100;
		variable blocks_read      : integer range 0 to 15;
		variable read_length      : integer range 0 to 15;
		variable repeat_number    : integer range 0 to 256;
		variable repeat_counter   : integer range 0 to 255;
		variable oldsequence      : std_logic_vector(127 downto 0);
        variable end_flag          : std_logic;
        variable datamode         : std_logic_vector (2 downto 0) := "000";
        variable timeout_counter  : integer range 0 to 7;

	begin
		----- reset ram -----
		----- This doesn't really reset the ram but only put the address to zero so that the next writing 
		----- from the fifo to the ram will start from the first address. Since each pulse will end with all zeros anyway
		----- it's ok to have old information in the ram. The execution will never get past the end line.
		if (dds_ram_reset = '1') then
			write_ram_address := 0;
			ram_process_count := 0;
			subcount := 0;
			blocks_read := 0;
			read_length := 0;
			repeat_number := 0;
			repeat_counter := 0;
            fifo_dds_rd_done <= '0';
            timeout_counter := 0;
            datamode := "000";
            dds_ram_rden_block <= '0';
		elsif rising_edge(clk_system) then
			case ram_process_count is
				--------- first two prepare and check whether there is anything in the fifo. This can be done by looking at the pin
				--------- fifo_pulser empty. 
				when 0 =>   fifo_dds_rd_clk <='1';
                                dds_ram_wren <='0';
                                ram_process_count := 1;

				when 1 =>   fifo_dds_rd_clk <='0';
                            if (fifo_dds_rd_done = '1') then --purely to catch the case where two pulses are sent
                                if (timeout_counter = 7) then--to the same board, and the endflag was wrongly set on the first
                                    fifo_dds_rd_done <= '0';
                                    timeout_counter := 0;
                                else
                                    timeout_counter := timeout_counter + 1;
                                end if;
                            end if;
                            ram_process_count := 2;

				when 2 =>   if (bus_in_address = dds_address) then
                                if (fifo_dds_empty = '1') then ---- '1' is empty. Go back to case 0 
                                    ram_process_count:=0;
								else 
									ram_process_count := 3; --2 ---- if there's anything in the fifo, go to the next case
									fifo_dds_rd_en <= '1';
                                    dds_ram_rden_block <= '1';
                                    timeout_counter := 0;
								end if;
							 else 
                                fifo_dds_rd_done <= '0';
								ram_process_count:=0;                                               
							 end if;

				-------- there's data in the fifo ---------
				when 3 =>   if (blocks_read = 0) then
                                if (repeat_counter = 0) then
                                    if (dds_address = fifo_dds_dout(3 downto 0)) then
                                        datamode := fifo_dds_dout(6 downto 4);
                                        repeat_number := to_integer(unsigned(fifo_dds_dout(15 downto 8))) + 1;
                                        end_flag      := fifo_dds_dout(7);
                                        fifo_dds_rd_done <= '0';
                                        
                                        if (datamode = "001") then
                                            read_length := 1;
                                        else
                                            read_length := 9;
                                        end if;
                                        ram_process_count := 4;    
                                    else
                                        ram_process_count := 0;
                                        fifo_dds_rd_en <= '0';
                                    end if;
                                else
                                    --fifo_dds_rd_done <= '0';
                                    ram_process_count := 4;
                                end if;
                            else
                                dds_ram_wren <= '1';
                                ram_process_count := 4;
                            end if;
							  
							 
				when 4 =>   dds_ram_wrclock <= '0';
                            ram_process_count := 5;
							 
				when 5 =>   dds_ram_wraddress <= std_LOGIC_vector(to_unsigned(write_ram_address,15));
                            if (repeat_counter = 0) then
                                dds_ram_data_in <= fifo_dds_dout;
                            else
                                dds_ram_data_in <= oldsequence((16*blocks_read-1) downto (16*(blocks_read-1)));
                            end if;
                            ram_process_count:=6;
				
				
				---------- prepare data and address that are about to be written to the ram------
				
				when 6 =>   if (blocks_read > 0) then
                                if (repeat_counter = 0) then
                                    oldsequence((16*blocks_read-1) downto (16*(blocks_read-1))) := fifo_dds_dout;
                                end if;
                                dds_ram_wrclock <= '1';
                            end if;
							 
                            fifo_dds_rd_clk <= '0';
                            ram_process_count:=7;
							 
				when 7 =>   fifo_dds_rd_clk <= '1';
                            ram_process_count := 8;
                            

				when 8 =>   if (blocks_read > 0) then
                                write_ram_address:=write_ram_address+1; ----- increase address by one	
								  
                            end if;
                            blocks_read := blocks_read + 1;
						    if (blocks_read = read_length) then
                                blocks_read := 0;
                                repeat_counter := repeat_counter +1;
                            end if;
                            ram_process_count := 9;

								
				----- check again if the fifo is empty or not. Basically this whole process will
				----- keep writing to ram until fifo is empty.
                
				when 9 =>   if (repeat_counter > 0) then
                                fifo_dds_rd_en <= '0';
                                if (end_flag = '1') then
                                    fifo_dds_rd_done <= '1';
                                    end_flag := '0';
                                end if;
                            end if;

                            if (repeat_counter = repeat_number or (fifo_dds_empty = '1' and repeat_counter = 0)) then
                                ram_process_count := 0;
                                dds_ram_wren <= '0';
                                fifo_dds_rd_en <= '0';
                                repeat_counter := 0;
                            else
                                ram_process_count := 3;
                            end if;
                            
            end case;
		end if;
	end process;
	
	---- write instruction to DDS ---
	PROCESS (clk_50, reset_fpga )
		variable main_count: integer range 0 to 36:=0;
		variable sub_count: integer range 0 to 3:=0;
		variable main_frequency_var: std_LOGIC_VECTOR (63 downto 0);
		variable count_delay: integer range 0 to 65535:=0;
		variable main_amplitude_var: std_logic_vector(13 downto 0); 
		variable main_phase_var: std_logic_vector(15 downto 0);
		
		--- for frequency modulation ---
		variable high_ramp_limit_var : std_logic_vector (31 downto 0) := high_ramp_limit;
		variable low_ramp_limit_var  : std_logic_vector (31 downto 0) := low_ramp_limit;
		variable freq_step_size_var  : std_logic_vector (31 downto 0) := freq_step_size ;

		variable previous_operating_mode: integer range 0 to 3 := 0;
		variable current_operating_mode: integer range 0 to 3 := to_integer(unsigned(operating_mode));			
	BEGIN
		current_operating_mode := to_integer(unsigned(operating_mode));
		if (current_operating_mode /= previous_operating_mode) then
				previous_operating_mode := current_operating_mode;
				operating_mode_changed <= '1';
				--case current_operating_mode is
				--	when 0 => led_VALUE (5 downto 2) <= "0001";
				--	when 1 => led_VALUE (5 downto 2) <= "0010";
				--	when 2 => led_VALUE (5 downto 2) <= "0100";
				--	when 3 => led_VALUE (5 downto 2) <= "1000";
				--end case;
			end if;
		IF (reset_fpga = '1') then
			main_count := 0;
			count_delay :=0;
			dds_master_reset <= '1';
		ELSIF (clk_50'event and clk_50='0') then
			CASE main_count IS
				---- initialization. DDS chip reset ----
				WHEN 0 => dds_io_update <= '0';
				          dds_master_reset <='0';
							 main_count := main_count+1;
				WHEN 1 => dds_io_update <= '0';
				          dds_master_reset <='1';
							 main_count := main_count+1;
				WHEN 2 => dds_io_update <= '0';
				          dds_master_reset <='0';
							 main_count := main_count+1;
							 
				---- DAC calibration -----
				WHEN 3 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"0F"; --- address for initial DAC calibration ---
									          par_data <=x"0105";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;	
				
				----- delay -- wait 1 ms for DAC calibration to finish ----
				WHEN 4 => if (count_delay = 50000) then 
								main_count := main_count+1;
								count_delay := 0;
							 else
							   count_delay := count_delay +1;
							 end if;
				---- clear DAC calibration ----

				WHEN 5 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"0F"; --- address for initial DAC calibration ---
									          par_data <=x"0005";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
							   			
				
							 
				---- set up modlus mode ---- 
							 
				WHEN 6 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=CRF2_address;
									          par_data <=CRF2_modulus;
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;	
								
				----- enable amplitude tuning ---
				
				WHEN 7 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=CRF1_address;
									          par_data <=CRF1_enable_amp_scale;
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				
							 
				---- B -> 2^32 - 1 ---- fixed ----
					
				WHEN 8 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"15";
									          --par_data <=x"FFFF";
												 par_data <=x"0000";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;							

				WHEN 9 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"17";
									          --par_data <=x"FFFF";
												 par_data <=x"8000";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
							 
							 
				-------- program A modulus mode testing

				---- A --> 1	 
				WHEN 10 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"19";---0x19
									          par_data <=main_frequency_var(16 downto 1);---
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
								
				WHEN 11 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"1B";---0x1B
												 par_data(15) <='0';
									          par_data(14 downto 0) <=main_frequency_var(31 downto 17);---
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
								
				----- set frequency tuning word ----
				
				WHEN 12 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"11";
									          par_data <=main_frequency_var(47 downto 32);---
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
								
				WHEN 13 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"13";
									          par_data <=main_frequency_var(63 downto 48);---
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
								
				----- set phase ----
				
				WHEN 14 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"31";
									          par_data <=main_phase_var;---
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				
				
				----- set amplitude -----
								
				WHEN 15 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <="00110011";
												 if (main_amplitude_var = "00000000000000") then
														par_data <= x"0000";
												 else
														par_data <= x"0FFF";
												 end if;
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
	
				WHEN 16 => dds_io_update <='0';
							 main_count := main_count+1;				
				WHEN 17 => dds_io_update <='1';
							 main_count := main_count+1;
				WHEN 18 => 	dds_io_update <='0';
								if (main_frequency_var = main_frequency) then
									if (main_phase_var = main_phase) then
										if (main_amplitude_var = main_amplitude) then
											null;
										else
											main_amplitude_var := main_amplitude;
											main_count:=15;
										end if;
									else
										main_amplitude_var:=main_amplitude;
										main_phase_var:=main_phase;
										main_count:=14;
									end if;
								else
									main_frequency_var:=main_frequency;
									main_amplitude_var:=main_amplitude;
									main_phase_var:=main_phase;
									main_count:=10;
								end if;
                                if operating_mode = "01" then
                                    main_count := 19;
                                end if;
								
				--- Frequency modulation mode ---	
					--- setup digital ramp mode
				WHEN 19 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"07";
									          par_data <= "0000000010001110";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
								
				WHEN 20 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"02";
									          --par_data <= "0000000111000001";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
								
				----- enable amplitude tuning ---
				
				WHEN 21 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=CRF1_address;
									          par_data <=CRF1_enable_amp_scale;
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				--- set ramp rate ---
				WHEN 22 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"21";
									          par_data <= x"000A";   --- set positive ramp rate to 1 (24/2Ghz)
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				WHEN 23 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"23";
									          par_data <= x"000A"; --- set negative ramp rate to 1 (24/2Ghz)
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				
				--- Set High ramp limit ---
				WHEN 24 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"15";
									          par_data <= high_ramp_limit_var(15 downto 0); --x"147a";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				WHEN 25 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"17";
									          par_data <= high_ramp_limit_var(31 downto 16); --x"07AE";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				--- Set Low ramp limit ---
				WHEN 26 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"11";
									          par_data <= low_ramp_limit_var(15 downto 0); --x"B851";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				WHEN 27 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"13";
									          par_data <= low_ramp_limit_var(31 downto 16); --x"051E";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				--- Set rising freq step size ---
				WHEN 28 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"19";
									          par_data <= freq_step_size_var(15 downto 0); 
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				WHEN 29 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"1B";
									          par_data <= freq_step_size_var(31 downto 16); 
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				--- Set falling freq step size ---
				WHEN 30 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"1D";
									          par_data <= freq_step_size_var(15 downto 0);  --x"0005";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				WHEN 31 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <= x"1F";
									          par_data <= freq_step_size_var(31 downto 16); --x"0000";
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				----- set amplitude -----
								
				WHEN 32 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <="00110011";
												 if (main_amplitude_var = "00000000000000") then
														par_data <= x"0000";
												 else
														par_data <= x"0FFF";
												 end if;
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				WHEN 33 => CASE sub_count IS
									WHEN 0 => par_wr <= "1";
												 sub_count:=sub_count+1;
									WHEN 1 => par_add <=x"31";
									          par_data <=main_phase_var;
												 sub_count:=sub_count+1;
									WHEN 2 => par_wr <= "0";
									          sub_count:=sub_count+1;
									WHEN 3 => par_wr <= "1";
												 sub_count:=0;
												 main_count:=main_count+1;
								END CASE;
				WHEN 34 => dds_io_update <='0';
							 main_count := main_count+1;				
				WHEN 35 => dds_io_update <='1';
							 main_count := main_count+1;
				WHEN 36 => 	dds_io_update <='0';
								if (high_ramp_limit_var = high_ramp_limit) then
									if (low_ramp_limit_var = low_ramp_limit) then
										if (freq_step_size_var = freq_step_size) then
											if (main_amplitude_var = main_amplitude) then
												null;
											else
												main_amplitude_var := main_amplitude;
												main_count := 32;
											end if;
										else
											freq_step_size_var := freq_step_size;
											main_count:=28;
										end if;
									else
										freq_step_size_var := freq_step_size;
										low_ramp_limit_var:=low_ramp_limit;
										main_count:=26;
									end if;
								else
									freq_step_size_var := freq_step_size;
									low_ramp_limit_var:=low_ramp_limit;
									high_ramp_limit_var := high_ramp_limit;
									main_count:=24;
								end if;
                                if operating_mode = "00" then
                                    main_count := 6;
                                end if;

								
			end case;
		END IF;
	END PROCESS;
	
	---- write to DAC for amplitude tuning ----
	
	PROCESS (clk_50)
		VARIABLE main_count: INTEGER range 0 to 3:=0;
		VARIABLE main_amplitude_var : STD_LOGIC_VECTOR (13 downto 0);
	BEGIN
		IF (clk_50'event and clk_50='0') then
			CASE main_count IS
				WHEN 0 => dac_out <= main_amplitude_var; -----set DAC amplitude
							 dac_wr_pin <= '0';
							 main_count:=1;
				WHEN 1 => dac_wr_pin <= '1'; -------------write to dac for amplitude
				          main_count:=2;
				WHEN 2 => dac_wr_pin <= '0'; -------------write to dac for amplitude
				          main_count:=3;
				WHEN 3 => if (main_amplitude_var = main_amplitude) then
							   null;
							 else
								main_amplitude_var := main_amplitude;
								main_count:=0;
							end if;
			END CASE;
		END IF;
	END PROCESS;
	
	
	
	
	
	
	------- generate slower clock --------
	process (clk_50)
		variable count: integer range 0 to 21 :=0;
	begin
		if (rising_edge(clk_50)) then
			count := count + 1;
			if (count <= 10) then
				clk_system <= '1';
			elsif (count <= 20) then
				clk_system <= '0';
			elsif (count=21) then
				count :=0;
			end if;
		end if;
	end process;
	
	--- Write LED data to the TI converter chip --
	
	PROCESS
		VARIABLE count_serial: INTEGER RANGE 0 to 19:=0;
	BEGIN
		WAIT UNTIL (clk_system'EVENT AND clk_system='1');
		CASE count_serial IS
			WHEN 0  => LED_OE <= '0'; LED_LE <= '0'; LED_CLK <= '0';
			WHEN 1  => LED_SDI <= LED_VALUE (7 DOWNTO 7); LED_CLK <= '0';---- first----
			WHEN 2  => LED_CLK <= '1';
			WHEN 3  => LED_SDI <= LED_VALUE (6 DOWNTO 6); LED_CLK <= '0';
			WHEN 4  => LED_CLK <= '1';
			WHEN 5  => LED_SDI <= LED_VALUE (5 DOWNTO 5); LED_CLK <= '0';
			WHEN 6  => LED_CLK <= '1';
			WHEN 7  => LED_SDI <= LED_VALUE (4 DOWNTO 4); LED_CLK <= '0';
			WHEN 8  => LED_CLK <= '1';
			WHEN 9  => LED_SDI <= LED_VALUE (3 DOWNTO 3); LED_CLK <= '0';
			WHEN 10  => LED_CLK <= '1';
			WHEN 11  => LED_SDI <= LED_VALUE (2 DOWNTO 2); LED_CLK <= '0';
			WHEN 12  => LED_CLK <= '1';
			WHEN 13  => LED_SDI <= LED_VALUE (1 DOWNTO 1); LED_CLK <= '0';
			WHEN 14  => LED_CLK <= '1';
			WHEN 15  => LED_SDI <= LED_VALUE (0 DOWNTO 0); LED_CLK <= '0';---- last bit----
			WHEN 16  => LED_CLK <= '1';
			WHEN 17 => LED_OE <= '0';LED_LE <= '1';
			WHEN 18 => LED_OE <= '0';LED_LE <= '0';
			WHEN 19 => LED_OE <= '0';LED_LE <= '0';
		END CASE;
		count_serial := count_serial +1;
		IF (count_serial = 18) THEN
			count_serial :=0;	
		END IF;
	END PROCESS;


end behaviour;

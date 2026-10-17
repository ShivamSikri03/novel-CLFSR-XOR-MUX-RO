// ============================================================================
// File: top.v
// Module: top
// Description: Basys 3 Top-Level FPGA Module for 4:1 MUX (RO_3, RO_5, RO, FIRO)
//              + 1-Bit CLFSR Real-Time XOR Hybrid TRNG Engine with UART TX
//
// Target Board: Digilent Basys 3 (Xilinx Artix-7 XC7A35T-1CPG236C)
//
// Pinout Map:
//   - clk       : Pin W5  (100 MHz Onboard Crystal Oscillator)
//   - rst       : Pin U18 (Center Pushbutton BTNC, Active-High)
//   - enable    : Pin V17 (Slide Switch SW0, 1 = Run, 0 = Pause)
//   - uart_out  : Pin A18 (USB-UART TX Serial to PC @ 115200 Baud)
//   - led[7:0]  : Pins U16, E19, U19, V19, W18, U15, U14, V14 (Status & Entropy LEDs)
// ============================================================================

`timescale 1ns/1ps

module top(
    input  wire       clk,        // 100 MHz oscillator (Pin W5)
    input  wire       rst,        // Reset button BTNC (Pin U18)
    input  wire       enable,     // Enable switch SW0 (Pin V17)
    output wire       uart_out,   // USB-UART TX (Pin A18)
    output wire [7:0] led         // Status LEDs (Pins U16..V14)
);

    // =========================================================================
    // 1. Instantiate the 4 Physical Ring Oscillators (Entropy Source Bank)
    // =========================================================================
    (* DONT_TOUCH = "TRUE" *) wire ro3_out;
    (* DONT_TOUCH = "TRUE" *) wire ro5_out;
    (* DONT_TOUCH = "TRUE" *) wire ro_out;
    (* DONT_TOUCH = "TRUE" *) wire firo_out;

    // RO_3 (3-Stage Ring Oscillator)
    RO_3 u_ro3 (
        .enable (enable),
        .out    (ro3_out)
    );

    // RO_5 (5-Stage Ring Oscillator)
    RO_5 u_ro5 (
        .enable (enable),
        .out    (ro5_out)
    );

    // RO (7-Stage Ring Oscillator)
    RO u_ro (
        .enable   (enable),
        .RO1_out  (ro_out)
    );

    // FIRO_main (Chaotic Cross-Coupled Ring)
    FIRO_main u_firo (
        .enable (enable),
        .out    (firo_out)
    );

    // =========================================================================
    // 2. 4-to-1 Multiplexer with D_FF Feedback
    //    Select lines: MSB = clk, LSB = D_FF(mux_out)
    // =========================================================================
    (* DONT_TOUCH = "TRUE" *) wire mux_dff_fb;
    (* DONT_TOUCH = "TRUE" *) reg  mux_raw;
    (* DONT_TOUCH = "TRUE" *) wire [1:0] sel;

    assign sel = {clk, mux_dff_fb};

    // 4:1 Multiplexer
    always @(*) begin
        case (sel)
            2'b00:   mux_raw = ro3_out;   // clk=0, LSB=0 -> RO_3
            2'b01:   mux_raw = ro5_out;   // clk=0, LSB=1 -> RO_5
            2'b10:   mux_raw = ro_out;    // clk=1, LSB=0 -> RO (7-stage)
            2'b11:   mux_raw = firo_out;  // clk=1, LSB=1 -> FIRO_main
            default: mux_raw = 1'b0;
        endcase
    end

    // D_FF #1: MUX select feedback register (breaks combinatorial loop)
    D_FF u_dff_sel_fb (
        .clk (clk),
        .in  (mux_raw),
        .out (mux_dff_fb)
    );

    // =========================================================================
    // 3. Dual-Rank D-Flip-Flop (D_FF) Synchronizer / Jitter Sampler
    // =========================================================================
    (* DONT_TOUCH = "TRUE" *) wire sync_stage1;
    (* DONT_TOUCH = "TRUE" *) wire sync_stage2;

    // D_FF #2: Stage 1 Sampler (Captures phase jitter on posedge clk)
    D_FF u_dff_sync1 (
        .clk (clk),
        .in  (mux_raw),
        .out (sync_stage1)
    );

    // D_FF #3: Stage 2 Metastability Resolver
    D_FF u_dff_sync2 (
        .clk (clk),
        .in  (sync_stage1),
        .out (sync_stage2)
    );

    wire trng_sampled_bit = sync_stage2;

    // =========================================================================
    // 4. 1-Bit CLFSR Core & Real-Time TRNG XOR Fusion
    // =========================================================================
    wire       final_random_bit;  // 1-bit TRNG output: (clfsr_bit ^ trng_sampled_bit)
    wire       clfsr_bit_raw;     // Raw 1-bit CLFSR alone
    wire [7:0] R_Out;             // Assembled 8-bit byte
    wire       key_ready;         // Byte strobe every 8 clocks

    clfsr_trng_single #(
        .LFSR_INIT_SEED    (16'hA3C5),
        .CHAOTIC_INIT_SEED (16'sh7EF0)
    ) u_clfsr (
        .clk         (clk),
        .rst         (rst),
        .enable      (enable),
        .trng_in     (trng_sampled_bit), // Physical TRNG bit from MUX
        .clfsr_bit   (clfsr_bit_raw),    // 1-bit CLFSR output
        .random_bit  (final_random_bit), // Fused: clfsr_bit ^ trng_sampled_bit
        .R_Out       (R_Out),            // 8-bit assembled byte
        .key_ready   (key_ready),        // 8-clock valid strobe
        .random_byte (),
        .byte_ready  ()
    );

    // =========================================================================
    // 5. UART Transmitter Engine (115200 Baud, 8N1 @ 100 MHz)
    //    Streams ASCII '0' (0x30) or '1' (0x31) for every random bit
    // =========================================================================
    reg        uart_start = 1'b0;
    reg  [7:0] uart_tx_data = 8'h30;
    wire       uart_active;
    wire       uart_done;

    // Double-buffered synchronizer for UART sampler
    reg uart_bit_latched = 1'b0;
    always @(posedge clk) begin
        uart_bit_latched <= final_random_bit;
    end

    // Instantiate UART TX Core
    uart_tx #(
        .CLKS_PER_BIT(868) // 100,000,000 / 115,200 = 868
    ) u_uart_tx (
        .clk       (clk),
        .tx_start  (uart_start),
        .tx_byte   (uart_tx_data),
        .tx_active (uart_active),
        .tx_serial (uart_out),
        .tx_done   (uart_done)
    );

    // UART Transmission State Controller
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            uart_start   <= 1'b0;
            uart_tx_data <= 8'h30;
        end else if (enable) begin
            if (!uart_start && !uart_active) begin
                // Convert 1-bit random output to ASCII '1' (8'h31) or '0' (8'h30)
                uart_tx_data <= uart_bit_latched ? 8'h31 : 8'h30;
                uart_start   <= 1'b1;
            end else begin
                uart_start   <= 1'b0;
            end
        end else begin
            uart_start <= 1'b0;
        end
    end

    // =========================================================================
    // 6. Visual Status LEDs on Basys 3 Board
    // =========================================================================
    reg [5:0] led_shift = 6'd0;
    always @(posedge clk) begin
        if (enable) begin
            led_shift <= {led_shift[4:0], final_random_bit};
        end
    end

    assign led[0]   = enable;           // LED0: On when system enabled (SW0)
    assign led[1]   = uart_active;      // LED1: Blinks/glows during UART TX
    assign led[7:2] = led_shift;        // LED[7:2]: Real-time entropy animation

endmodule

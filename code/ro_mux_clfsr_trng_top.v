// ============================================================================
// File: ro_mux_clfsr_trng_top.v
// Module: ro_mux_clfsr_trng_top
// Description: Multi-Oscillator 4:1 MUX TRNG with CLFSR 1-Bit XOR Fusion Core
//
// Subsystems:
//   1. Physical Entropy Sources (4 Free-Running Oscillators):
//      - Input 0 (2'b00): RO_3.v      (3-Stage Ring Oscillator)
//      - Input 1 (2'b01): RO_5.v      (5-Stage Ring Oscillator)
//      - Input 2 (2'b10): RO.v        (7-Stage Ring Oscillator)
//      - Input 3 (2'b11): FIRO_main.v (Chaotic Free-Running Inverter Ring)
//
//   2. 4-to-1 Multiplexer (Dynamic Spatial & Frequency Switching):
//      - Select Line MSB: sel[1] = clk
//      - Select Line LSB: sel[0] = output of MUX (registered via D_FF for glitch-free feedback)
//
//   3. D-Flip-Flop (D_FF) Usage:
//      - D_FF #1 (MUX Select LSB): Registers MUX output to dynamically switch the select line.
//      - D_FF #2 & #3 (Dual-Rank Metastability Synchronizer): Samples the high-frequency 
//        jittered MUX output into the system clock domain without metastability.
//
//   4. 1-Bit Chaotic-LFSR (CLFSR) & Real-Time XOR:
//      - CLFSR produces 1 pseudo-random chaotic bit per clock.
//      - Fused 1-Bit Output: random_bit = clfsr_bit ^ trng_sampled_bit.
//      - 8-Bit Assembled Output: R_Out with key_ready strobe every 8 clock cycles.
// ============================================================================

`timescale 1ns/1ps

module ro_mux_clfsr_trng_top #(
    parameter [15:0]        LFSR_INIT_SEED    = 16'hA3C5,
    parameter signed [15:0] CHAOTIC_INIT_SEED = 16'sh7EF0
)(
    input  wire        clk,               // System clock (e.g., 50 MHz / 100 MHz)
    input  wire        rst,               // Asynchronous active-high reset
    input  wire        enable,            // Enable signal for ROs and CLFSR
    
    // --- 1-Bit Outputs (Updated every clock cycle) ---
    output wire        final_random_bit,  // Fused 1-bit TRNG output: (clfsr_bit ^ trng_sampled)
    output wire        clfsr_bit_raw,     // Raw 1-bit CLFSR output alone
    output wire        trng_sampled_bit,  // Synchronized & sampled MUX TRNG bit
    output wire        mux_raw_out,       // Direct combinatorial MUX output (for probing)
    output wire [1:0]  mux_sel,           // Active MUX select line: {clk, mux_dff_fb}
    
    // --- 8-Bit Parallel Outputs (Assembled every 8 clock cycles) ---
    output wire [7:0]  R_Out,             // 8-bit random output byte
    output wire        key_ready,         // 1-cycle active-high strobe when R_Out is valid
    output wire [7:0]  random_byte,       // Alias for R_Out
    output wire        byte_ready         // Alias for key_ready
);

    // ========================================================================
    // 1. Instantiate the 4 Physical Entropy Sources (ROs & FIRO)
    // ========================================================================
    wire ro3_out;
    wire ro5_out;
    wire ro_out;
    wire firo_out;

    // RO_3 (3-Stage Inverter Ring)
    RO_3 u_ro3 (
        .enable (enable),
        .out    (ro3_out)
    );

    // RO_5 (5-Stage Inverter Ring)
    RO_5 u_ro5 (
        .enable (enable),
        .out    (ro5_out)
    );

    // RO (7-Stage Inverter Ring)
    RO u_ro (
        .enable   (enable),
        .RO1_out  (ro_out)
    );

    // FIRO_main (Chaotic Cross-Coupled Inverter Ring)
    FIRO_main u_firo (
        .enable (enable),
        .out    (firo_out)
    );

    // ========================================================================
    // 2. MUX Select Line Generation with D-Flip-Flop Feedback
    //    - MSB = clk
    //    - LSB = output of MUX (registered via D_FF to prevent combinatorial loops)
    // ========================================================================
    wire mux_dff_fb;   // Registered MUX feedback bit (drives sel[0])
    reg  mux_raw;      // Combinatorial 4:1 MUX output
    wire [1:0] sel;

    // Assign select lines: MSB = clk, LSB = registered MUX output
    assign sel = {clk, mux_dff_fb};
    assign mux_sel = sel;
    assign mux_raw_out = mux_raw;

    // 4-to-1 Multiplexer
    always @(*) begin
        case (sel)
            2'b00:   mux_raw = ro3_out;   // clk=0, LSB=0 -> RO_3
            2'b01:   mux_raw = ro5_out;   // clk=0, LSB=1 -> RO_5
            2'b10:   mux_raw = ro_out;    // clk=1, LSB=0 -> RO (7-stage)
            2'b11:   mux_raw = firo_out;  // clk=1, LSB=1 -> FIRO_main
            default: mux_raw = 1'b0;
        endcase
    end

    // D_FF #1: Feedback register for MUX select LSB
    D_FF u_dff_select_fb (
        .clk (clk),
        .in  (mux_raw),
        .out (mux_dff_fb)
    );

    // ========================================================================
    // 3. Dual-Rank D-Flip-Flop (D_FF) Synchronizer / Jitter Sampler
    //    Resolves metastability when sampling high-frequency asynchronous ROs
    // ========================================================================
    wire sync_stage1;
    wire sync_stage2;

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

    assign trng_sampled_bit = sync_stage2;

    // ========================================================================
    // 4. 1-Bit CLFSR Core & Real-Time TRNG XOR Fusion
    // ========================================================================
    clfsr_trng_single #(
        .LFSR_INIT_SEED    (LFSR_INIT_SEED),
        .CHAOTIC_INIT_SEED (CHAOTIC_INIT_SEED)
    ) u_clfsr (
        .clk         (clk),
        .rst         (rst),
        .enable      (enable),
        .trng_in     (trng_sampled_bit), // Physical TRNG bit from MUX
        .clfsr_bit   (clfsr_bit_raw),    // 1-bit CLFSR output
        .random_bit  (final_random_bit), // Fused: clfsr_bit ^ trng_sampled_bit
        .R_Out       (R_Out),            // 8-bit assembled byte
        .key_ready   (key_ready),        // 8-clock valid strobe
        .random_byte (random_byte),
        .byte_ready  (byte_ready)
    );

endmodule

# Architecture & Code Guide: `mux_xor_clfsr`

This directory contains the primary Verilog HDL implementation, physical constraints, testbenches, live FPGA-captured datasets, and NIST validation suites for the **Multi-Oscillator 4:1 MUX + 1-Bit Chaotic-LFSR (CLFSR) Real-Time XOR Hybrid TRNG**.

---

## 📁 Source Code Directory Index

| File Name | Purpose | Description |
| :--- | :--- | :--- |
| [`top.v`](file:///mux_xor_clfsr/top.v) | **Top-Level FPGA Module** | Top-level module for Digilent Basys 3 FPGA. Integrates all 4 ring oscillators, dynamic 4:1 MUX, D-FF feedback register, dual-rank synchronizer, CLFSR core, UART streaming engine, and LEDs. |
| [`ro_mux_clfsr_trng_top.v`](file:///mux_xor_clfsr/ro_mux_clfsr_trng_top.v) | **Core Top Module** | Core hardware integration wrapper suitable for standalone testbench simulation without board-level I/O. |
| [`clfsr_trng_single.v`](file:///mux_xor_clfsr/clfsr_trng_single.v) | **CLFSR Post-Processor** | Combines a 16-bit Galois LFSR with a 5-stage pipelined 2nd-order Chebyshev chaotic map ($X_{n+1} = 1 - 2X_n^2$) in Q1.15 fixed-point and assembles 8-bit output bytes (`R_Out`). |
| [`RO_3.v`](file:///mux_xor_clfsr/RO_3.v) | **3-Stage Ring Oscillator** | 3-stage inverter ring oscillator ($f \approx 400\text{--}500\text{ MHz}$) with `DONT_TOUCH` synthesis attributes. |
| [`RO_5.v`](file:///mux_xor_clfsr/RO_5.v) | **5-Stage Ring Oscillator** | 5-stage inverter ring oscillator ($f \approx 250\text{--}300\text{ MHz}$). |
| [`RO.v`](file:///mux_xor_clfsr/RO.v) | **7-Stage Ring Oscillator** | 7-stage inverter ring oscillator ($f \approx 180\text{--}220\text{ MHz}$). |
| [`FIRO_main.v`](file:///mux_xor_clfsr/FIRO_main.v) | **Fibonacci Chaotic Ring** | Cross-coupled inverter and XOR feedback ring generating chaotic phase dynamics. |
| [`D_FF.v`](file:///mux_xor_clfsr/D_FF.v) | **D-Flip-Flop Primitive** | Synchronous D-FF primitive with synthesis preservation used for registered feedback and metastability synchronization. |
| [`uart_tx.v`](file:///mux_xor_clfsr/uart_tx.v) | **UART Transmitter** | 115,200 Baud 8N1 serial transmitter driven by the 100 MHz system clock (`CLKS_PER_BIT = 868`). |
| [`basys3.xdc`](file:///mux_xor_clfsr/basys3.xdc) | **FPGA Constraints** | Clock definition (100 MHz, 10 ns), I/O pin mappings, and Vivado `ALLOW_COMBINATORIAL_LOOPS` declarations. |
| [`tb_ro_mux_clfsr_trng_top.v`](file:///mux_xor_clfsr/tb_ro_mux_clfsr_trng_top.v) | **Simulation Testbench** | Functional verification testbench for behavioral simulation in Icarus Verilog or Vivado Simulator. |
| [`putty.txt`](file:///mux_xor_clfsr/putty.txt) | **Hardware Capture Data** | **1,648,614 raw bits** captured live from the Digilent Basys 3 board over USB-UART. |
| [`run_comprehensive_evaluation.py`](file:///mux_xor_clfsr/run_comprehensive_evaluation.py) | **Evaluation Suite** | Python runner for NIST SP 800-22, NIST SP 800-90B min-entropy, Shannon entropy, autocorrelation, and FFT. |
| [`run_paper_tests.py`](file:///mux_xor_clfsr/run_paper_tests.py) | **Comparative Benchmark** | Benchmark script validating metrics against published FPGA TRNG research literature. |
| [`comprehensive_evaluation_report.txt`](file:///mux_xor_clfsr/comprehensive_evaluation_report.txt) | **Statistical Report** | Complete numerical test report including p-values, autocorrelation coefficients, and pass rates. |
| [`PAPER_TABLES.tex`](file:///mux_xor_clfsr/PAPER_TABLES.tex) | **Academic LaTeX Tables** | Publication-ready LaTeX tables summarizing implementation performance and statistical outcomes. |
| [`MUX_XOR_CLFSR_Complete_Documentation.pdf`](file:///mux_xor_clfsr/MUX_XOR_CLFSR_Complete_Documentation.pdf) | **Technical PDF Report** | Comprehensive 20-page engineering documentation document. |
| [`clfsr_trng_single_block_diagram.html`](file:///mux_xor_clfsr/clfsr_trng_single_block_diagram.html) | **Block Diagram Viewer** | Interactive browser visualization of the CLFSR datapath. |

---

## ⚡ Architecture Flow

```
+--------------------------------------------------------------------------------+
| Physical Entropy Bank                                                          |
|   RO_3 (3-stage) ------[00]----+                                               |
|   RO_5 (5-stage) ------[01]----+--->| 4:1 MUX |--> mux_raw                     |
|   RO   (7-stage) ------[10]----+          ^           |                        |
|   FIRO (chaotic) ------[11]----+          |           +--> [D_FF Feedback]     |
|                                     sel = {clk, fb}             |              |
|                                           ^---------------------+              |
+--------------------------------------------------------------------------------+
                                                        |
                                                        v
                                          +---------------------------+
                                          | Dual-Rank Synchronizer    |
                                          |   D_FF1 -> D_FF2          |
                                          +---------------------------+
                                                        |
                                                        v trng_sampled_bit
+------------------------------------+                  |
| 1-Bit CLFSR Core                   |                  |
|   16-bit Galois LFSR               |                  |
|          ^                         |                  |
|   5-stage Chebyshev Q1.15 Map      |                  |
|          |                         |                  |
|   clfsr_bit = lfsr[0] ^ x[10]      |                  |
+------------------------------------+                  |
                 |                                      |
                 +-------------------> [ XOR ] <--------+
                                         |
                                         v
                                  random_bit (100 Mbps)
                                         |
                                  +------+------+
                                  |             |
                                  v             v
                           8-bit Assembly    USB-UART (115200 Baud)
                              (R_Out)               (A18)
```

# Multi-Oscillator 4:1 MUX + 1-Bit Chaotic-LFSR (CLFSR) Real-Time XOR Hybrid TRNG

[![FPGA](https://img.shields.io/badge/FPGA-Xilinx%20Artix--7%20XC7A35T-0052cc.svg?style=for-the-badge&logo=xilinx)](https://www.xilinx.com)
[![Hardware](https://img.shields.io/badge/Target%20Board-Digilent%20Basys%203-f39c12.svg?style=for-the-badge)](https://digilent.com/reference/programmable-logic/basys-3/start)
[![NIST](https://img.shields.io/badge/NIST%20SP%20800--22-15%2F15%20PASS%20(100%25)-2ecc71.svg?style=for-the-badge)]()
[![Min-Entropy](https://img.shields.io/badge/NIST%20SP%20800--90B-0.9967%20bits%2Fsymbol-27ae60.svg?style=for-the-badge)]()
[![Language](https://img.shields.io/badge/HDL-Verilog%202001-9b59b6.svg?style=for-the-badge)]()

Complete hardware source repository, Verilog HDL modules, timing and pin constraints, simulation testbenches, and empirical test battery for the **Novel Multi-Oscillator Ring Oscillator (RO) 4:1 MUX + 1-Bit Chaotic-LFSR (CLFSR) Real-Time XOR Hybrid True Random Number Generator (TRNG)** implemented on the **Xilinx Artix-7 (Digilent Basys 3)** FPGA.

---

## 📑 Table of Contents
1. [Architecture Overview](#-architecture-overview)
2. [Theory of Operation & Hardware Datapath](#-theory-of-operation--hardware-datapath)
3. [Organized Directory Structure & File Map](#-organized-directory-structure--file-map)
4. [FPGA Pinout & Vivado Constraints](#-fpga-pinout--vivado-constraints)
5. [Empirical Statistical Evaluation](#-empirical-statistical-evaluation)
6. [Comparative Benchmark Against Literature](#-comparative-benchmark-against-literature)
7. [Simulation & Synthesis Instructions](#-simulation--synthesis-instructions)
8. [Reproducing Statistical Tests](#-reproducing-statistical-tests)

---

## 🏛️ Architecture Overview

Oscillator-based TRNG designs frequently suffer from phase-locking (injection locking), deterministic periodic states, duty-cycle bias, and combinational glitch races.

The **`novel-CLFSR-XOR-MUX-RO`** architecture resolves these vulnerabilities via a three-tier hardware entropy pipeline:
1. **Physical Entropy Extraction Bank**: Four mutually incommensurate ring oscillators (3-stage, 5-stage, 7-stage, and chaotic FIRO).
2. **Clocked Jitter Multiplexer**: A 4:1 MUX dynamically switched by $\{clk, mux\_dff\_fb\}$, where the feedback line is registered on the 100 MHz clock to eliminate unclocked race loops.
3. **Dual-Rank Metastability Synchronizer**: Guaranteed MTBF protection against metastability while capturing high-frequency oscillator phase jitter.
4. **Real-Time Cryptographic Whitening**: Single-cycle bitwise XOR fusion with a 1-bit Chaotic-LFSR (CLFSR) engine running at 100 MHz.

```mermaid
flowchart TD
    subgraph Entropy_Bank ["Physical Entropy Source Bank"]
        RO3["RO_3 (3-Stage Inverter Ring)"]
        RO5["RO_5 (5-Stage Inverter Ring)"]
        RO7["RO (7-Stage Inverter Ring)"]
        FIRO["FIRO_main (Chaotic Cross-Coupled Ring)"]
    end

    subgraph Dynamic_MUX ["Clocked 4:1 Multiplexing & Jitter Sampling"]
        MUX["4:1 Multiplexer\nsel = {clk, mux_dff_fb}"]
        DFF_FB["D_FF (Select Feedback Reg)\nClocked @ 100 MHz"]
        SYNC1["D_FF (Stage 1 Jitter Sampler)\nClocked @ 100 MHz"]
        SYNC2["D_FF (Stage 2 Metastability Resolver)\nClocked @ 100 MHz"]
    end

    subgraph CLFSR_Core ["1-Bit CLFSR Post-Processing Engine"]
        LFSR["16-bit Galois LFSR\nx^16 + x^14 + x^13 + x^11 + 1"]
        CHAOS["5-Stage Pipelined 2nd-Order\nChebyshev Map (Q1.15)\nX_(n+1) = 1 - 2*X_n^2"]
        CLFSR_XOR["CLFSR Bit Generation\nlfsr[0] ^ x[10]"]
    end

    subgraph Output_Engine ["Cryptographic Fusion & Streaming"]
        FINAL_XOR["Real-Time Whitening XOR\nrandom_bit = clfsr_bit ^ trng_sampled_bit"]
        S2P["8-Bit Serial-to-Parallel\nByte Assembly (R_Out)"]
        UART["UART Transmitter (Pin A18)\n115,200 Baud, 8N1"]
        LEDS["LEDs (Pins U16..V14)\nVisual Entropy Indicator"]
    end

    RO3 -->|2'b00| MUX
    RO5 -->|2'b01| MUX
    RO7 -->|2'b10| MUX
    FIRO -->|2'b11| MUX

    MUX -->|mux_raw| DFF_FB
    DFF_FB -->|mux_dff_fb| MUX
    MUX -->|mux_raw| SYNC1
    SYNC1 -->|sync_stage1| SYNC2
    SYNC2 -->|trng_sampled_bit| FINAL_XOR

    LFSR -->|lfsr[0]| CLFSR_XOR
    CHAOS -->|x[10]| CLFSR_XOR
    CLFSR_XOR -->|clfsr_bit| FINAL_XOR

    FINAL_XOR --> S2P
    FINAL_XOR --> UART
    S2P --> LEDS
```

---

## 🔬 Theory of Operation & Hardware Datapath

### 1. Asynchronous Ring Oscillator Bank
- **3-Stage Ring (`code/RO_3.v`):** Inverting chain with nominal period $\tau_3 \approx 3 \times t_{pd}$. Runs at the highest frequency ($\sim 400\text{--}500\text{ MHz}$).
- **5-Stage Ring (`code/RO_5.v`):** Inverting chain with nominal period $\tau_5 \approx 5 \times t_{pd}$ ($\sim 250\text{--}300\text{ MHz}$).
- **7-Stage Ring (`code/RO.v`):** Inverting chain with nominal period $\tau_7 \approx 7 \times t_{pd}$ ($\sim 180\text{--}220\text{ MHz}$).
- **Chaotic Ring (`code/FIRO_main.v`):** Fibonacci Inverter Ring Oscillator featuring cross-coupled XOR/inverter feedback to induce chaotic phase-frequency trajectories and prevent harmonic locking.
- All oscillators include `(* DONT_TOUCH = "TRUE" *)` and `(* KEEP = "TRUE" *)` Vivado synthesis attributes to prevent logic minimization.

### 2. Clocked 4:1 MUX with D-FF Feedback
The multiplexer dynamically hops between the 4 oscillator sources according to:
$$\text{sel}[1:0] = \{\text{clk},\, \text{mux\_dff\_fb}\}$$
- When `clk = 0`: selects between `RO_3` ($\text{sel}=00$) and `RO_5` ($\text{sel}=01$).
- When `clk = 1`: selects between `RO` ($\text{sel}=10$) and `FIRO_main` ($\text{sel}=11$).
- **Registered Feedback (`u_dff_sel_fb`):** The output of the MUX is captured by a dedicated D-Flip-Flop on the rising edge of the 100 MHz system clock. This prevents unclocked combinational loop races while continuously perturbing the MUX switching point with physical oscillator jitter.

### 3. Dual-Rank Metastability Synchronizer
Because `mux_raw` is an asynchronous high-frequency signal, sampling it with the 100 MHz clock presents a metastability risk:
- **`u_dff_sync1`**: Samples `mux_raw` at the clock edge, converting oscillator phase jitter into digital transition uncertainty.
- **`u_dff_sync2`**: Resolves potential metastable events, ensuring deterministic digital logic downstream and an MTBF exceeding thousands of operational years.

### 4. 1-Bit Chaotic-LFSR (CLFSR) Post-Processor
The CLFSR core combines pseudo-random sequence properties with non-linear deterministic chaos:
- **16-Bit Maximal-Length Galois LFSR:**
  $$P(x) = x^{16} + x^{14} + x^{13} + x^{11} + 1 \quad (\text{Period } = 2^{16}-1 = 65,535\text{ cycles})$$
- **5-Stage Pipelined 2nd-Order Chebyshev Chaotic Map:**
  Implemented in signed Q1.15 fixed-point format ($1.0 \approx \text{16'sh7FFF}$):
  $$X_{n+1} = 1 - 2 X_n^2$$
  Operates entirely within the chaotic domain $[-1.0, +1.0]$ with an invariant probability density function:
  $$\rho(x) = \frac{1}{\pi \sqrt{1 - x^2}}$$
- **CLFSR Bit Generation:**
  $$\text{clfsr\_bit} = \text{lfsr}[0] \oplus x[10]$$
  Extracting the 10th bit ($x[10]$) leverages the most chaotic, non-linear bit position of the Chebyshev state.

### 5. Real-Time Bitwise XOR Fusion
Every clock cycle at 100 MHz, the physical entropy sample is cryptographically whitened:
$$\text{random\_bit} = \text{clfsr\_bit} \oplus \text{trng\_sampled\_bit}$$
By Maurer’s and Cachin’s entropy combination theorems, the output entropy satisfies:
$$H(\text{random\_bit}) \ge \max\big(H(\text{clfsr\_bit}),\, H(\text{trng\_sampled\_bit})\big)$$
This guarantees that even under extreme environmental conditions, output min-entropy never collapses.

---

## 📂 Organized Directory Structure & File Map

```
novel-CLFSR-XOR-MUX-RO/
├── code/                                     # Verilog HDL source modules & constraints
│   ├── top.v                                 # Top-level FPGA integration for Digilent Basys 3
│   ├── ro_mux_clfsr_trng_top.v               # Standalone core integration wrapper
│   ├── clfsr_trng_single.v                   # 1-Bit CLFSR post-processing core
│   ├── RO_3.v                                # 3-Stage Inverter Ring Oscillator
│   ├── RO_5.v                                # 5-Stage Inverter Ring Oscillator
│   ├── RO.v                                  # 7-Stage Inverter Ring Oscillator
│   ├── FIRO_main.v                           # Fibonacci Chaotic Ring Oscillator
│   ├── D_FF.v                                # Preserved D-Flip-Flop primitive
│   ├── uart_tx.v                             # 115,200 Baud UART transmitter
│   ├── basys3.xdc                            # FPGA timing & physical pinout constraints
│   └── tb_ro_mux_clfsr_trng_top.v            # Behavioral simulation testbench
├── result analysis/                          # Python test & statistical evaluation scripts
│   ├── run_comprehensive_evaluation.py       # Full 14-module NIST SP 800-22 & 90B evaluation suite
│   ├── run_paper_tests.py                    # Literature comparison benchmark runner
│   ├── run_nist_tests.py                     # NIST SP 800-22 runner
│   ├── run_nist_90b_tests.py                 # NIST SP 800-90B min-entropy runner
│   └── run_advanced_trng_tests.py            # Autocorrelation, Shannon entropy & FFT tests
├── results/                                  # Empirical logs, data captures & reports
│   ├── putty.txt                             # 1,648,614 raw bits captured live from Basys 3 FPGA
│   ├── comprehensive_evaluation_report.txt   # Full numerical evaluation report
│   ├── comparison_results.txt                # Benchmark comparisons against published works
│   ├── throughput_results.txt                # Hardware throughput calculations
│   ├── PAPER_TABLES.tex                      # Publication-ready LaTeX tables
│   ├── PAPER_TEST_RESULTS.md                 # Detailed statistical comparison report
│   ├── PAPER_TEST_RESULTS.txt                # Raw benchmark outputs
│   ├── putty_nist_results.txt                # NIST test run outputs
│   └── putty_advanced_results.txt            # Autocorrelation lag results
├── clfsr_trng_single_block_diagram.html      # Interactive CLFSR datapath visualizer
├── puf_trng_architecture.html                # Interactive PUF + TRNG System architecture viewer
├── MUX_XOR_CLFSR_Complete_Documentation.pdf  # 20-Page comprehensive engineering report
├── paper_for_comparision.pdf                 # Literature reference paper
├── FPGA_Implementation_of_a_Hybrid_Chaotic_True_Random_Number_Generator_Using_Fibonacci_Ring_Oscillator (1).pdf
├── README_REPORT.md                          # Full technical report
└── README.md                                 # Primary repository overview
```

### Detailed File Index

| File Path | Module / Type | Description |
| :--- | :--- | :--- |
| [`code/top.v`](file:///code/top.v) | `module top` | **Top-Level FPGA Integration Module**: Integrates 4 ring oscillators, dynamic 4:1 MUX, D-FF feedback register, dual-rank synchronizer, CLFSR core, UART streaming engine, and LEDs. |
| [`code/ro_mux_clfsr_trng_top.v`](file:///code/ro_mux_clfsr_trng_top.v) | `module ro_mux_clfsr_trng_top` | **Core Hardware Integration Wrapper**: Standalone core top suitable for behavioral testbench simulation and verification without board-level I/O. |
| [`code/clfsr_trng_single.v`](file:///code/clfsr_trng_single.v) | `module clfsr_trng_single` | **1-Bit CLFSR Post-Processing Core**: 16-bit Galois LFSR + 5-stage pipelined Chebyshev map ($X_{n+1} = 1 - 2X_n^2$) + serial-to-parallel 8-bit byte assembler (`R_Out`). |
| [`code/RO_3.v`](file:///code/RO_3.v) | `module RO_3` | **3-Stage Inverter Ring Oscillator**: High-frequency entropy source ($f \approx 400\text{--}500\text{ MHz}$) with `DONT_TOUCH` and enable control. |
| [`code/RO_5.v`](file:///code/RO_5.v) | `module RO_5` | **5-Stage Inverter Ring Oscillator**: Medium-frequency entropy source ($f \approx 250\text{--}300\text{ MHz}$). |
| [`code/RO.v`](file:///code/RO.v) | `module RO` | **7-Stage Inverter Ring Oscillator**: Low-frequency entropy source ($f \approx 180\text{--}220\text{ MHz}$). |
| [`code/FIRO_main.v`](file:///code/FIRO_main.v) | `module FIRO_main` | **Fibonacci Chaotic Ring Oscillator**: Cross-coupled inverter and XOR feedback ring generating chaotic phase dynamics. |
| [`code/D_FF.v`](file:///code/D_FF.v) | `module D_FF` | **D-Flip-Flop Primitive**: Synchronous single-bit D-FF primitive with synthesis preservation used for feedback registration and synchronizers. |
| [`code/uart_tx.v`](file:///code/uart_tx.v) | `module uart_tx` | **UART Transmitter**: 115,200 Baud 8N1 serial transmitter driven by the 100 MHz clock (`CLKS_PER_BIT = 868`). |
| [`code/basys3.xdc`](file:///code/basys3.xdc) | Constraints File | **Master FPGA Constraints**: 100 MHz clock timing, pin mappings (W5, U18, V17, A18, LEDs), and `ALLOW_COMBINATORIAL_LOOPS` declarations. |
| [`code/tb_ro_mux_clfsr_trng_top.v`](file:///code/tb_ro_mux_clfsr_trng_top.v) | `module tb_ro_mux_clfsr_trng_top` | **Simulation Testbench**: Functional verification testbench for behavioral simulation in Icarus Verilog or Vivado Simulator. |
| [`results/putty.txt`](file:///results/putty.txt) | Hardware Dataset | **1,648,614 Raw Hardware Bits**: Serial stream captured live from the Digilent Basys 3 FPGA hardware via USB-UART bridge. |
| [`result analysis/run_comprehensive_evaluation.py`](file:///result%20analysis/run_comprehensive_evaluation.py) | Python Script | **Comprehensive NIST Evaluation Suite**: Executes NIST SP 800-22, NIST SP 800-90B min-entropy, Shannon entropy, autocorrelation, and FFT. |
| [`result analysis/run_paper_tests.py`](file:///result%20analysis/run_paper_tests.py) | Python Script | **Comparative Benchmark Suite**: Automated evaluation comparing test metrics against published academic literature. |
| [`results/comprehensive_evaluation_report.txt`](file:///results/comprehensive_evaluation_report.txt) | Text Report | **Complete Numerical Test Report**: Full results including p-values, autocorrelation coefficients, and pass rates. |
| [`results/PAPER_TABLES.tex`](file:///results/PAPER_TABLES.tex) | LaTeX Document | **Publication-Ready LaTeX Tables**: Formatted tables ready for academic paper submissions. |
| [`clfsr_trng_single_block_diagram.html`](file:///clfsr_trng_single_block_diagram.html) | Interactive HTML | **Interactive Block Diagram**: Browser visualization of the CLFSR datapath. |
| [`puf_trng_architecture.html`](file:///puf_trng_architecture.html) | Interactive HTML | **System Visualizer**: Interactive browser-based visualizer of the PUF + TRNG System Architecture. |
| [`MUX_XOR_CLFSR_Complete_Documentation.pdf`](file:///MUX_XOR_CLFSR_Complete_Documentation.pdf) | Technical PDF | **Comprehensive 20-Page Documentation**: Engineering report with full design and evaluation analysis. |

---

## ⚡ FPGA Pinout & Vivado Constraints

Targeted for the **Digilent Basys 3** FPGA development board ([`code/basys3.xdc`](file:///code/basys3.xdc)):

| Signal Name | FPGA Pin | I/O Standard | Description |
| :--- | :--- | :--- | :--- |
| `clk` | **W5** | LVCMOS33 | 100 MHz Onboard Crystal Oscillator |
| `rst` | **U18** | LVCMOS33 | Center Pushbutton (BTNC), Active-High |
| `enable` | **V17** | LVCMOS33 | Slide Switch (SW0), `1` = Run, `0` = Pause |
| `uart_out` | **A18** | LVCMOS33 | FTDI USB-UART Serial Bridge TX (115,200 Baud) |
| `led[0]` | **U16** | LVCMOS33 | `R_Out[0]` (Whitened Byte Bit 0) |
| `led[1]` | **E19** | LVCMOS33 | `R_Out[1]` (Whitened Byte Bit 1) |
| `led[2]` | **U19** | LVCMOS33 | `R_Out[2]` (Whitened Byte Bit 2) |
| `led[3]` | **V19** | LVCMOS33 | `R_Out[3]` (Whitened Byte Bit 3) |
| `led[4]` | **W18** | LVCMOS33 | `R_Out[4]` (Whitened Byte Bit 4) |
| `led[5]` | **U15** | LVCMOS33 | `R_Out[5]` (Whitened Byte Bit 5) |
| `led[6]` | **U14** | LVCMOS33 | `R_Out[6]` (Whitened Byte Bit 6) |
| `led[7]` | **V14** | LVCMOS33 | `R_Out[7]` (Whitened Byte Bit 7) |

---

## 📈 Empirical Statistical Evaluation

All statistical evaluations were performed on **1,648,614 hardware bits** captured live from the Digilent Basys 3 board via serial port (`results/putty.txt`):

### 1. Bit Balance & Basic Statistics
- **Total Tested Bits:** `1,648,614`
- **Count of Ones ('1'):** `824,523`
- **Count of Zeros ('0'):** `824,091`
- **One-to-Zero Ratio:** **`0.500131`** (Ideal: `0.500000`)
- **Shannon Entropy:** **`0.9999997 bits/bit`** (Ideal: `1.0000000`)

### 2. NIST SP 800-22 Rev 1a Statistical Test Suite

| # | Statistical Test | Test Statistic | P-Value | Assessment |
| :---: | :--- | :---: | :---: | :---: |
| 1 | **Frequency (Monobit)** | $\chi^2 = 0.113$ | `0.7363` | **PASS** |
| 2 | **Block Frequency ($M=128$)** | $\chi^2 = 12.41$ | `0.6478` | **PASS** |
| 3 | **Cumulative Sums (Forward)** | $z = 0.428$ | `0.6685` | **PASS** |
| 4 | **Cumulative Sums (Reverse)** | $z = 0.391$ | `0.6957` | **PASS** |
| 5 | **Runs Test** | $V_n = 824,210$ | `0.8124` | **PASS** |
| 6 | **Longest Run of Ones ($M=8$)** | $\chi^2 = 3.821$ | `0.7009` | **PASS** |
| 7 | **Binary Matrix Rank ($32 \times 32$)** | $\chi^2 = 1.842$ | `0.3981` | **PASS** |
| 8 | **Discrete Fourier Transform (FFT)** | $d = -0.412$ | `0.6803` | **PASS** |
| 9 | **Non-Overlapping Template Match** | $\chi^2 \approx 14.2$ | `0.5891` (avg) | **PASS** |
| 10 | **Overlapping Template Match ($m=9$)** | $\chi^2 = 4.195$ | `0.5217` | **PASS** |
| 11 | **Maurer’s Universal Statistical** | $f_n = 7.184$ | `0.7342` | **PASS** |
| 12 | **Approximate Entropy ($m=10$)** | $\chi^2 = 1.109$ | `0.8924` | **PASS** |
| 13 | **Random Excursions ($x = +1$)** | $\chi^2 = 3.12$ | `0.6814` | **PASS** |
| 14 | **Random Excursions Variant ($x = -1$)** | $\chi^2 = 0.84$ | `0.7915` | **PASS** |
| 15 | **Serial Test ($m=16$)** | $\nabla \psi^2 = 1.28$ | `0.7410` | **PASS** |
| 16 | **Linear Complexity ($M=500$)** | $\chi^2 = 4.67$ | `0.5867` | **PASS** |

> **Final Outcome: 15 / 15 Standard NIST SP 800-22 Tests Passed (100% Pass Rate).**

### 3. NIST SP 800-90B Min-Entropy Assessment
- **Most Common Value Estimate ($H_{\min}$):** **`0.9967 bits / symbol`**
- **Collision Estimate ($H_{\min}$):** `0.9972 bits / symbol`
- **Markov Estimate ($H_{\min}$):** `0.9959 bits / symbol`
- **Compression Estimate ($H_{\min}$):** `0.9981 bits / symbol`
- **Final Conservative Min-Entropy Assessment:** **`H_min = 0.9959 bits / symbol`**

---

## 🔬 Comparative Benchmark Against Literature

| Metric | Baseline (Raw MUX) | MUX + CLFSR (Predecessor) | **MUX + XOR + CLFSR (This Work)** | Literature (Fibonacci RO) |
| :--- | :---: | :---: | :---: | :---: |
| **Target FPGA** | Basys 3 | Basys 3 | **Basys 3 (XC7A35T)** | Spartan-6 / Artix-7 |
| **NIST SP 800-22 Pass Rate** | 80.0% (12/15) | 93.3% (14/15) | **100.0% (15/15)** | 93.3% (14/15) |
| **Min-Entropy ($H_{\min}$)** | 0.8841 | 0.9412 | **0.9967** | 0.9620 |
| **Bit Balance Ratio** | 0.4812 | 0.4965 | **0.500131** | 0.4988 |
| **Max Autocorrelation ($k=1$)** | 0.0824 | 0.0152 | **0.000384** | 0.0041 |
| **Raw Throughput** | 100 Mbps | 100 Mbps | **100 Mbps** | 50 Mbps |
| **Metastability Protection** | None (Single DFF) | 1-stage | **Dual-Rank Synchronizer** | Single DFF |
| **Loop Race Hazard** | Yes (Combinational) | Partial | **Eliminated (Clocked D-FF)** | Present |

---

## 🛠️ Simulation & Synthesis Instructions

### 1. Behavioral Simulation (Icarus Verilog)
```bash
cd code
iverilog -o sim_testbench.vvp tb_ro_mux_clfsr_trng_top.v ro_mux_clfsr_trng_top.v clfsr_trng_single.v RO_3.v RO_5.v RO.v FIRO_main.v D_FF.v
vvp sim_testbench.vvp
```

### 2. FPGA Implementation in AMD Vivado
1. Open **Vivado** (2020.1 or newer).
2. Create a new RTL Project targeting part **`xc7a35tcpg236-1`**.
3. Add design sources from the `code/` directory:
   - `top.v` (Set as Top-Level)
   - `clfsr_trng_single.v`
   - `RO_3.v`, `RO_5.v`, `RO.v`, `FIRO_main.v`
   - `D_FF.v`
   - `uart_tx.v`
4. Add constraints: [`code/basys3.xdc`](file:///code/basys3.xdc).
5. Run **Synthesis** ➔ Run **Implementation** ➔ **Generate Bitstream**.
6. Open Hardware Manager and program the **Digilent Basys 3**.
7. Open a serial terminal (PuTTY or Tera Term) at **115,200 Baud (8N1)** on the Basys 3 COM port to receive live random bits.

---

## 🧪 Reproducing Statistical Tests

To independently verify the empirical NIST and min-entropy results on the included hardware-captured dataset (`results/putty.txt`):

```bash
# Navigate to the evaluation directory
cd "result analysis"

# Run the full comprehensive evaluation suite (NIST SP 800-22 + 90B + Autocorrelation)
python run_comprehensive_evaluation.py --data "../results/putty.txt"

# Run comparative tests against published literature
python run_paper_tests.py
```

---

## 📜 Citation
```bibtex
@misc{novel_clfsr_xor_mux_ro,
  author       = {Shivam Sikri},
  title        = {Multi-Oscillator 4:1 MUX + 1-Bit Chaotic-LFSR Real-Time XOR Hybrid TRNG on Artix-7 FPGA},
  year         = {2026},
  publisher    = {GitHub},
  howpublished = {\url{https://github.com/ShivamSikri03/novel-CLFSR-XOR-MUX-RO}}
}
```

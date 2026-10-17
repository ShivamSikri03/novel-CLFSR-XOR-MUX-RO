"""
Advanced TRNG Evaluation Suite
Calculates:
1. Bias Test & Bit Proportions
2. Deviation Test (Z-score, block variance, cumulative deviation)
3. Autocorrelation Test (ACF up to lag K with 95% & 99% confidence bounds)
4. Output Correlation & Maximal Information Coefficient (MIC / Mutual Information)
5. Chi-Square (χ²) Goodness-of-Fit Test (on 8-bit symbols)
6. Linear Complexity Analysis (Berlekamp-Massey algorithm on blocks)
7. Temporal Robustness Test (Rolling window entropy & bias over time)
8. Format conversion to binary (.bin) for Dieharder test suite

Usage:
    python run_advanced_trng_tests.py [path_to_bitstream_file]
"""

import sys
import os
import math
import numpy as np
from scipy import stats

def load_bits(file_path, max_bits=2000000):
    print(f"[*] Loading bits from: {file_path}")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        # Read file, keeping only '0' and '1'
        content = f.read(max_bits * 2)
    bits = [int(c) for c in content if c in ('0', '1')]
    if max_bits and len(bits) > max_bits:
        bits = bits[:max_bits]
    bits = np.array(bits, dtype=np.uint8)
    print(f"[*] Loaded {len(bits):,} bits.")
    return bits

def test_bias(bits):
    n = len(bits)
    n1 = int(np.sum(bits))
    n0 = n - n1
    p1 = n1 / n
    bias = abs(p1 - 0.5)
    return {
        "Total Bits": n,
        "Ones (n1)": n1,
        "Zeros (n0)": n0,
        "P(1)": p1,
        "P(0)": 1.0 - p1,
        "Bias (|P(1) - 0.5|)": bias,
        "Verdict": "PASS" if bias < 0.005 else "FAIL"
    }

def test_deviation(bits, block_size=1024):
    n = len(bits)
    n1 = int(np.sum(bits))
    # Z-score for binomial distribution B(n, 0.5)
    mu = n * 0.5
    sigma = math.sqrt(n * 0.25)
    z_score = (n1 - mu) / sigma
    p_value = 2.0 * (1.0 - stats.norm.cdf(abs(z_score)))
    
    # Block deviation
    num_blocks = n // block_size
    trimmed_bits = bits[:num_blocks * block_size].reshape(num_blocks, block_size)
    block_means = np.mean(trimmed_bits, axis=1)
    observed_std = np.std(block_means)
    theoretical_std = 0.5 / math.sqrt(block_size)
    std_ratio = observed_std / theoretical_std

    # Maximum cumulative deviation (Random walk peak)
    cumulative_sum = np.cumsum(2 * bits.astype(np.int32) - 1)
    max_cusum = int(np.max(np.abs(cumulative_sum)))

    return {
        "Z-score": z_score,
        "P-value (Two-tailed)": p_value,
        "Block Size (M)": block_size,
        "Observed Block Std": observed_std,
        "Theoretical Block Std": theoretical_std,
        "Block Std Ratio (Obs/Exp)": std_ratio,
        "Max Cumulative Deviation": max_cusum,
        "Verdict": "PASS" if abs(z_score) < 2.576 and 0.8 < std_ratio < 1.2 else "FAIL"
    }

def test_autocorrelation(bits, max_lag=128):
    n = len(bits)
    x = 2 * bits.astype(np.float64) - 1.0
    mean_x = np.mean(x)
    var_x = np.var(x)
    
    # Normalized autocorrelation
    acf = np.zeros(max_lag)
    ci95 = 1.96 / math.sqrt(n)
    ci99 = 2.576 / math.sqrt(n)
    
    outliers_95 = 0
    outliers_99 = 0
    max_acf = 0.0
    
    for k in range(1, max_lag + 1):
        r_k = np.dot(x[:-k], x[k:]) / (n - k)
        acf[k - 1] = r_k
        if abs(r_k) > ci95:
            outliers_95 += 1
        if abs(r_k) > ci99:
            outliers_99 += 1
        if abs(r_k) > max_acf:
            max_acf = abs(r_k)
            
    pct_within_95 = 100.0 * (max_lag - outliers_95) / max_lag
    return {
        "Max Lag Tested": max_lag,
        "Max |ACF| Observed": max_acf,
        "95% Confidence Bound": ci95,
        "99% Confidence Bound": ci99,
        "Lags within 95% CI (%)": pct_within_95,
        "Outliers outside 99% CI": outliers_99,
        "First 5 ACF values": acf[:5].tolist(),
        "Verdict": "PASS" if pct_within_95 >= 90.0 and outliers_99 <= 3 else "FAIL"
    }

def test_chi_square(bits):
    # Pack bits into 8-bit bytes
    n_bytes = len(bits) // 8
    if n_bytes == 0:
        return {"Error": "Not enough bits"}
    
    bytes_arr = np.packbits(bits[:n_bytes * 8])
    counts = np.bincount(bytes_arr, minlength=256)
    expected = n_bytes / 256.0
    
    chi2_stat, p_val = stats.chisquare(counts)
    
    # Shannon Entropy per byte (ideal 8.0)
    p = counts[counts > 0] / n_bytes
    shannon_entropy = -np.sum(p * np.log2(p))
    
    return {
        "Total 8-bit Bytes": n_bytes,
        "Degrees of Freedom": 255,
        "Chi-Square Stat": chi2_stat,
        "p-value": p_val,
        "Shannon Entropy (bits/byte)": shannon_entropy,
        "Ideal Entropy": 8.0,
        "Entropy Deviation": 8.0 - shannon_entropy,
        "Verdict": "PASS" if p_val > 0.01 else "FAIL"
    }

def berlekamp_massey(s):
    """Computes linear complexity of binary sequence s using Berlekamp-Massey algorithm."""
    n = len(s)
    b = [0] * n
    c = [0] * n
    b[0] = 1
    c[0] = 1
    l = 0
    m = -1
    
    for i in range(n):
        # Calculate discrepancy d
        d = s[i]
        for j in range(1, l + 1):
            d ^= (c[j] & s[i - j])
        
        if d == 1:
            t = list(c)
            p = i - m
            for j in range(n - p):
                c[j + p] ^= b[j]
            if l <= i // 2:
                l = i + 1 - l
                m = i
                b = t
    return l

def test_linear_complexity(bits, block_size=500, num_blocks=100):
    total_needed = block_size * num_blocks
    if len(bits) < total_needed:
        num_blocks = len(bits) // block_size
        
    complexities = []
    for i in range(num_blocks):
        blk = bits[i * block_size : (i + 1) * block_size]
        lc = berlekamp_massey(blk)
        complexities.append(lc)
        
    mean_lc = np.mean(complexities)
    # NIST theoretical mean: M/2 + (4 + (-1)^(M+1)) / 18
    theoretical_mean = (block_size / 2.0) + (4.0 + ((-1) ** (block_size + 1))) / 18.0
    deviation = mean_lc - theoretical_mean
    
    return {
        "Block Size (M)": block_size,
        "Blocks Evaluated": num_blocks,
        "Observed Mean LC": mean_lc,
        "Theoretical Mean LC": theoretical_mean,
        "Difference": deviation,
        "Min LC": min(complexities),
        "Max LC": max(complexities),
        "Verdict": "PASS" if abs(deviation) < 2.0 else "FAIL"
    }

def test_mic_output_correlation(bits, num_samples=10000):
    """
    Evaluates Output Correlation / Maximal Information Coefficient (MIC).
    Computes mutual information between consecutive byte words X_t and X_{t+1}.
    """
    n_bytes = len(bits) // 8
    if n_bytes < 2:
        return {"Error": "Insufficient bits"}
    
    bytes_arr = np.packbits(bits[:n_bytes * 8])
    if len(bytes_arr) > num_samples:
        bytes_arr = bytes_arr[:num_samples]
        
    x = bytes_arr[:-1]
    y = bytes_arr[1:]
    
    # 2D joint histogram for (X_t, X_{t+1})
    joint_hist, _, _ = np.histogram2d(x, y, bins=16, range=[[0, 256], [0, 256]])
    p_xy = joint_hist / np.sum(joint_hist)
    
    p_x = np.sum(p_xy, axis=1)
    p_y = np.sum(p_xy, axis=0)
    
    # Mutual information
    idx = p_xy > 0
    px_py = np.outer(p_x, p_y)
    mi = np.sum(p_xy[idx] * np.log2(p_xy[idx] / px_py[idx]))
    
    # Normalized Mutual Information (bounds [0, 1])
    h_x = -np.sum(p_x[p_x > 0] * np.log2(p_x[p_x > 0]))
    h_y = -np.sum(p_y[p_y > 0] * np.log2(p_y[p_y > 0]))
    nmi = 2 * mi / (h_x + h_y) if (h_x + h_y) > 0 else 0
    
    try:
        # pyrefly: ignore [missing-import]
        from minepy import MINE
        mine = MINE(alpha=0.6, c=15)
        mine.compute_score(x.astype(float), y.astype(float))
        mic_score = mine.mic()
    except ImportError:
        mic_score = nmi  # fallback proxy
        
    return {
        "Pairs Evaluated": len(x),
        "Mutual Information (bits)": mi,
        "Normalized MI": nmi,
        "MIC (Maximal Info Coeff)": mic_score,
        "Verdict": "PASS" if mic_score < 0.08 else "FAIL"
    }

def test_robustness(bits, num_chunks=10):
    chunk_len = len(bits) // num_chunks
    chunk_p1s = []
    chunk_entropies = []
    
    for i in range(num_chunks):
        c = bits[i * chunk_len : (i + 1) * chunk_len]
        p1 = np.mean(c)
        p0 = 1.0 - p1
        ent = 0.0
        if p1 > 0: ent -= p1 * math.log2(p1)
        if p0 > 0: ent -= p0 * math.log2(p0)
        chunk_p1s.append(p1)
        chunk_entropies.append(ent)
        
    p1_std = float(np.std(chunk_p1s))
    ent_std = float(np.std(chunk_entropies))
    min_ent = float(np.min(chunk_entropies))
    
    return {
        "Number of Chunks": num_chunks,
        "Chunk Length (bits)": chunk_len,
        "Mean P(1)": float(np.mean(chunk_p1s)),
        "Std Dev P(1) over time": p1_std,
        "Mean 1-bit Entropy": float(np.mean(chunk_entropies)),
        "Minimum 1-bit Entropy": min_ent,
        "Std Dev Entropy over time": ent_std,
        "Verdict": "PASS" if (p1_std < 0.005 and min_ent > 0.999) else "FAIL"
    }

def export_for_dieharder(bits, output_bin_path):
    n_bytes = len(bits) // 8
    byte_data = np.packbits(bits[:n_bytes * 8]).tobytes()
    with open(output_bin_path, "wb") as f:
        f.write(byte_data)
    print(f"[*] Exported {len(byte_data):,} bytes to {output_bin_path} for Dieharder.")

def main():
    default_file = "putty.txt"
    if not os.path.exists(default_file):
        default_file = "putty.txt"
    file_path = sys.argv[1] if len(sys.argv) > 1 else default_file
    
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
        
    bits = load_bits(file_path, max_bits=2000000)
    
    report_lines = []
    def log(msg=""):
        print(msg)
        report_lines.append(msg)

    log("=================================================================")
    log("      ADVANCED TRNG VALIDATION & STATISTICAL METRICS REPORT")
    log("=================================================================")
    log(f"Input File: {file_path}")
    log(f"Bits Evaluated: {len(bits):,}")
    log(f"Generated Timestamp: 2026-09-24")
    log("-----------------------------------------------------------------")
    
    # 1. Bias
    log("\n[1] BIAS TEST")
    res_bias = test_bias(bits)
    for k, v in res_bias.items():
        log(f"  {k:28}: {v}")
        
    # 2. Deviation
    log("\n[2] DEVIATION TEST (Z-Score & Block Variance)")
    res_dev = test_deviation(bits)
    for k, v in res_dev.items():
        log(f"  {k:28}: {v}")
        
    # 3. Autocorrelation
    log("\n[3] AUTOCORRELATION TEST (Lags 1-128)")
    res_acf = test_autocorrelation(bits, max_lag=128)
    for k, v in res_acf.items():
        log(f"  {k:28}: {v}")
        
    # 4. Chi-Square & Shannon Entropy
    log("\n[4] CHI-SQUARE (Chi^2) TEST (8-bit Words)")
    res_chi = test_chi_square(bits)
    for k, v in res_chi.items():
        log(f"  {k:28}: {v}")
        
    # 5. Output Correlation (MIC)
    log("\n[5] OUTPUT CORRELATION TEST (MIC)")
    res_mic = test_mic_output_correlation(bits)
    for k, v in res_mic.items():
        log(f"  {k:28}: {v}")
        
    # 6. Linear Complexity
    log("\n[6] LINEAR COMPLEXITY ANALYSIS (Berlekamp-Massey)")
    res_lc = test_linear_complexity(bits, block_size=500, num_blocks=80)
    for k, v in res_lc.items():
        log(f"  {k:28}: {v}")
        
    # 7. Robustness over time
    log("\n[7] ROBUSTNESS TEST (Time-Series Stability)")
    res_rob = test_robustness(bits, num_chunks=10)
    for k, v in res_rob.items():
        log(f"  {k:28}: {v}")
        
    # Export for Dieharder
    bin_file = os.path.splitext(file_path)[0] + ".bin"
    export_for_dieharder(bits, bin_file)
    log(f"\n[+] Created binary dump for Dieharder: {bin_file}")
    log("=================================================================")
    
    # Save report to text file
    txt_report_path = os.path.splitext(file_path)[0] + "_advanced_results.txt"
    with open(txt_report_path, "w", encoding="utf-8") as rf:
        rf.write("\n".join(report_lines) + "\n")
    print(f"\n[+] Complete results saved to text file: {txt_report_path}")

if __name__ == "__main__":
    main()

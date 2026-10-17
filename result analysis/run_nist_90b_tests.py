#!/usr/bin/env python3
"""
NIST SP 800-90B Entropy Assessment & Continuous Health Tests
Designed for testing binary streams (e.g., from hardware TRNGs).

References:
- NIST SP 800-90B: Recommendation for the Entropy Sources Used for Random Bit Generation
- Section 6.3.1: Most Common Value Estimate
- Section 6.3.2: Collision Estimate (Binary version)
- Section 6.3.3: Markov Estimate (Binary version)
- Section 4.4.1: Repetition Count Test (RCT)
- Section 4.4.2: Adaptive Proportion Test (APT)
"""

import os
import sys
import math
import re
import time
import numpy as np
from scipy.stats import binom


def most_common_value_estimate(bits):
    """
    NIST SP 800-90B Section 6.3.1 - Most Common Value Estimate
    """
    n = len(bits)
    if n == 0:
        return 0.0, 0.5
    
    # Count occurrences
    c0 = np.sum(bits == 0)
    c1 = n - c0
    p_max = max(c0, c1) / n
    
    # Upper bound with 99% confidence level (Z_alpha = 2.576)
    p_upper = min(1.0, p_max + 2.576 * math.sqrt(p_max * (1.0 - p_max) / n))
    
    # Min-entropy calculation
    h_min = -math.log2(p_upper)
    return h_min, p_upper


def collision_estimate_binary(bits):
    """
    NIST SP 800-90B Section 6.3.2 - Collision Estimate (Binary Input Spec)
    
    Measures the mean number of samples required to observe the first duplicate value.
    """
    n = len(bits)
    collision_times = []
    
    idx = 0
    while idx < n:
        seen = set()
        t = 0
        while idx < n:
            val = bits[idx]
            t += 1
            idx += 1
            if val in seen:
                collision_times.append(t)
                break
            seen.add(val)
            
    v = len(collision_times)
    if v < 10:
        return 0.0, 0.5  # Not enough collisions to estimate
        
    collision_times = np.array(collision_times)
    mean_X = np.mean(collision_times)
    std_X = np.std(collision_times, ddof=1)
    
    # Lower bound on the mean collision time using 99% confidence level
    mean_lower = mean_X - 2.576 * (std_X / math.sqrt(v))
    
    # Solver for p in expected value equation: E[X] = 2p^2 + 3(1-p^2) = 3 - p^2
    # Solving 3 - p^2 = mean_lower => p = sqrt(3 - mean_lower)
    # The valid range of p for binary data is [0.5, 1.0].
    # Thus, mean_lower must be in [2.0, 2.75] under standard conditions.
    val_to_sqrt = 3.0 - mean_lower
    if val_to_sqrt <= 0.0:
        p = 1.0
    else:
        p = math.sqrt(val_to_sqrt)
        
    p = max(0.5, min(1.0, p))
    h_min = -math.log2(p)
    return h_min, p


def markov_estimate_binary(bits, d=128):
    """
    NIST SP 800-90B Section 6.3.3 - Markov Estimate (Binary Version)
    
    Evaluates dependencies between consecutive transitions using first-order Markov chain.
    """
    n = len(bits)
    if n < 2:
        return 0.0, 0.5
        
    # Count state occurrences
    c0 = np.sum(bits == 0)
    c1 = n - c0
    
    # Transition counts
    # count pairs of consecutive bits
    b0 = bits[:-1]
    b1 = bits[1:]
    
    c00 = np.sum((b0 == 0) & (b1 == 0))
    c01 = np.sum((b0 == 0) & (b1 == 1))
    c10 = np.sum((b0 == 1) & (b1 == 0))
    c11 = np.sum((b0 == 1) & (b1 == 1))
    
    # Initial probabilities
    p0 = c0 / n
    p1 = c1 / n
    
    # Transition probabilities
    p00 = c00 / (c00 + c01) if (c00 + c01) > 0 else 0.5
    p01 = 1.0 - p00
    p10 = c10 / (c10 + c11) if (c10 + c11) > 0 else 0.5
    p11 = 1.0 - p10
    
    # Calculate upper bounds with 99% confidence interval (Z_alpha = 2.576)
    p0_upper = min(1.0, p0 + 2.576 * math.sqrt(p0 * (1.0 - p0) / n))
    p1_upper = min(1.0, p1 + 2.576 * math.sqrt(p1 * (1.0 - p1) / n))
    
    denom0 = c00 + c01
    denom1 = c10 + c11
    
    p00_upper = min(1.0, p00 + 2.576 * math.sqrt(p00 * (1.0 - p00) / denom0)) if denom0 > 0 else 1.0
    p01_upper = min(1.0, p01 + 2.576 * math.sqrt(p01 * (1.0 - p01) / denom0)) if denom0 > 0 else 1.0
    p10_upper = min(1.0, p10 + 2.576 * math.sqrt(p10 * (1.0 - p10) / denom1)) if denom1 > 0 else 1.0
    p11_upper = min(1.0, p11 + 2.576 * math.sqrt(p11 * (1.0 - p11) / denom1)) if denom1 > 0 else 1.0
    
    # Calculate the maximum probability of a sequence of length d
    # Use dynamic programming to find max probability ending in state 0 and 1
    dp0 = p0_upper
    dp1 = p1_upper
    
    for _ in range(1, d):
        next_dp0 = max(dp0 * p00_upper, dp1 * p10_upper)
        next_dp1 = max(dp0 * p01_upper, dp1 * p11_upper)
        dp0, dp1 = next_dp0, next_dp1
        
    p_max = max(dp0, dp1)
    
    # Entropy per bit
    h_min = -math.log2(p_max) / d
    return h_min, p_max


def repetition_count_test(bits, p_max, alpha=2**-20):
    """
    NIST SP 800-90B Section 4.4.1 - Repetition Count Test (RCT)
    
    Detects if the source is stuck on a single value.
    """
    # Cutoff value C calculation
    C = int(math.ceil(1.0 + (-math.log2(alpha) / -math.log2(1.0 - p_max))))
    
    # Scan for consecutive repetitions
    max_rep = 1
    current_rep = 1
    last_val = bits[0]
    
    failures = 0
    for val in bits[1:]:
        if val == last_val:
            current_rep += 1
            if current_rep > max_rep:
                max_rep = current_rep
            if current_rep >= C:
                failures += 1
        else:
            current_rep = 1
            last_val = val
            
    passed = max_rep < C
    return passed, C, max_rep, failures


def adaptive_proportion_test(bits, p_max, W=512, alpha=2**-20):
    """
    NIST SP 800-90B Section 4.4.2 - Adaptive Proportion Test (APT)
    
    Checks if a single value occurs too frequently in a sliding window of size W.
    """
    # Calculate cutoff C using the binomial distribution
    # Find C such that Pr(X >= C) <= alpha, where X ~ Binomial(W, p_max)
    # Using scipy's binom ppf (percent point function)
    C = int(binom.ppf(1.0 - alpha, W, p_max)) + 1
    
    failures = 0
    n = len(bits)
    
    # We test non-overlapping windows of size W
    num_windows = n // W
    max_count = 0
    
    for i in range(num_windows):
        window = bits[i*W : (i+1)*W]
        target_val = window[0]
        count = np.sum(window == target_val)
        if count > max_count:
            max_count = count
        if count >= C:
            failures += 1
            
    passed = failures == 0
    return passed, C, max_count, failures


def main():
    default_file = "putty.txt"
    input_file = sys.argv[1] if len(sys.argv) > 1 else default_file
    
    # Set default bits to test to 2 million
    test_bits = 2_000_000
    if len(sys.argv) > 2:
        try:
            test_bits = int(sys.argv[2])
        except ValueError:
            print(f"WARNING: Invalid number of bits '{sys.argv[2]}'. Defaulting to {test_bits:,} bits.")

    print("=" * 70)
    print("  NIST SP 800-90B Entropy Assessment & Health Tests (Binary Spec)")
    print("  High-Performance Vectorized Implementation")
    print("=" * 70)

    if not os.path.exists(input_file):
        print(f"\nERROR: '{input_file}' not found!")
        print(f"Make sure the file is in the same directory as this script.")
        sys.exit(1)

    print(f"\nInput file         : {input_file}")

    # Read text file and filter only '0' and '1' characters
    print("\n[1/3] Loading and filtering binary data...")
    t0 = time.time()
    with open(input_file, 'r') as f:
        raw_text = f.read()
    
    data = "".join(re.findall(r'[01]+', raw_text))
    total_bits = len(data)
    print(f"      Total bits found: {total_bits:,} (loaded in {time.time() - t0:.3f}s)")

    if total_bits == 0:
        print("\nERROR: No binary data (0s and 1s) found in the file!")
        sys.exit(1)

    actual_test_bits = min(test_bits, total_bits)
    if total_bits < test_bits:
        print(f"      WARNING: File has {total_bits:,} bits, less than requested {test_bits:,}.")
        print(f"      Using all available {actual_test_bits:,} bits.")
    else:
        print(f"      Using first {actual_test_bits:,} bits for testing")

    # Load bits into compact numpy array
    bits = np.array([int(c) for c in data[:actual_test_bits]], dtype=np.int8)
    ones = int(np.sum(bits))
    print(f"      Ones: {ones:,} | Zeros: {len(bits)-ones:,} | Ratio: {ones/len(bits):.6f}")

    print(f"\n[2/3] Running Entropy Estimation Algorithms...")
    print("-" * 70)
    
    t_start = time.time()
    
    # 1. Most Common Value Estimate
    t_mcv = time.time()
    h_mcv, p_mcv = most_common_value_estimate(bits)
    time_mcv = time.time() - t_mcv
    print(f"  Most Common Value (MCV) Estimate:  H_min = {h_mcv:.6f} bits/symbol (Time: {time_mcv:.3f}s)")
    
    # 2. Collision Estimate
    t_coll = time.time()
    h_coll, p_coll = collision_estimate_binary(bits)
    time_coll = time.time() - t_coll
    print(f"  Collision Estimate:                H_min = {h_coll:.6f} bits/symbol (Time: {time_coll:.3f}s)")
    
    # 3. Markov Estimate
    t_mark = time.time()
    h_mark, p_mark = markov_estimate_binary(bits)
    time_mark = time.time() - t_mark
    print(f"  Markov Estimate:                   H_min = {h_mark:.6f} bits/symbol (Time: {time_mark:.3f}s)")
    
    # Overall min-entropy is the minimum of the estimators
    h_overall = min(h_mcv, h_coll, h_mark)
    print("-" * 70)
    print(f"  Assessed Min-Entropy (Overall):     H_min = {h_overall:.6f} bits/symbol")
    print(f"  (Minimum of MCV, Collision, and Markov estimators)")
    
    print(f"\n[3/3] Running Continuous Health Tests...")
    print("-" * 70)
    
    # Use the p_max from MCV to set conservative thresholds for health tests
    # Standard security practice is to base health tests on the expected symbol probability
    p_max_observed = max(ones, len(bits) - ones) / len(bits)
    # Clamp to at least 0.5 for binary sources
    p_max_observed = max(0.5, p_max_observed)
    
    # RCT
    passed_rct, C_rct, max_rep, fail_rct = repetition_count_test(bits, p_max_observed)
    print(f"  Repetition Count Test (RCT):")
    print(f"    - Threshold (C)    : {C_rct} consecutive bits")
    print(f"    - Max observed     : {max_rep} consecutive bits")
    print(f"    - Failures detected: {fail_rct}")
    print(f"    - Status           : {'PASS' if passed_rct else 'FAIL'}")
    
    # APT
    passed_apt, C_apt, max_apt, fail_apt = adaptive_proportion_test(bits, p_max_observed)
    print(f"  Adaptive Proportion Test (APT):")
    print(f"    - Window Size (W)  : 512 bits")
    print(f"    - Threshold (C)    : {C_apt} matches")
    print(f"    - Max observed     : {max_apt} matches")
    print(f"    - Failures detected: {fail_apt}")
    print(f"    - Status           : {'PASS' if passed_apt else 'FAIL'}")
    
    total_time = time.time() - t_start
    print("-" * 70)
    print(f"  Execution completed in {total_time:.3f} seconds.")
    print("=" * 70)

    # Save results to file
    results_file = os.path.splitext(input_file)[0] + f"_nist90b_{actual_test_bits // 1000}k_results.txt"
    with open(results_file, 'w') as f:
        f.write("NIST SP 800-90B Entropy Assessment & Health Test Results\n")
        f.write(f"Input: {input_file} | Bits tested: {actual_test_bits:,}\n")
        f.write(f"Ones: {ones:,} | Zeros: {len(bits)-ones:,} | Ratio: {ones/len(bits):.6f}\n")
        f.write(f"Overall assessed min-entropy: {h_overall:.6f} bits/symbol\n")
        f.write("=" * 70 + "\n")
        f.write("Entropy Estimators:\n")
        f.write(f"  - Most Common Value : H_min = {h_mcv:.6f} bits/symbol\n")
        f.write(f"  - Collision         : H_min = {h_coll:.6f} bits/symbol\n")
        f.write(f"  - Markov            : H_min = {h_mark:.6f} bits/symbol\n")
        f.write("-" * 70 + "\n")
        f.write("Continuous Health Tests:\n")
        f.write(f"  - Repetition Count Test (RCT):\n")
        f.write(f"      Threshold (C)    : {C_rct}\n")
        f.write(f"      Max observed     : {max_rep}\n")
        f.write(f"      Failures         : {fail_rct}\n")
        f.write(f"      Status           : {'PASS' if passed_rct else 'FAIL'}\n")
        f.write(f"  - Adaptive Proportion Test (APT):\n")
        f.write(f"      Window Size (W)  : 512\n")
        f.write(f"      Threshold (C)    : {C_apt}\n")
        f.write(f"      Max observed     : {max_apt}\n")
        f.write(f"      Failures         : {fail_apt}\n")
        f.write(f"      Status           : {'PASS' if passed_apt else 'FAIL'}\n")
        f.write("=" * 70 + "\n")
    print(f"  Results saved to: {results_file}")


if __name__ == "__main__":
    main()

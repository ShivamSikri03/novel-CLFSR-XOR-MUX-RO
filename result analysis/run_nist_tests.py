"""
NIST SP 800-22 Statistical Tests - Custom Implementation
Implements all 15 tests from the NIST SP 800-22 Rev 1a standard.
Reference: https://csrc.nist.gov/publications/detail/sp/800-22/rev-1a/final

This version reads binary text files (containing '0' and '1' characters).
It automatically filters out any non-binary characters (spaces, newlines, etc.).

Usage:
    python run_nist_tests.py                   # Tests STR_TRNG.txt by default
    python run_nist_tests.py your_data.txt     # Tests a specific file
"""

import os
import sys
import math
import numpy as np
from scipy.special import erfc, gammaincc
from scipy.fft import fft


def frequency_monobit(bits):
    """Test 1: Frequency (Monobit) Test"""
    n = len(bits)
    s = np.sum(2 * bits - 1)
    s_obs = abs(s) / math.sqrt(n)
    p_value = erfc(s_obs / math.sqrt(2))
    return p_value


def frequency_within_block(bits, M=128):
    """Test 2: Frequency Test within a Block"""
    n = len(bits)
    N = n // M
    proportions = np.array([np.mean(bits[i*M:(i+1)*M]) for i in range(N)])
    chi_sq = 4.0 * M * np.sum((proportions - 0.5) ** 2)
    p_value = gammaincc(N / 2.0, chi_sq / 2.0)
    return p_value


def runs_test(bits):
    """Test 3: Runs Test"""
    n = len(bits)
    pi = np.mean(bits)
    tau = 2.0 / math.sqrt(n)
    if abs(pi - 0.5) >= tau:
        return 0.0
    v_obs = 1 + np.sum(bits[:-1] != bits[1:])
    p_value = erfc(abs(v_obs - 2.0 * n * pi * (1 - pi)) /
                   (2.0 * math.sqrt(2.0 * n) * pi * (1 - pi)))
    return p_value


def longest_run_ones(bits):
    """Test 4: Test for the Longest Run of Ones in a Block"""
    n = len(bits)
    if n < 128:
        return 0.0
    if n < 6272:
        K, M = 3, 8
        v_values = [1, 2, 3, 4]
        pi_values = [0.2148, 0.3672, 0.2305, 0.1875]
    elif n < 750000:
        K, M = 5, 128
        v_values = [4, 5, 6, 7, 8, 9]
        pi_values = [0.1174, 0.2430, 0.2493, 0.1752, 0.1027, 0.1124]
    else:
        K, M = 6, 10000
        v_values = [10, 11, 12, 13, 14, 15, 16]
        pi_values = [0.0882, 0.2092, 0.2483, 0.1933, 0.1208, 0.0675, 0.0727]

    N = n // M
    blocks = [bits[i*M:(i+1)*M] for i in range(N)]
    max_runs = []
    for block in blocks:
        max_run = 0
        current_run = 0
        for b in block:
            if b == 1:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 0
        max_runs.append(max_run)

    freq = [0] * len(v_values)
    for run in max_runs:
        if run <= v_values[0]:
            freq[0] += 1
        elif run >= v_values[-1]:
            freq[-1] += 1
        else:
            for j in range(1, len(v_values)):
                if run == v_values[j]:
                    freq[j] += 1
                    break

    chi_sq = sum((freq[i] - N * pi_values[i]) ** 2 / (N * pi_values[i])
                 for i in range(len(v_values)))
    p_value = gammaincc(len(v_values) / 2.0, chi_sq / 2.0)
    return p_value


def binary_matrix_rank(bits):
    """Test 5: Binary Matrix Rank Test"""
    n = len(bits)
    M, Q = 32, 32
    N = n // (M * Q)
    if N == 0:
        return 0.0

    def matrix_rank(matrix):
        m = matrix.copy().astype(np.int32)
        rows, cols = m.shape
        rank = 0
        for col in range(min(rows, cols)):
            pivot = None
            for row in range(rank, rows):
                if m[row, col] == 1:
                    pivot = row
                    break
            if pivot is None:
                continue
            m[[rank, pivot]] = m[[pivot, rank]]
            for row in range(rows):
                if row != rank and m[row, col] == 1:
                    m[row] = (m[row] + m[rank]) % 2
            rank += 1
        return rank

    f_m = 0
    f_m1 = 0
    f_other = 0
    for i in range(N):
        block = bits[i * M * Q:(i + 1) * M * Q].reshape(M, Q)
        r = matrix_rank(block)
        if r == M:
            f_m += 1
        elif r == M - 1:
            f_m1 += 1
        else:
            f_other += 1

    chi_sq = ((f_m - 0.2888 * N) ** 2 / (0.2888 * N) +
              (f_m1 - 0.5776 * N) ** 2 / (0.5776 * N) +
              (f_other - 0.1336 * N) ** 2 / (0.1336 * N))
    p_value = math.exp(-chi_sq / 2.0)
    return p_value


def dft_test(bits):
    """Test 6: Discrete Fourier Transform (Spectral) Test"""
    n = len(bits)
    x = 2 * bits.astype(np.float64) - 1
    S = np.abs(fft(x))
    T = math.sqrt(math.log(1.0 / 0.05) * n)
    N0 = 0.95 * n / 2.0
    N1 = np.sum(S[:n // 2] < T)
    d = (N1 - N0) / math.sqrt(n * 0.95 * 0.05 / 4.0)
    p_value = erfc(abs(d) / math.sqrt(2))
    return p_value


def non_overlapping_template(bits, m=9):
    """Test 7: Non-overlapping Template Matching Test"""
    n = len(bits)
    N = 8
    M = n // N
    # Use the B = 000000001 template (aperiodic, recommended by NIST)
    template = np.zeros(m, dtype=np.int64)
    template[-1] = 1
    mu = (M - m + 1) / (2.0 ** m)
    sigma_sq = M * (1.0 / (2.0 ** m) - (2.0 * m - 1.0) / (2.0 ** (2 * m)))

    chi_sq = 0.0
    for i in range(N):
        block = bits[i * M:(i + 1) * M]
        count = 0
        j = 0
        while j <= len(block) - m:
            if np.array_equal(block[j:j + m], template):
                count += 1
                j += m
            else:
                j += 1
        chi_sq += (count - mu) ** 2 / sigma_sq

    p_value = gammaincc(N / 2.0, chi_sq / 2.0)
    return p_value


def overlapping_template(bits, m=9):
    """Test 8: Overlapping Template Matching Test"""
    n = len(bits)
    K = 5
    M = 1032
    N = 968
    if n < N * M:
        return 0.0

    lam = float(M - m + 1) / (2.0 ** m)
    eta = lam / 2.0
    
    pi = [0.0] * (K + 1)
    pi[0] = math.exp(-eta)
    
    def nchoosek(n_val, k_val):
        return math.comb(n_val, k_val)
        
    for u in range(1, K):
        sum_val = 0.0
        for k in range(1, u + 1):
            term = (eta ** k) / math.factorial(k) * nchoosek(u - 1, k - 1)
            sum_val += term
        pi[u] = math.exp(-eta) * (2.0 ** -u) * sum_val
    pi[K] = max(1.0 - sum(pi[:K]), 1e-10)

    freq = [0] * (K + 1)
    for i in range(N):
        block = bits[i * M:(i + 1) * M]
        count = 0
        for j in range(M - m + 1):
            if np.all(block[j:j + m] == 1):
                count += 1
        idx = min(count, K)
        freq[idx] += 1

    chi_sq = sum((freq[i] - N * pi[i]) ** 2 / (N * pi[i])
                 for i in range(K + 1) if N * pi[i] > 0)
    p_value = gammaincc(K / 2.0, chi_sq / 2.0)
    return p_value


def maurers_universal(bits):
    """Test 9: Maurer's Universal Statistical Test"""
    n = len(bits)
    L = 7
    if n < 387840:
        L = 6
    Q = 10 * (2 ** L)
    K = n // L - Q
    if K <= 0:
        return 0.0

    expected = {6: 5.2177052, 7: 6.1962507, 8: 7.1836656,
                9: 8.1764248, 10: 9.1723243}
    variance = {6: 2.954, 7: 3.125, 8: 3.238,
                9: 3.311, 10: 3.356}

    table = {}
    for i in range(Q):
        block_val = 0
        for j in range(L):
            block_val = (block_val << 1) | int(bits[i * L + j])
        table[block_val] = i + 1

    total = 0.0
    for i in range(Q, Q + K):
        block_val = 0
        for j in range(L):
            block_val = (block_val << 1) | int(bits[i * L + j])
        if block_val in table:
            total += math.log2(i + 1 - table[block_val])
        table[block_val] = i + 1

    fn = total / K
    c = 0.7 - 0.8 / L + (4 + 32.0 / L) * (K ** (-3.0 / L)) / 15.0
    sigma = c * math.sqrt(variance.get(L, 3.125) / K)
    p_value = erfc(abs(fn - expected.get(L, 6.1962507)) / (math.sqrt(2) * sigma))
    return p_value


def linear_complexity(bits, M=500):
    """Test 10: Linear Complexity Test"""
    n = len(bits)
    N = n // M
    if N == 0:
        return 0.0
    K = 6
    pi = [0.010417, 0.031250, 0.125000, 0.500000, 0.250000, 0.062500, 0.020833]

    def berlekamp_massey(s):
        """Berlekamp-Massey algorithm over GF(2)"""
        n_bm = len(s)
        # Use Python lists for correct GF(2) arithmetic
        c = [0] * n_bm
        b = [0] * n_bm
        c[0] = 1
        b[0] = 1
        L_val = 0
        m_val = -1
        for nn in range(n_bm):
            d = int(s[nn])
            for i in range(1, L_val + 1):
                d ^= (c[i] & int(s[nn - i]))
            d = d & 1  # Ensure GF(2)
            if d == 1:
                t = c[:]
                shift = nn - m_val
                for i in range(shift, n_bm):
                    c[i] ^= b[i - shift]
                if L_val <= nn // 2:
                    L_val = nn + 1 - L_val
                    m_val = nn
                    b = t[:]
        return L_val

    mu = M / 2.0 + (9.0 + (-1) ** (M + 1)) / 36.0 - (M / 3.0 + 2.0 / 9.0) / (2 ** M)

    freq = [0] * (K + 1)
    for i in range(N):
        block = bits[i * M:(i + 1) * M]
        lc = berlekamp_massey(block)
        T = (-1) ** M * (lc - mu) + 2.0 / 9.0
        if T <= -2.5:
            freq[0] += 1
        elif T <= -1.5:
            freq[1] += 1
        elif T <= -0.5:
            freq[2] += 1
        elif T <= 0.5:
            freq[3] += 1
        elif T <= 1.5:
            freq[4] += 1
        elif T <= 2.5:
            freq[5] += 1
        else:
            freq[6] += 1

    chi_sq = sum((freq[i] - N * pi[i]) ** 2 / (N * pi[i])
                 for i in range(K + 1) if N * pi[i] > 0)
    p_value = gammaincc(K / 2.0, chi_sq / 2.0)
    return p_value


def serial_test(bits, m=16):
    """Test 11: Serial Test"""
    n = len(bits)
    extended = np.concatenate([bits, bits[:m - 1]])

    def psi_sq(mm):
        counts = {}
        for i in range(n):
            pattern = 0
            for j in range(mm):
                pattern = (pattern << 1) | int(extended[i + j])
            counts[pattern] = counts.get(pattern, 0) + 1
        return (2 ** mm / n) * sum(v ** 2 for v in counts.values()) - n

    psi_m = psi_sq(m)
    psi_m1 = psi_sq(m - 1)
    psi_m2 = psi_sq(m - 2)
    del1 = psi_m - psi_m1
    del2 = psi_m - 2 * psi_m1 + psi_m2
    p1 = gammaincc(2 ** (m - 2), del1 / 2.0)
    p2 = gammaincc(2 ** (m - 3), del2 / 2.0)
    return min(p1, p2)


def approximate_entropy(bits, m=10):
    """Test 12: Approximate Entropy Test"""
    n = len(bits)

    def phi_m(mm):
        extended = np.concatenate([bits, bits[:mm - 1]])
        counts = {}
        for i in range(n):
            pattern = 0
            for j in range(mm):
                pattern = (pattern << 1) | int(extended[i + j])
            counts[pattern] = counts.get(pattern, 0) + 1
        c_values = [counts.get(i, 0) / n for i in range(2 ** mm)]
        return sum(c * math.log(c) if c > 0 else 0 for c in c_values)

    phi1 = phi_m(m)
    phi2 = phi_m(m + 1)
    apen = phi1 - phi2
    chi_sq = 2.0 * n * (math.log(2) - apen)
    p_value = gammaincc(2 ** (m - 1), chi_sq / 2.0)
    return p_value


def cumulative_sums(bits):
    """Test 13: Cumulative Sums Test"""
    n = len(bits)
    x = 2 * bits.astype(np.float64) - 1
    S = np.cumsum(x)
    z = float(np.max(np.abs(S)))

    total = 0.0
    start = int((-n / z + 1) / 4)
    end = int((n / z - 1) / 4) + 1
    for k in range(start, end + 1):
        t1_arg = (4 * k + 1) * z / math.sqrt(n)
        t2_arg = (4 * k - 1) * z / math.sqrt(n)
        from scipy.stats import norm
        total += norm.cdf(t1_arg) - norm.cdf(t2_arg)
    p_value = 1.0 - total
    # Backward
    S_rev = np.cumsum(x[::-1])
    z_rev = float(np.max(np.abs(S_rev)))
    total_rev = 0.0
    start = int((-n / z_rev + 1) / 4)
    end = int((n / z_rev - 1) / 4) + 1
    for k in range(start, end + 1):
        t1_arg = (4 * k + 1) * z_rev / math.sqrt(n)
        t2_arg = (4 * k - 1) * z_rev / math.sqrt(n)
        total_rev += norm.cdf(t1_arg) - norm.cdf(t2_arg)
    p_rev = 1.0 - total_rev

    return min(p_value, p_rev)


def random_excursion(bits):
    """Test 14: Random Excursions Test"""
    n = len(bits)
    x = 2 * bits.astype(np.int64) - 1
    S = np.concatenate([[0], np.cumsum(x), [0]])

    cycles = []
    start = 0
    for i in range(1, len(S)):
        if S[i] == 0:
            cycles.append(S[start:i + 1])
            start = i
    J = len(cycles)
    if J < 500:
        return 0.5  # Not enough cycles

    states = [-4, -3, -2, -1, 1, 2, 3, 4]
    pi_table = [
        [0.5, 0.25, 0.125, 0.0625, 0.0312, 0.0312],
        [0.75, 0.0625, 0.0469, 0.0352, 0.0264, 0.0791],
        [0.8333, 0.0278, 0.0231, 0.0193, 0.0161, 0.0804],
        [0.875, 0.0156, 0.0137, 0.0120, 0.0105, 0.0733],
    ]

    p_values = []
    for idx, state in enumerate(states):
        pi_idx = min(abs(state) - 1, 3)
        pi = pi_table[pi_idx]
        freq = [0] * 6
        for cycle in cycles:
            count = np.sum(cycle == state)
            if count >= 5:
                freq[5] += 1
            else:
                freq[int(count)] += 1
        chi_sq = sum((freq[k] - J * pi[k]) ** 2 / (J * pi[k])
                     for k in range(6) if J * pi[k] > 0)
        p_val = gammaincc(5 / 2.0, chi_sq / 2.0)
        p_values.append(p_val)

    return min(p_values) if p_values else 0.0


def random_excursion_variant(bits):
    """Test 15: Random Excursions Variant Test"""
    n = len(bits)
    x = 2 * bits.astype(np.int64) - 1
    S = np.concatenate([[0], np.cumsum(x), [0]])

    J = np.sum(S[1:] == 0)
    if J < 500:
        return 0.5

    states = list(range(-9, 0)) + list(range(1, 10))
    p_values = []
    for state in states:
        count = np.sum(S == state)
        p_val = erfc(abs(count - J) / math.sqrt(2 * J * (4 * abs(state) - 2)))
        p_values.append(p_val)

    return min(p_values) if p_values else 0.0


# ============================================================
# Main
# ============================================================
def main():
    # Default data file - change this to test different files
    default_file = "putty.txt"
    # default_file = "r_bits_single_row.txt"
    input_file = sys.argv[1] if len(sys.argv) > 1 else default_file
    test_bits = 2_000_000  # NIST recommends 1,000,000 bits minimum

    print("=" * 65)
    print("  NIST SP 800-22 Rev 1a Statistical Test Suite")
    print("  Custom Implementation - All 15 Tests")
    print("=" * 65)

    if not os.path.exists(input_file):
        print(f"\nERROR: '{input_file}' not found!")
        print(f"Make sure the file is in the same directory as this script,")
        print(f"or provide the full path as a command-line argument.")
        sys.exit(1)

    print(f"\nInput file  : {input_file}")

    # Read text file and filter only '0' and '1' characters
    print("\n[1/2] Loading binary data from text file...")
    with open(input_file, 'r') as f:
        raw_text = f.read()
    data = ''.join(c for c in raw_text if c in '01')
    total_bits = len(data)
    print(f"      Total bits found: {total_bits:,}")

    if total_bits == 0:
        print("\nERROR: No binary data (0s and 1s) found in the file!")
        sys.exit(1)

    # Use the first 'test_bits' bits (or all if less available)
    actual_test_bits = min(test_bits, total_bits)
    if total_bits < test_bits:
        print(f"      WARNING: File has {total_bits:,} bits, less than "
              f"recommended {test_bits:,}. Using all available bits.")
    else:
        print(f"      Using first {actual_test_bits:,} bits for testing")

    bits = np.array([int(c) for c in data[:actual_test_bits]], dtype=np.int64)
    ones = int(np.sum(bits))
    print(f"      Ones: {ones:,} | Zeros: {len(bits)-ones:,} | "
          f"Ratio: {ones/len(bits):.6f}")

    print(f"\n[2/2] Running all 15 NIST SP 800-22 tests...")
    print("-" * 65)

    tests = [
        ("1.  Frequency (Monobit)", lambda b: frequency_monobit(b)),
        ("2.  Frequency Within Block", lambda b: frequency_within_block(b)),
        ("3.  Runs", lambda b: runs_test(b)),
        ("4.  Longest Run of Ones", lambda b: longest_run_ones(b)),
        ("5.  Binary Matrix Rank", lambda b: binary_matrix_rank(b)),
        ("6.  Discrete Fourier Transform", lambda b: dft_test(b)),
        ("7.  Non-Overlapping Template", lambda b: non_overlapping_template(b)),
        ("8.  Overlapping Template", lambda b: overlapping_template(b)),
        ("9.  Maurer's Universal", lambda b: maurers_universal(b)),
        ("10. Linear Complexity", lambda b: linear_complexity(b)),
        ("11. Serial", lambda b: serial_test(b)),
        ("12. Approximate Entropy", lambda b: approximate_entropy(b)),
        ("13. Cumulative Sums", lambda b: cumulative_sums(b)),
        ("14. Random Excursion", lambda b: random_excursion(b)),
        ("15. Random Excursion Variant", lambda b: random_excursion_variant(b)),
    ]

    results = []
    print(f"\n{'Test Name':<40} {'P-Value':>10} {'Result':>8}")
    print("-" * 65)

    for name, test_fn in tests:
        try:
            p = test_fn(bits)
            passed = p >= 0.01
            status = "PASS" if passed else "FAIL"
            results.append((name, p, passed))
            print(f"  {name:<38} {p:>10.6f} {status:>8}")
        except Exception as e:
            results.append((name, 0.0, False))
            print(f"  {name:<38} {'ERROR':>10} {'FAIL':>8}  ({e})")

    pass_count = sum(1 for _, _, p in results if p)
    fail_count = len(results) - pass_count
    print("-" * 65)
    print(f"\n  SUMMARY: {pass_count}/{len(results)} tests PASSED, "
          f"{fail_count}/{len(results)} tests FAILED")

    if fail_count == 0:
        print("\n  [OK] ALL TESTS PASSED!")
    elif fail_count <= 2:
        print("\n  [WARN] Minor failures - may be acceptable")
    else:
        print("\n  [FAIL] Multiple test failures detected")
    print("\n" + "=" * 65)

    # Save results to file
    results_file = os.path.splitext(input_file)[0] + "_nist_results.txt"
    with open(results_file, 'w') as f:
        f.write("NIST SP 800-22 Rev 1a Statistical Test Results\n")
        f.write(f"Input: {input_file} | Bits tested: {actual_test_bits:,}\n")
        f.write(f"Ones: {ones:,} | Zeros: {len(bits)-ones:,} | "
                f"Ratio: {ones/len(bits):.6f}\n")
        f.write("=" * 65 + "\n")
        for name, p, passed in results:
            f.write(f"  {name:<38} {p:>10.6f} "
                    f"{'PASS' if passed else 'FAIL':>8}\n")
        f.write("-" * 65 + "\n")
        f.write(f"SUMMARY: {pass_count}/{len(results)} PASSED\n")
    print(f"  Results saved to: {results_file}")


if __name__ == "__main__":
    main()

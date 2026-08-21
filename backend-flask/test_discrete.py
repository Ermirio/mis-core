import pandas as pd
import numpy as np

# Test 1: Discrete Data (like estado)
data1 = [1, 1, 1, 2, 2, 4, 4, 4, 4, 1]
series1 = pd.Series(data1)
n_unique1 = int(series1.nunique())
count1 = int(series1.count())
is_discrete1 = bool(n_unique1 <= 15 or n_unique1 < (count1 * 0.05))

if is_discrete1:
    val_counts = series1.value_counts().sort_index()
    hist_counts = val_counts.tolist()
    bins = val_counts.index.tolist()
    print("Test 1 (Discrete): Passed. Counts:", hist_counts, "Bins:", bins)
else:
    print("Test 1 Failed.")

# Test 2: Continuous Data (like speed)
data2 = np.random.normal(100, 15, 1000)
series2 = pd.Series(data2)
n_unique2 = int(series2.nunique())
count2 = int(series2.count())
is_discrete2 = bool(n_unique2 <= 15 or n_unique2 < (count2 * 0.05))

if not is_discrete2:
    hist, bin_edges = np.histogram(series2, bins='auto')
    print("Test 2 (Continuous): Passed. Bins format:", bin_edges[:3], "...")
else:
    print("Test 2 Failed.")

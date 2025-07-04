import streamlit as st
import pandas as pd
import numpy as np
import scipy
import scipy.stats as stats
import sklearn
#import pywt
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from datetime import timedelta
#import collections
from collections import defaultdict
from scipy.fft import rfft, rfftfreq
from scipy.signal import find_peaks, peak_widths
from scipy.signal import hilbert
import math
from sklearn.metrics.pairwise import cosine_similarity
from matplotlib import gridspec
#from thre_fused_tdi_module import plot_thre_fused_tdi
#import morlet_phase_enhancement
#from morlet_phase_enhancement import morlet_phase_panel

# ======================= CONFIG ==========================
st.set_page_config(page_title="CYA Quantum Tracker", layout="wide")
st.title("🔥 CYA MOMENTUM TRACKER: Phase 1 + 2 + 3 + 4")

# Create a container for the floating add round button
floating_container = st.empty()
latest_rds = None
latest_delta = None

# ================ SESSION STATE INIT =====================
if "roundsc" not in st.session_state:
    st.session_state.roundsc = []
if "ga_pattern" not in st.session_state:
    st.session_state.ga_pattern = None
if "forecast_msi" not in st.session_state:
    st.session_state.forecast_msi = []
if "completed_cycles" not in st.session_state:
    st.session_state.completed_cycles = 0
if "last_position" not in st.session_state:
    st.session_state.last_position = 0
if "current_mult" not in st.session_state:
    st.session_state.current_mult = 2.0

if "alignment_score_history" not in st.session_state:
    st.session_state["alignment_score_history"] = []

# ================ CONFIGURATION SIDEBAR ==================
with st.sidebar:
    st.header("⚙️ QUANTUM PARAMETERS")
    WINDOW_SIZE = st.slider("MSI Window Size", 5, 100, 20)
    PINK_THRESHOLD = st.number_input("Pink Threshold", value=10.0)
    STRICT_RTT = st.checkbox("Strict RTT Mode", value=False)
    selected_window = st.sidebar.selectbox(
    "Select Fibonacci spirals Window",
    options=[3, 5, 8, 13, 21, 34, 55],
    index=5  # default to 34
    )
    fib_window = st.sidebar.selectbox(
    "Fibonacci Envelope Window Size",
    options=[5, 8, 13, 21, 34],
    index=2  # default to 13
    )

    st.sidebar.subheader("FLP Projection Layers")
    fib_layer_options = [3, 5, 8, 13, 21, 34, 55]
    selected_fib_layers = st.sidebar.multiselect(
        "Choose Fibonacci Gaps (in rounds) for Projection",
        options=fib_layer_options,
        default=[5, 8, 13, 21, 34]
    )

    st.sidebar.subheader("MSI Multi-Window Settings")

    default_fib_windows = [3, 5, 8, 13, 21, 34]
    
    selected_msi_windows = st.sidebar.multiselect(
        "Select MSI Window Sizes (Fibonacci)",
        options=default_fib_windows,
        default=[13, 21]
    )
    st.sidebar.subheader("🧭 Set Weights for Each MSI Window")

    window_weights = []
    for window in selected_msi_windows:
        weight = st.sidebar.slider(
            f"Weight for MSI {window}",
            min_value=0.0,
            max_value=3.0,
            value=1.0,
            step=0.1
        )
        window_weights.append(weight)

    # ---------------------------------
    # Sidebar Toggles for Fib Retracement
    # ---------------------------------
    st.sidebar.subheader("📐 Fibonacci Retracement Settings")
    fib_msi_window = st.sidebar.selectbox(
    "MSI Window for Fib Retracement",
    options=[3, 5, 8, 13, 21, 34, 55],
    index=2
    )

    fib_lookback_window = st.sidebar.selectbox(
    "Lookback Window (Rounds)",
    options=[3, 5, 8, 13, 21, 34, 55],
    index=3
    )
    
    show_fib_retracement = st.sidebar.checkbox(
        "📏 Show Fib Retracements", value=True
    )
    show_fib_ext = st.sidebar.checkbox(
        "📏 Show Fib extentsions", value=True
    )

    st.sidebar.subheader("📐 Multi-Window Fibonacci Analysis")
    multi_fib_windows = st.sidebar.multiselect(
        "Select Fib Lookback Windows",
        options=[5, 8, 13, 21, 34, 55],
        default=[13, 21, 34]
    )
    show_multi_fib_analysis = st.sidebar.checkbox(
        "📊 Show Multi-Window Fib Analysis",
        value=True
    )

    st.sidebar.subheader("🎯 Fib Alignment Score Engine Settings")

    fib_alignment_window = st.sidebar.selectbox(
        "Lookback Window (Rounds)",
        options=[21, 34, 55],
        index=1
    )
    
    fib_alignment_tolerance = st.sidebar.slider(
        "Gap Tolerance",
        min_value=0.5,
        max_value=3.0,
        value=1.0,
        step=0.1
    )
    st.header("📉 Indicator Visibility")

    show_supertrend = st.checkbox("🟢 Show SuperTrend", value=True)
    show_ichimoku   = st.checkbox("☁️ Show Ichimoku (Tenkan/Kijun)", value=True)
    show_fibo   = st.checkbox("💫 Show FIB modules", value=True)
    show_bb   = st.checkbox("🌈 Show BB bands", value=True)
    show_fibo_bands   = st.checkbox("📏 Show FIB  bands", value=True)
    show_msi_res = st.checkbox("💹 MSI Res", value=True)

    st.header("📊 PANEL TOGGLES")
    FAST_ENTRY_MODE = st.checkbox("⚡ Fast Entry Mode", value=False)
    show_thre = st.checkbox("🌀 THRE Panel", value=True)
    
    
    show_fpm = st.checkbox("🧬 FPM Panel", value=True)
    show_anchor = st.checkbox("🔗 Fractal Anchor", value=True)
    
    if st.button("🔄 Full Reset", help="Clear all historical data"):
        st.session_state.roundsc = []
        st.rerun()
        
    # Clear cached functions
    if st.button("🧹 Clear Cache", help="Force harmonic + MSI recalculation"):
        st.cache_data.clear()  # Streamlit's built-in cache clearer
        st.success("Cache cleared — recalculations will run fresh.")

# =================== ADVANCED HELPER FUNCTIONS ========================
@st.cache_data
def bollinger_bands(series, window, num_std=2):
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std()
    upper_band = rolling_mean + num_std * rolling_std
    lower_band = rolling_mean - num_std * rolling_std
    return rolling_mean, upper_band, lower_band

@st.cache_data
def detect_dominant_cycle(scores):
    N = len(scores)
    if N < 20:
        return None
    T = 1
    yf = rfft(scores - np.mean(scores))
    xf = rfftfreq(N, T)
    dominant_freq = xf[np.argmax(np.abs(yf[1:])) + 1]
    if dominant_freq == 0:
        return None
    return round(1 / dominant_freq)

@st.cache_data
def get_phase_label(position, cycle_length):
    pct = (position / cycle_length) * 100
    if pct <= 16:
        return "Birth Phase", pct
    elif pct <= 33:
        return "Ascent Phase", pct
    elif pct <= 50:
        return "Peak Phase", pct
    elif pct <= 67:
        return "Post-Peak", pct
    elif pct <= 84:
        return "Falling Phase", pct
    else:
        return "End Phase", pct


    
FIB_NUMBERS = [3, 5, 8, 13, 21, 34, 55]
FIBONACCI_NUMBERS = [3, 5, 8, 13, 21, 34, 55]
ENVELOPE_MULTS = [1.0, 1.618, 2.618]
FIB_GAPS = [3, 5, 8, 13, 21, 34, 55]

class NaturalFibonacciSpiralDetector:
    def __init__(self, df, window_size=34):
        self.df = df.tail(window_size).reset_index(drop=True)
        self.df["round_index"] = self.df.index
        self.window_size = window_size
        self.spiral_candidates = []

    def detect_spirals(self):
        score_types = [-1, 1, 2]  # Blue, Purple, Pink
        scores = self.df["score"].fillna(0).values

        for score_type in score_types:
            idxs = [i for i, val in enumerate(scores) if val == score_type]

            # Check for Fibonacci Gaps within this score type
            for i in range(len(idxs)):
                for j in range(i + 1, len(idxs)):
                    gap = idxs[j] - idxs[i]
                    if gap in FIB_NUMBERS:
                        self.spiral_candidates.append({
                            "score_type": score_type,
                            "start_idx": idxs[i],
                            "end_idx": idxs[j],
                            "gap": gap,
                            "center_idx": (idxs[i] + idxs[j]) // 2
                        })

        return self._select_strongest_spirals()

    def _select_strongest_spirals(self, max_spirals=3):
        centers = defaultdict(int)

        # Count how often each center index appears
        for candidate in self.spiral_candidates:
            centers[candidate["center_idx"]] += 1

        # Sort by frequency (descending)
        top_centers = sorted(centers.items(), key=lambda x: -x[1])[:max_spirals]
        spiral_centers = []

        for center_idx, freq in top_centers:
            ts = self.df.loc[center_idx, "timestamp"]
            label = self._label_score(self.df.loc[center_idx, "score"])
            spiral_centers.append({
                "center_index": center_idx,
                "round_index": center_idx,
                "timestamp": ts,
                "score_type": self.df.loc[center_idx, "score"],
                "label": label,
                "confirmations": freq
            })

        return spiral_centers

    def _label_score(self, s):
        return { -1: "Blue", 1: "Purple", 2: "Pink" }.get(s, "Unknown")
    
def get_spiral_echoes(spiral_centers, df, gaps=[3, 5, 8, 13]):
    echoes = []

    for sc in spiral_centers:
        base_idx = sc["round_index"]

        for gap in gaps:
            echo_idx = base_idx + gap
            if echo_idx < len(df):
                echoes.append({
                    "echo_round": echo_idx,
                    "source_round": base_idx,
                    "timestamp": df.loc[echo_idx, "timestamp"],
                    "source_label": sc["label"],
                    "gap": gap
                })

    return echoes    

def project_true_forward_flp(spiral_centers, fib_layers=[6, 12, 18, 24, 30], max_rounds=None):
    """
    Create a forward projection map from spiral centers using Fibonacci gaps.
    Returns a list of watchlist targets.
    """

    watchlist = []

    for sc in spiral_centers:
        base_idx = sc["round_index"]

        for gap in fib_layers:
            target_idx = base_idx + gap
            if max_rounds is None or target_idx < max_rounds:
                watchlist.append({
                    "source_round": base_idx,
                    "source_label": sc["label"],
                    "gap": gap,
                    "target_round": target_idx
                })

    return watchlist

def compute_resonance(row, selected_windows, weights=None):
    if weights is None:
        weights = [1] * len(selected_windows)
    weighted_sum = 0
    weight_total = sum(weights)
    
    for i, window in enumerate(selected_windows):
        sign_col = f"sign_{window}"
        weighted_sum += row[sign_col] * weights[i]
    
    resonance_score = weighted_sum / weight_total
    return round(resonance_score, 2) 

def compute_slope_agreement(slopes):
    """Percentage of slopes in the same direction."""
    signs = [np.sign(s) for s in slopes]
    pos_count = signs.count(1)
    neg_count = signs.count(-1)
    return round(max(pos_count, neg_count) / len(signs), 2)

def compute_ordering_score(msi_values):
    """Measures hierarchy — are shorter windows leading longer?"""
    mismatches = sum(1 for i in range(len(msi_values)-1) if msi_values[i] < msi_values[i+1])
    return round(1 - (mismatches / (len(msi_values) - 1)), 2)

def detect_slope_inflections(slope_series):
    """Counts number of sign flips in slopes."""
    inflections = 0
    for i in range(1, len(slope_series)):
        if np.sign(slope_series[i]) != np.sign(slope_series[i-1]):
            inflections += 1
    return inflections

def compute_weighted_energy(msi_values, window_sizes):
    weights = []
    for w in window_sizes:
        if w <= 8:
            weights.append(0.5)
        elif w <= 21:
            weights.append(1.0)
        else:
            weights.append(1.5)
    weighted = [v * w for v, w in zip(msi_values, weights)]
    return sum(weighted) / sum(weights)

def dynamic_feb_bands(ma_value, phase_score):
    """Phase-weighted dynamic envelope bands."""
    if phase_score >= 0.75:
        mults = ENVELOPE_MULTS
    elif phase_score >= 0.5:
        mults = [0.85, 1.3, 2.0]
    else:
        mults = [0.7, 1.0, 1.5]
    return [round(ma_value * m, 3) for m in mults]

def check_envelope_breakouts(msi_value, bands):
    """Flags for each breakout level."""
    return {
        "breakout_1": msi_value >= bands[0],
        "breakout_1_618": msi_value >= bands[1],
        "breakout_2_618": msi_value >= bands[2],
    }

def compute_volatility(series, window=5):
    """Std deviation over recent rounds."""
    return round(series[-window:].std(), 3)

def compute_gap_since_last_pink(current_index, last_pink_index):
    """How many rounds since last surge/pink?"""
    if last_pink_index is None:
        return None
    return max(1, current_index - last_pink_index)

def fib_gap_alignment(gap):
    """How closely does gap match Fibonacci numbers?"""
    if gap is None:
        return 0.5
    closest = min(FIBONACCI_NUMBERS, key=lambda x: abs(x - gap))
    alignment = 1 - (abs(closest - gap) / max(FIBONACCI_NUMBERS))
    return round(max(0, alignment), 2)

def map_phase_label(score):
    if score >= 0.75:
        return "Ascent"
    elif score >= 0.5:
        return "Birth"
    elif 0.4 <= score < 0.5:
        return "Peak"
    elif 0.25 <= score < 0.4:
        return "Post-Peak"
    else:
        return "Collapse"

def compute_custom_phase_score(
    current_round_index,
    last_pink_index,
    msi_values,
    slopes,
    window_sizes
):
    # Ordering Score
    ordering_score = compute_ordering_score(msi_values)
    
    # Slope Agreement
    slope_alignment = compute_slope_agreement(current_slopes)
    
    # Weighted Energy
    weighted_energy = compute_weighted_energy(msi_values, window_sizes)

    gap = compute_gap_since_last_pink(current_round_index, last_pink_index)
    fib_alignment = fib_gap_alignment(gap)

     # Final Phase Score (tunable weights)
    phase_score = (
        ordering_score * 0.3 +
        slope_alignment * 0.2 +
        weighted_energy * 0.3 +
        fib_alignment * 0.2
    )
    phase_score = round(min(max(phase_score, 0.0), 1.0), 3)

    phase_label = map_phase_label(phase_score)

    return {
        'ordering_score': ordering_score,
        'slope_alignment': slope_alignment,
        'weighted_energy': weighted_energy,
        "gap_since_last_pink": gap,
        "fib_gap_alignment": fib_alignment,
        'phase_score': phase_score,
        'phase_label': phase_label
    }

def estimate_regime_length_class(gap):
    """Classifies regime by gap size."""
    if gap is None:
        return "Unknown", None
    if gap <= 8:
        return "Micro", 8
    elif gap <= 21:
        return "Meso", 21
    else:
        return "Macro", 34

def compute_spiral_projection_windows(current_round, fib_numbers=FIBONACCI_NUMBERS):
    """Predict future likely shift windows."""
    return [current_round + f for f in fib_numbers]

def detect_trap_cluster_state(recent_gaps, fib_numbers=FIBONACCI_NUMBERS):
    """
    Determines if recent pink gaps are clustering tightly in Fibonacci intervals,
    which suggests bait/trap regimes designed to harvest bets.
    """
    if len(recent_gaps) < 3:
        return "Unknown"

    # Count how many gaps are in small Fib range
    tight_cluster_count = sum(1 for g in recent_gaps if g in [3,5,8])
    if tight_cluster_count >= 2:
        return "High Trap Probability"

    # Check for expansion pattern
    expansion_gaps = [g for g in recent_gaps if g > 13]
    if len(expansion_gaps) >= 2:
        return "Expansion Zone (Dry Trap)"

    return "Neutral"


def classify_phase_label(slope_agreement, ordering_score, inflections, phase_score, volatility):
    """
    Label the current phase of the regime based on MSI slope structure, inflections,
    and volatility.
    """
    if slope_agreement >= 0.8 and ordering_score >= 0.75 and inflections <= 1 and phase_score >= 0.75:
        return "Ascent"

    if slope_agreement >= 0.5 and ordering_score >= 0.5 and inflections <= 2 and phase_score >= 0.5:
        return "Birth"

    if inflections >= 3 or volatility > 1.0:
        return "Peak / Range"

    if slope_agreement <= 0.2 and ordering_score <= 0.2:
        return "Collapse / Blue Train"

    return "Unclassified"

def classify_regime_state(
    current_round_index,
    last_pink_index,
    recent_scores,
    current_msi_values,
    current_slopes,
    slope_history_series,
    phase_score,
    recent_gap_history
):
    """
    Complete regime classification for current round.
    """

    # Core Slope Features
    slope_agreement = compute_slope_agreement(current_slopes)
    ordering_score = compute_ordering_score(current_msi_values)
    inflections = sum([detect_slope_inflections(s) for s in slope_history_series])
    volatility = compute_volatility(recent_scores)

    # Envelope Breakout Detection
    ma_value = np.mean(recent_scores)
    bands = dynamic_feb_bands(ma_value, phase_score)
    msi_mean_value = np.mean(current_msi_values)
    envelope_flags = check_envelope_breakouts(msi_mean_value, bands)

    # Gap and Fibonacci Alignment
    gap = compute_gap_since_last_pink(current_round_index, last_pink_index)
    gap_alignment = fib_gap_alignment(gap)
    regime_type, estimated_length = estimate_regime_length_class(gap)
    current_pos_in_regime = gap if gap else 0
    rounds_to_shift = estimated_length - current_pos_in_regime if estimated_length else None

    spiral_forecast = compute_spiral_projection_windows(current_round_index)
    trap_cluster_state = detect_trap_cluster_state(recent_gap_history)

    # Phase Classification
    phase_label = classify_phase_label(slope_agreement, ordering_score, inflections, phase_score, volatility)

    # Final Result
    result = {
        "regime_type": regime_type,
        "estimated_length": estimated_length,
        "phase_label": phase_label,
        "phase_score": phase_score,
        "current_round_in_regime": current_pos_in_regime,
        "rounds_to_next_shift": rounds_to_shift,
        "gap_since_last_pink": gap,
        "fib_gap_alignment": gap_alignment,
        "spiral_projection_windows": spiral_forecast,
        "trap_cluster_state": trap_cluster_state,
        "slope_agreement": slope_agreement,
        "ordering_score": ordering_score,
        "slope_inflections": inflections,
        "volatility": volatility,
        "envelope_flags": envelope_flags
    }

    return result

# ============================
# MSI FIBONACCI RETRACEMENT MODULE
# ============================

def calculate_fibonacci_retracements(msi_series, fib_lookback_window):
    """
    Calculate Fibonacci retracement and extension levels
    from swing high/low over user-specified lookback window.
    """
    recent = msi_series.tail(fib_lookback_window).dropna()
    if recent.empty or len(recent) < 2:
        return None

    swing_high = recent.max()
    swing_low = recent.min()

    if swing_high == swing_low:
        # Avoid division by zero when flat
        return None

    # Compute standard retracement levels
    retracements = {
        "0.0": round(swing_low, 3),
        "0.236": round(swing_high - 0.236 * (swing_high - swing_low), 3),
        "0.382": round(swing_high - 0.382 * (swing_high - swing_low), 3),
        "0.5": round((swing_high + swing_low) / 2, 3),
        "0.618": round(swing_high - 0.618 * (swing_high - swing_low), 3),
        "0.786": round(swing_high - 0.786 * (swing_high - swing_low), 3),
        "1.0": round(swing_high, 3)
    }

    # Compute extension levels
    range_ = swing_high - swing_low
    extensions = {
        "1.618": round(swing_high + 0.618 * range_, 3),
        "2.618": round(swing_high + 1.618 * range_, 3),
        "3.618": round(swing_high + 2.618 * range_, 3),
        "-0.618": round(swing_low - 0.618 * range_, 3),
        "-1.618": round(swing_low - 1.618 * range_, 3),
        "-2.618": round(swing_low - 2.618 * range_, 3)
    }

    return retracements, extensions, swing_high, swing_low

def compute_multi_window_fib_retracements(df, msi_column, windows):
    """
    For each selected lookback window, compute retracement levels.
    Returns a dict of window -> retracement levels.
    """
    results = {}
    for w in windows:
        res = calculate_fibonacci_retracements(df[msi_column], w)
        if res:
            retrace, ext, high, low = res
            results[w] = {
                "retracements": retrace,
                "extensions": ext,
                "swing_high": high,
                "swing_low": low
            }
    return results

def compute_fib_alignment_score(df, fib_threshold=10.0, lookback_window=34, tolerance=1.0):
    """
    Compute a score 0–1 for how well the sequence of recent 'pink' rounds
    aligns to Fibonacci intervals.
    #- fib_threshold: multiplier value considered a pink.
    #- lookback_window: number of rounds to analyze.
    #- tolerance: +/- range allowed when matching Fib gaps.
    """
    if len(df) < lookback_window:
        return None, []

    recent_df = df.tail(lookback_window).copy()
    recent_df = recent_df.reset_index(drop=True)
    recent_df['relative_index'] = recent_df.index

    # Find pink rounds in recent window
    pink_indexes = recent_df[recent_df['multiplier'] >= fib_threshold]['relative_index'].tolist()

    if len(pink_indexes) < 2:
        return 0.0, []

    # Compute gaps between pink rounds
    gaps = [pink_indexes[i+1] - pink_indexes[i] for i in range(len(pink_indexes)-1)]

    # For each gap, score it by closeness to Fib sequence
    scores = []
    for gap in gaps:
        diffs = [abs(gap - fib) for fib in FIB_GAPS]
        min_diff = min(diffs)
        if min_diff <= tolerance:
            # Perfect or near-perfect match
            scores.append(1.0)
        else:
            # Score decays with distance
            decay = np.exp(-min_diff / tolerance)
            scores.append(decay)

    # Average score
    if scores:
        alignment_score = np.clip(np.mean(scores), 0, 1)
    else:
        alignment_score = 0.0

    return round(alignment_score, 3), gaps

class QuantumFibonacciEntanglement:
    def __init__(self, multiplier_sequence: list):
        """
        PURE standalone Fibonacci quantum detector
        Only requires raw multiplier sequence
        """
        self.multipliers = multiplier_sequence
        self.pure_ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    
    def fib_wavelet_analysis(self):
        """Measure casino's Fib sequence manipulation"""
        if len(self.multipliers) < 3:
            return 0.0  # Insufficient data
        
        actual_ranges = []
        fib_lengths = [3, 5, 8, 13, 21]
        
        for fib in fib_lengths:
            if len(self.multipliers) >= fib:
                # Analyze last 'fib' rounds
                segment = self.multipliers[-fib:]
                actual_range = max(segment) - min(segment)
                actual_ranges.append(actual_range)
        
        if not actual_ranges:
            return 0.0
            
        avg_range = sum(actual_ranges) / len(actual_ranges)
        normalized_ranges = [r / avg_range for r in actual_ranges]
        
        decoherence = 0
        for i in range(min(len(normalized_ranges), 5)):  # First 5 ratios
            decoherence += abs(normalized_ranges[i] - self.pure_ratios[i])
            
        return decoherence / 5  # Normalized 0-1 score

    def golden_phase_lock(self, window=8):
        """Detect golden ratio violations"""
        if len(self.multipliers) < window or window < 2:
            return False
            
        recent = self.multipliers[-window:]
        deviations = []
        
        for i in range(1, len(recent)):
            ratio = recent[i] / recent[i-1]
            # Measure deviation from golden ratio (1.618)
            deviation = abs(ratio - 1.618) / 1.618  # Relative error
            deviations.append(deviation)
        
        avg_deviation = sum(deviations) / len(deviations)
        return avg_deviation > 0.25  # Threshold for violation

    def entangled_fib_prediction(self):
        """Quantum forecast using only multipliers"""
        if len(self.multipliers) < 8:
            return "NEUTRAL"
        
        # Directly calculate MSI-like scores
        msi_3 = sum(1 for m in self.multipliers[-3:] if m > 1.0)
        msi_5 = sum(1 for m in self.multipliers[-5:] if m > 1.0)
        msi_8 = sum(1 for m in self.multipliers[-8:] if m > 1.0)
        
        # Quantum prediction equation (Golden Ratio based)
        φ = (1 + math.sqrt(5)) / 2  # 1.618...
        prediction = msi_5 * φ - msi_3
        
        if prediction > 1.618 * msi_8:
            return "SURGE_IMMINENT"
        elif prediction < 0.382 * msi_8:
            return "TRAP_DEPLOYING"
        return "NEUTRAL"


@st.cache_data
def calculate_purple_pressure(df, window=10):
    recent = df.tail(window)
    purple_scores = recent[recent['type'] == 'Purple']['score']
    if len(purple_scores) == 0:
        return 0
    return purple_scores.sum() / window

@st.cache_data
def calculate_blue_decay(df, window=10):
    recent = df.tail(window)
    blue_scores = recent[recent['type'] == 'Blue']['multiplier']
    if len(blue_scores) == 0:
        return 0
    decay = np.mean([2.0 - b for b in blue_scores])  # The lower the blue, the higher the decay
    return decay * (len(blue_scores) / window)

@st.cache_data
def compute_tpi(df, window=10):
    pressure = calculate_purple_pressure(df, window)
    decay = calculate_blue_decay(df, window)
    return round(pressure - decay, 2)

@st.cache_data
def rrqi(df, window=30):
    recent = df.tail(window)
    blues = len(recent[recent['type'] == 'Blue'])
    purples = len(recent[recent['type'] == 'Purple'])
    pinks = len(recent[recent['type'] == 'Pink'])
    quality = (purples + 2*pinks - blues) / window
    return round(quality, 2)
    
@st.cache_data    
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
    
@st.cache_data 
def compute_supertrend(df, period=10, multiplier=2.0, source="msi"):
        df = df.copy()
        src = df[source]
        hl2 = src  # substitute for high+low/2
    
        # True range approximation
        df['prev_close'] = src.shift(1)
        df['tr'] = abs(src - df['prev_close'])
        df['atr'] = df['tr'].rolling(window=period).mean()
    
        # Bands
        df['upper_band'] = hl2 - multiplier * df['atr']
        df['lower_band'] = hl2 + multiplier * df['atr']
    
        # Initialize trend
        trend = [1]  # start with uptrend
    
        for i in range(1, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i - 1]
    
            upper_band = max(curr['upper_band'], prev['upper_band']) if prev['prev_close'] > prev['upper_band'] else curr['upper_band']
            lower_band = min(curr['lower_band'], prev['lower_band']) if prev['prev_close'] < prev['lower_band'] else curr['lower_band']
    
            if trend[-1] == -1 and curr['prev_close'] > lower_band:
                trend.append(1)
            elif trend[-1] == 1 and curr['prev_close'] < upper_band:
                trend.append(-1)
            else:
                trend.append(trend[-1])
    
            df.at[df.index[i], 'upper_band'] = upper_band
            df.at[df.index[i], 'lower_band'] = lower_band
    
        df["trend"] = trend
        df["supertrend"] = np.where(df["trend"] == 1, df["upper_band"], df["lower_band"])
        df["buy_signal"] = (df["trend"] == 1) & (pd.Series(trend).shift(1) == -1)
        df["sell_signal"] = (df["trend"] == -1) & (pd.Series(trend).shift(1) == 1)
    
        return df
    




    
@st.cache_data
def multi_harmonic_resonance_analysis(df, num_harmonics=5):
    scores = df["score"].fillna(0).values
    N = len(scores)
    yf = rfft(scores - np.mean(scores))
    xf = rfftfreq(N, 1)
    amplitudes = np.abs(yf)
    top_indices = amplitudes.argsort()[-num_harmonics:][::-1] if len(amplitudes) >= num_harmonics else amplitudes.argsort()
    resonance_matrix = np.zeros((num_harmonics, num_harmonics))
    harmonic_waves = []
    
    for i, idx in enumerate(top_indices):
        if i < len(xf) and i < len(yf):
            freq = xf[idx]
            phase = np.angle(yf[idx])
            wave = np.sin(2 * np.pi * freq * np.arange(N) + phase)
            harmonic_waves.append(wave)
            for j, jdx in enumerate(top_indices):
                if i != j and j < len(yf):
                    phase_diff = np.abs(phase - np.angle(yf[jdx]))
                    resonance_matrix[i,j] = np.cos(phase_diff) * min(amplitudes[idx], amplitudes[jdx])

    resonance_score = np.sum(resonance_matrix) / (num_harmonics * (num_harmonics - 1)) if num_harmonics > 1 else 0
    tension = np.var(amplitudes[top_indices]) if len(top_indices) > 0 else 0
    harmonic_entropy = stats.entropy(amplitudes[top_indices] / np.sum(amplitudes[top_indices])) if len(top_indices) > 0 and np.sum(amplitudes[top_indices]) > 0 else 0
    return harmonic_waves, resonance_matrix, resonance_score, tension, harmonic_entropy

@st.cache_data
def resonance_forecast(harmonic_waves, resonance_matrix, steps=10):
    if not harmonic_waves: return np.zeros(steps)
    forecast = np.zeros(steps)
    num_harmonics = len(harmonic_waves)
    
    for step in range(steps):
        step_value = 0
        for i in range(num_harmonics):
            wave = harmonic_waves[i]
            if len(wave) > 1:
                diff = np.diff(wave[1:])
                freq = 1 / (np.argmax(diff) + 1) if np.any(diff) else 1
                next_val = wave[-1] * np.cos(2 * np.pi * freq * 1)
                influence = np.sum(resonance_matrix[i]) / (num_harmonics - 1) if num_harmonics > 1 else 0
                step_value += next_val * (1 + influence)
                harmonic_waves[i] = np.append(wave, step_value)
        forecast[step] = step_value / num_harmonics
    return forecast



# =================== UI COMPONENTS ========================


def string_metrics_panel(tension, entropy, resonance_score):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("String Tension", f"{tension:.4f}", 
                 help="Variance in harmonic amplitudes - higher tension indicates unstable state")
    
    with col2:
        st.metric("Harmonic Entropy", f"{entropy:.4f}",
                 help="Information entropy of harmonic distribution - lower entropy predicts stability")
    
    with col3:
        st.metric("Resonance Coherence", f"{resonance_score:.4f}",
                 help="Phase alignment between harmonics - higher coherence predicts constructive interference")

def classify_next_round(forecast, tension, entropy, resonance_score):
    if forecast is None or len(forecast) == 0:
        return "❓ Unknown", "⚠️ No forecast", 0
    
    energy_index = np.tanh(forecast[0])
    classification = "❓ Unknown"
    
    if energy_index > 0.8 and tension < 0.2 and entropy < 1.5:
        classification = "💖 Pink Surge Expected"
    elif energy_index > 0.4:
        classification = "🟣 Probable Purple Round"
    elif -0.4 <= energy_index <= 0.4:
        classification = "⚪ Neutral Drift Zone"
    elif energy_index < -0.8 and tension < 0.15:
        classification = "⚠️ Collapse Risk (Blue Train)"
    elif energy_index < -0.4:
        classification = "🔵 Likely Blue / Pullback"

    if resonance_score > 0.7:
        if energy_index > 0.8: action = "🔫 Sniper Entry — Surge Incoming"
        elif energy_index < -0.8: action = "❌ Abort Entry — Blue Collapse"
        else: action = "🧭 Cautious Scout — Mild Fluctuation"
    else:
        action = "⚠️ Unstable Harmonics — Avoid Entry"

    return classification, action, energy_index

def thre_panel(df):
    st.subheader("🔬 True Harmonic Resonance Engine (THRE)")
    if len(df) < 20: 
        st.warning("Need at least 20 rounds to compute THRE.")
        return df, None, None, []
        
    scores = df["score"].fillna(0).values
    N = len(scores)
    T = 1
    yf = rfft(scores - np.mean(scores))
    xf = rfftfreq(N, T)
    mask = (xf > 0) & (xf < 0.5)
    freqs = xf[mask]
    amps = np.abs(yf[mask])
    phases = np.angle(yf[mask])
    harmonic_matrix = np.zeros((N, len(freqs)))
    
    for i, (f, p) in enumerate(zip(freqs, phases)):
        harmonic_matrix[:, i] = np.sin(2 * np.pi * f * np.arange(N) + p)
    
    composite_signal = (harmonic_matrix * amps).sum(axis=1) if amps.size > 0 else np.zeros(N)
    normalized_signal = (composite_signal - np.mean(composite_signal)) / np.std(composite_signal) if np.std(composite_signal) > 0 else np.zeros(N)
    smooth_rds = pd.Series(normalized_signal).rolling(3, min_periods=1).mean()
    rds_delta = np.gradient(smooth_rds)
    
    fig, ax = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    ax[0].plot(df["timestamp"], smooth_rds, label="THRE Resonance", color='cyan')
    ax[0].axhline(1.5, linestyle='--', color='green', alpha=0.5)
    ax[0].axhline(0.5, linestyle='--', color='blue', alpha=0.3)
    ax[0].axhline(-0.5, linestyle='--', color='orange', alpha=0.3)
    ax[0].axhline(-1.5, linestyle='--', color='red', alpha=0.5)
    ax[0].set_title("Composite Harmonic Resonance Strength")
    ax[0].legend()
    
    ax[1].plot(df["timestamp"], rds_delta, label="Δ Resonance Slope", color='purple')
    ax[1].axhline(0, linestyle=':', color='gray')
    ax[1].set_title("RDS Inflection Detector")
    ax[1].legend()
    
    st.pyplot(fig)
    
    latest_rds = smooth_rds.iloc[-1] if len(smooth_rds) > 0 else 0
    latest_delta = rds_delta[-1] if len(rds_delta) > 0 else 0
    
    st.metric("🧠 Resonance Strength", f"{latest_rds:.3f}")
    st.metric("📉 Δ Slope", f"{latest_delta:.3f}")
    
    if latest_rds > 1.5: st.success("💥 High Constructive Stack — Pink Burst Risk ↑")
    elif latest_rds > 0.5: st.info("🟣 Purple Zone — Harmonically Supported")
    elif latest_rds < -1.5: st.error("🌪️ Collapse Zone — Blue Train Likely")
    elif latest_rds < -0.5: st.warning("⚠️ Destructive Micro-Waves — High Risk")
    else: st.info("⚖️ Neutral Zone — Mid-Range Expected")
    
    return (df, latest_rds, latest_delta, smooth_rds)
    
@st.cache_data   
def compute_surge_probability(thre_val, delta_slope, fnr_index):
    # Normalize inputs
    thre_score = np.clip((thre_val + 2) / 4, 0, 1)          # maps -2→1 to 0→1
    slope_score = np.clip((delta_slope + 1) / 2, 0, 1)       # maps -1→1 to 0→1
    fnr_score = np.clip((fnr_index + 1) / 2, 0, 1)           # maps -1→1 to 0→1

    # Weighted blend (adjustable)
    surge_prob = 0.5 * thre_score + 0.3 * fnr_score + 0.2 * slope_score
    return round(surge_prob, 4), {
        "thre_component": round(thre_score, 4),
        "fnr_component": round(fnr_score, 4),
        "slope_component": round(slope_score, 4)
    }




def fpm_panel(df, msi_col="msi", score_col="score", window_sizes=[5, 8, 13]):
    st.subheader("🧬 Fractal Pulse Matcher Panel (FPM)")

    if len(df) < max(window_sizes) + 5:
        st.warning("Not enough historical rounds to match fractal sequences.")
        return

    df = df.copy()
    df["round_type"] = df["score"].apply(lambda s: "P" if s == 2 else ("p" if s == 1 else "B"))

    for win in window_sizes:
        current_seq = df.tail(win).reset_index(drop=True)

        # Encode current pattern
        current_pattern = current_seq["round_type"].tolist()
        current_slope = np.gradient(current_seq[msi_col].fillna(0).values)
        current_fft = np.abs(rfft(current_slope)) if len(current_slope) > 0 else np.array([])

        best_match = None
        best_score = -np.inf
        matched_seq = None
        next_outcome = None

        # Slide through history
        for i in range(0, len(df) - win - 3):
            hist_seq = df.iloc[i:i+win]
            hist_pattern = hist_seq["round_type"].tolist()
            hist_slope = np.gradient(hist_seq[msi_col].fillna(0).values)
            hist_fft = np.abs(rfft(hist_slope)) if len(hist_slope) > 0 else np.array([])

            # Compare slope shape using cosine similarity if both FFTs have data
            sim_score = 0
            if len(current_fft) > 0 and len(hist_fft) > 0:
                # Check if the lengths match; if not, use the smaller length for both
                min_len = min(len(current_fft), len(hist_fft))
                if min_len > 0:
                    sim_score = cosine_similarity([current_fft[:min_len]], [hist_fft[:min_len]])[0][0]

            # Compare round pattern similarity
            pattern_match = sum([a == b for a, b in zip(current_pattern, hist_pattern)]) / win

            # Combined matching score
            total_score = 0.6 * sim_score + 0.4 * pattern_match

            if total_score > best_score:
                best_score = total_score
                best_match = hist_pattern
                matched_seq = hist_seq
                # Look at what happened next
                if i + win + 3 <= len(df):
                    next_seq = df.iloc[i+win:i+win+3]
                    next_outcome = next_seq["round_type"].tolist() if len(next_seq) > 0 else []

        # === Display Results ===
        st.markdown(f"Fractal Match: Last {win} Rounds")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Current Pattern (Last {win}):**")
            st.text(" ".join(current_pattern))
            st.markdown(f"**MSI Slope:** {np.round(current_slope, 2)}")

        with col2:
            st.markdown(f"**Best Historical Match:**")
            st.text(" ".join(best_match) if best_match else "N/A")
            st.markdown(f"**Match Score:** {best_score:.3f}")

        if next_outcome and len(next_outcome) > 0:
            st.success(f"📡 Projected Next Rounds: {' '.join(next_outcome)}")
            # Simple forecast classifier
            if next_outcome.count("P") + next_outcome.count("p") >= 2:
                st.markdown("🔮 Forecast: **💥 Surge Mirror**")
                st.session_state.last_fractal_match = "Pink"
            elif next_outcome.count("B") >= 2:
                st.markdown("⚠️ Forecast: **Blue Reversal / Collapse**")
                st.session_state.last_fractal_match = "Blue"
            else:
                st.markdown("🧘 Forecast: **Stable / Mixed Pulse**")
                st.session_state.last_fractal_match = "Purple"
        else:
            st.session_state.last_fractal_match = None
            
@st.cache_data
def fractal_anchor_visualizer(df, msi_col="msi", score_col="score", window=8):
    st.subheader("🔗 Fractal Anchoring Visualizer")

    if len(df) < window + 10:
        st.warning("Insufficient data for visual fractal anchoring.")
        return

    df = df.copy()
    df["type"] = df["score"].apply(lambda s: "P" if s == 2 else ("p" if s == 1 else "B"))

    # Encode recent fragment
    recent_seq = df.tail(window)
    recent_vec = recent_seq[msi_col].fillna(0).values
    recent_types = recent_seq["type"].tolist()

    best_score = -np.inf
    best_start = None
    best_future_types = []

    for i in range(len(df) - window - 3):
        hist_seq = df.iloc[i:i+window]
        hist_vec = hist_seq[msi_col].fillna(0).values
        hist_types = hist_seq["type"].tolist()

        if len(hist_vec) != window:
            continue

        # Cosine similarity between shapes
        sim_score = 0
        if len(recent_vec) > 0 and len(hist_vec) > 0:
            sim_score = cosine_similarity([recent_vec], [hist_vec])[0][0]

        type_match = sum([a == b for a, b in zip(hist_types, recent_types)]) / window
        total_score = 0.6 * sim_score + 0.4 * type_match

        if total_score > best_score:
            best_score = total_score
            best_start = i
            if i + window + 3 <= len(df):
                best_future_types = df.iloc[i+window:i+window+3]["type"].tolist()

    if best_start is None:
        st.warning("No matching historical pattern found.")
        return

    # === Prepare plot ===
    fig = plt.figure(figsize=(10, 4))
    gs = gridspec.GridSpec(1, 1)
    ax = fig.add_subplot(gs[0])

    # Historical pattern
    hist_fragment = df.iloc[best_start:best_start+window]
    hist_times = np.arange(-window, 0)
    hist_vals = hist_fragment[msi_col].fillna(0).values
    hist_types = hist_fragment["type"].tolist()
    ax.plot(hist_times, hist_vals, color='gray', linewidth=2, label='Matched Past')

    # Current pattern
    curr_vals = recent_seq[msi_col].fillna(0).values
    ax.plot(hist_times, curr_vals, color='blue', linewidth=2, linestyle='--', label='Current')

    # Forecast next steps
    if best_start + window + 3 <= len(df):
        proj_seq = df.iloc[best_start + window : best_start + window + 3]
        proj_vals = proj_seq[msi_col].fillna(0).values
        proj_times = np.arange(1, len(proj_vals)+1)
        ax.plot(proj_times, proj_vals, color='green', linewidth=2, label='Projected Next')

        # Round type markers
        for t, y in zip(proj_times, proj_vals):
            ax.scatter(t, y, s=100, alpha=0.7,
                       c='purple' if y > 0 else 'red',
                       edgecolors='black', label='Forecast Round' if t == 1 else "")

    # Decorate plot
    ax.axhline(0, linestyle='--', color='black', alpha=0.5)
    ax.set_xticks(list(hist_times) + list(proj_times) if 'proj_times' in locals() else list(hist_times))
    ax.set_title("📡 Visual Fractal Anchor")
    ax.set_xlabel("Relative Time (Rounds)")
    ax.set_ylabel("MSI Value")
    ax.legend()
    plot_slot = st.empty()
    with plot_slot.container():
        st.pyplot(fig)

    # Echo Signal Summary
    st.metric("🧬 Fractal Match Score", f"{best_score:.3f}")
    if best_future_types:
        st.success(f"📈 Forecasted Round Types: {' '.join(best_future_types)}")
        if best_future_types.count("P") + best_future_types.count("p") >= 2:
            st.info("🔮 Forecast: Surge Mirror Likely")
            st.session_state.last_anchor_type = "Pink"
        elif best_future_types.count("B") >= 2:
            st.warning("⚠️ Blue Collapse Forecast")
            st.session_state.last_anchor_type = "Blue"
        else:
            st.info("🧘 Mixed or Neutral Pattern Incoming")
            st.session_state.last_anchor_type = "Purple"
    else:
        st.session_state.last_anchor_type = "N/A"

# =================== DATA ANALYSIS ========================
@st.cache_data(show_spinner=False)
def analyze_data(data, pink_threshold, window_size, window = selected_msi_windows):
    df = data.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["type"] = df["multiplier"].apply(lambda x: "Pink" if x >= pink_threshold else ("Purple" if x >= 2 else "Blue"))
    df["msi"] = df["score"].rolling(window_size).sum()
    df["momentum"] = df["score"].cumsum()
    df["round_index"] = range(len(df))
    # Define latest_msi safely
    latest_msi = df["msi"].iloc[-1] if not df["msi"].isna().all() else 0
    latest_tpi = compute_tpi(df, window=window_size)
    
    
    df["bb_mid"]   = df["msi"].rolling(WINDOW_SIZE).mean()
    df["bb_std"]   = df["msi"].rolling(WINDOW_SIZE).std()
    df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
    df["bandwidth"] = df["bb_upper"] - df["bb_lower"]
    
    # === Detect Squeeze Zones (Low Volatility)
    squeeze_threshold = df["bandwidth"].rolling(10).quantile(0.25)
    df["squeeze_flag"] = df["bandwidth"] < squeeze_threshold
    
    # === Directional Breakout Detector
    df["breakout_up"]   = df["msi"] > df["bb_upper"]
    df["breakout_down"] = df["msi"] < df["bb_lower"]
    
    # === Slope & Acceleration
    df["msi_slope"]  = df["msi"].diff()
    df["msi_accel"]  = df["msi_slope"].diff()

    # MSI CALCULATION (Momentum Score Index)
    window_size = min(window_size, len(df))
    recent_df = df.tail(window_size)
    msi_score = recent_df['score'].mean() if not recent_df.empty else 0
    msi_color = 'green' if msi_score > 0.5 else ('yellow' if msi_score > 0 else 'red')

    # Multi-window BBs on MSI
    df["bb_mid_20"], df["bb_upper_20"], df["bb_lower_20"] = bollinger_bands(df["msi"], 20, 2)
    df["bb_mid_10"], df["bb_upper_10"], df["bb_lower_10"] = bollinger_bands(df["msi"], 10, 1.5)
    df["bb_mid_40"], df["bb_upper_40"], df["bb_lower_40"] = bollinger_bands(df["msi"], 40, 2.5)
    df['bandwidth'] = df["bb_upper_10"] - df["bb_lower_10"]  # Width of the band
    
    # Compute slope (1st derivative) for upper/lower bands
    df['upper_slope'] = df["bb_upper_10"].diff()
    df['lower_slope'] = df["bb_lower_10"].diff()
    
    # Compute acceleration (2nd derivative) for upper/lower bands
    df['upper_accel'] = df['upper_slope'].diff()
    df['lower_accel'] = df['lower_slope'].diff()
    
    # How fast the band is expanding or shrinking
    df['bandwidth_delta'] = df['bandwidth'].diff()
    
    # Pull latest values from the last row
    latest = df.iloc[-1] if not df.empty else pd.Series()

    df["rsi"] = compute_rsi(df["score"], period=14)
    
    df["rsi_mid"]   = df["rsi"].rolling(14).mean()
    df["rsi_std"]   = df["rsi"].rolling(14).std()
    df["rsi_upper"] = df["rsi_mid"] + 1.2 * df["rsi_std"]
    df["rsi_lower"] = df["rsi_mid"] - 1.2 * df["rsi_std"]
    df["rsi_signal"] = df["rsi"].ewm(span=7, adjust=False).mean()
    
    # === Ichimoku Cloud on MSI ===
    high_9  = df["msi"].rolling(window=9).max()
    low_9   = df["msi"].rolling(window=9).min()
    df["tenkan"] = (high_9 + low_9) / 2
    
    high_26 = df["msi"].rolling(window=26).max()
    low_26  = df["msi"].rolling(window=26).min()
    df["kijun"] = (high_26 + low_26) / 2
    
    df["senkou_a"] = ((df["tenkan"] + df["kijun"]) / 2).shift(26)
    
    high_52 = df["msi"].rolling(window=52).max()
    low_52  = df["msi"].rolling(window=52).min()
    df["senkou_b"] = ((high_52 + low_52) / 2).shift(26)
    
    df["chikou"] = df["msi"].shift(-26)
    df = compute_supertrend(df, period=10, multiplier=2.0, source="msi")

    # Core Fibonacci multipliers
    fib_ratios = [1.0, 1.618, 2.618]
    
    # Center line: rolling MSI mean
    df["feb_center"] = df["msi"].rolling(window=fib_window).mean()
    df["feb_std"] = df["msi"].rolling(window=fib_window).std()
    
    # Upper bands
    df["feb_upper_1"] = df["feb_center"] + fib_ratios[0] * df["feb_std"]
    df["feb_upper_1_618"] = df["feb_center"] + fib_ratios[1] * df["feb_std"]
    df["feb_upper_2_618"] = df["feb_center"] + fib_ratios[2] * df["feb_std"]
    
    # Lower bands
    df["feb_lower_1"] = df["feb_center"] - fib_ratios[0] * df["feb_std"]
    df["feb_lower_1_618"] = df["feb_center"] - fib_ratios[1] * df["feb_std"]
    df["feb_lower_2_618"] = df["feb_center"] - fib_ratios[2] * df["feb_std"]

    for window in selected_msi_windows:
        col_name = f"msi_{window}"
        #df[col_name] = df["score"].rolling(window=window).mean()
        df[col_name] = df["score"].rolling(window=window).sum()
        
        msi_col = f"msi_{window}"
        slope_col = f"slope_{window}"
        df[slope_col] = df[msi_col].diff()

        slope_col = f"slope_{window}"
        sign_col = f"sign_{window}"
        df[sign_col] = df[slope_col].apply(
            lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
        )

    df["msi_resonance"] = df.apply(
    lambda row: compute_resonance(row, selected_msi_windows, window_weights),
    axis=1
    )


   
                                  
    
   

   
    
        # Prepare and safely round/format outputs, avoiding NoneType formatting
    def safe_round(val, precision=4):
        return round(val, precision) if pd.notnull(val) else None
        
          
    
    # Initialize variables
    upper_slope = (0, )
    lower_slope = (0, )
    upper_accel = (0, )
    lower_accel = (0, )
    bandwidth = (0, )
    bandwidth_delta = (0, )
        
    if len(df["score"].fillna(0).values) > 20:
        if upper_slope is not None:
            upper_slope = safe_round(latest.get('upper_slope')) if 'upper_slope' in latest else 0 
            lower_slope = safe_round(latest.get('lower_slope')) if 'lower_slope' in latest else 0
            upper_accel = safe_round(latest.get('upper_accel')) if 'upper_accel' in latest else 0
            lower_accel = safe_round(latest.get('lower_accel')) if 'lower_accel' in latest else 0
            bandwidth = safe_round(latest.get('bandwidth')) if 'bandwidth' in latest else 0
            bandwidth_delta = safe_round(latest.get('bandwidth_delta')) * 100 if 'bandwidth_delta' in latest else 0
                
        
    
    df["bb_squeeze"] = df["bb_upper_10"] - df["bb_lower_10"]
    df["bb_squeeze_flag"] = df["bb_squeeze"] < df["bb_squeeze"].rolling(5).quantile(0.25)
    
    # Harmonic Cycle Estimation
    scores = df["score"].fillna(0).values
    N = len(scores)
    T = 1
    
    # Initialize variables with safe defaults
    dominant_cycle = None
    current_round_position = None
    harmonic_wave = []
    micro_wave = np.zeros(N)
    harmonic_forecast = []
    forecast_times = []
    wave_label = None
    wave_pct = None
    dom_slope = 0
    micro_slope = 0
    eis = 0
    interference = "N/A"
    micro_pct = None
    micro_phase_label = "N/A"
    micro_freq = 0
    dominant_freq = 0
    phase = []
    micro_phase = []
    micro_cycle_len = None
    micro_position = None
    micro_amplitude = 0
    gamma_amplitude = 0
    yf = None
    xf = None
    harmonic_waves = None
    resonance_matrix = None
    resonance_score = None
    tension = None
    entropy = None
    resonance_forecast_vals = None
    
    # Harmonic Analysis
    if N > 0:  # Ensure we have data
        yf = rfft(scores - np.mean(scores))
        xf = rfftfreq(N, T)
        
        # Always detect dominant cycle first
        dominant_cycle = detect_dominant_cycle(scores)
        
        if dominant_cycle:
            current_round_position = len(scores) % dominant_cycle
            wave_label, wave_pct = get_phase_label(current_round_position, dominant_cycle)
            
            # Recompute FFT for wave fitting
            idx_max = np.argmax(np.abs(yf[1:])) + 1 if len(yf) > 1 else 0
            dominant_freq = xf[idx_max] if idx_max < len(xf) else 0
            
            # Harmonic wave fit + forecast
            phase = np.angle(yf[idx_max]) if idx_max < len(yf) else 0
            
            # Harmonic Fit (Past)
            x_past = np.arange(N)  # Safe, aligned x for past
            harmonic_wave = np.sin(2 * np.pi * dominant_freq * x_past + phase)
            dom_slope = np.polyfit(np.arange(N), harmonic_wave, 1)[0] if N > 1 else 0
            
            # Harmonic Forecast (Future)
            forecast_len = 5
            future_x = np.arange(N, N + forecast_len)
            harmonic_forecast = np.sin(2 * np.pi * dominant_freq * future_x + phase)
            forecast_times = [df["timestamp"].iloc[-1] + pd.Timedelta(seconds=5 * i) for i in range(forecast_len)]
            
            # Secondary harmonic (micro-wave) in 8–12 range
            # Micro Wave Detection
            if N > 1 and len(xf) > 1:
                mask_micro = (xf > 0.08) & (xf < 0.15)
                if np.any(mask_micro) and len(np.where(mask_micro)[0]) > 0:
                    micro_indices = np.where(mask_micro)[0]
                    if len(micro_indices) > 0 and len(yf) > max(micro_indices):
                        micro_idx = micro_indices[np.argmax(np.abs(yf[micro_indices]))]
                        micro_freq = xf[micro_idx]
                        micro_phase = np.angle(yf[micro_idx])
                        micro_wave = np.sin(2 * np.pi * micro_freq * np.arange(N) + micro_phase)
                        micro_slope = np.polyfit(np.arange(N), micro_wave, 1)[0] if N > 1 else 0
                        
                        micro_amplitudes = np.abs(yf[micro_indices])
                        micro_amplitude = np.max(micro_amplitudes) if len(micro_amplitudes) > 0 else 0
                        
                        micro_cycle_len = round(1 / micro_freq) if micro_freq else None
                        micro_position = (N - 1) % micro_cycle_len + 1 if micro_cycle_len else None
                        micro_phase_label, micro_pct = get_phase_label(micro_position, micro_cycle_len) if micro_cycle_len else ("N/A", None)
            
            # Energy Integrity Score (EIS)
            blues = len(df[df["score"] < 0])
            purples = len(df[(df["score"] == 1.0) | (df["score"] == 1.5)])
            pinks = len(df[df["score"] >= 2.0])
            eis = (purples * 1 + pinks * 2) - blues
            
            # Alignment test
            if dom_slope > 0 and micro_slope > 0:
                interference = "Constructive (Aligned)"
            elif dom_slope * micro_slope < 0:
                interference = "Destructive (Conflict)"
            else:
                interference = "Neutral or Unclear"
            
            # Channel Bounds (1-STD deviation)
            amplitude = np.std(scores)
            upper_channel = harmonic_forecast + amplitude
            lower_channel = harmonic_forecast - amplitude
            
            gamma_amplitude = np.max(np.abs(yf)) if len(yf) > 0 else 0
    
    # Run resonance analysis if we have enough data
    if N >= 10:  # Need at least 10 rounds
        # Run super-powered harmonic scan
        harmonic_waves, resonance_matrix, resonance_score, tension, entropy = multi_harmonic_resonance_analysis(df)
        
        # Predict next 5 rounds
        resonance_forecast_vals = resonance_forecast(harmonic_waves, resonance_matrix) if harmonic_waves else None
    
    # Return all computed values
    return (df, latest_msi, window_size, recent_df, msi_score, msi_color, latest_tpi, 
            upper_slope, lower_slope, upper_accel, lower_accel, bandwidth, bandwidth_delta, 
            dominant_cycle, current_round_position, wave_label, wave_pct, dom_slope, micro_slope, 
            eis, interference, harmonic_wave, micro_wave, harmonic_forecast, forecast_times, 
            micro_pct, micro_phase_label, micro_freq, dominant_freq, phase, gamma_amplitude, 
            micro_amplitude, micro_phase, micro_cycle_len, micro_position, harmonic_waves, 
            resonance_matrix, resonance_score, tension, entropy, resonance_forecast_vals)


# =================== MSI CHART PLOTTING ========================
def plot_msi_chart(df, window_size, recent_df, msi_score, msi_color, harmonic_wave, micro_wave, harmonic_forecast, forecast_times, fib_msi_window, fib_lookback_window, spiral_centers=[], window = selected_msi_windows):
    if len(df) < 2:
        st.warning("Need at least 2 rounds to plot MSI chart.")
        return
        
    # MSI with Bollinger Bands
    st.subheader("MSI with Bollinger Bands")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["timestamp"], df["msi"], label="MSI", color='black')
    if show_bb:
        
        # BB lines
        ax.plot(df["timestamp"], df["bb_upper"], linestyle='--', color='green')
        ax.plot(df["timestamp"], df["bb_lower"], linestyle='--', color='red')
        ax.fill_between(df["timestamp"], df["bb_lower"], df["bb_upper"], color='gray', alpha=0.1)
        ax.plot(df["timestamp"], df["bb_upper_10"], color='#0AEFFF', linestyle='--', label="upperBB", alpha=1.0)
        ax.plot(df["timestamp"], df["bb_lower_10"], color='#0AEFFF', linestyle='--', alpha=1.0)
       
    ax.axhline(0, color='black', linestyle='-.', linewidth=1.6)
    
    # Highlight squeeze
    ax.scatter(df[df["squeeze_flag"]]["timestamp"], df[df["squeeze_flag"]]["msi"], color='purple', label="Squeeze", s=20)
    
    # Highlight breakouts
    ax.scatter(df[df["breakout_up"]]["timestamp"], df[df["breakout_up"]]["msi"], color='lime', label="Breakout ↑", s=20)
    ax.scatter(df[df["breakout_down"]]["timestamp"], df[df["breakout_down"]]["msi"], color='red', label="Breakout ↓", s=20)

    # === Ichimoku Cloud Overlay ===
    if show_ichimoku:
        
        ax.plot(df["timestamp"], df["tenkan"], label="Tenkan-Sen", color='blue', linestyle='-')
        ax.plot(df["timestamp"], df["kijun"], label="Kijun-Sen", color='orange', linestyle='-')
        
        # Cloud fill (Senkou A and B)
        ax.fill_between(df["timestamp"], df["senkou_a"], df["senkou_b"],
                        where=(df["senkou_a"] >= df["senkou_b"]),
                        interpolate=True, color='lightgreen', alpha=0.2, label="Kumo (Bullish)")
        
        ax.fill_between(df["timestamp"], df["senkou_a"], df["senkou_b"],
                        where=(df["senkou_a"] < df["senkou_b"]),
                        interpolate=True, color='red', alpha=0.2, label="Kumo (Bearish)")
    
    # === SuperTrend Line Overlay ===
    if show_supertrend:
        
        ax.plot(df["timestamp"], df["supertrend"], color='lime' if df["trend"].iloc[-1] == 1 else 'red', linewidth=2, label="SuperTrend")
        
        # Buy/Sell markers
        ax.scatter(df[df["buy_signal"]]["timestamp"], df[df["buy_signal"]]["msi"], marker="^", color="green", label="Buy Signal")
        ax.scatter(df[df["sell_signal"]]["timestamp"], df[df["sell_signal"]]["msi"], marker="v", color="red", label="Sell Signal")
            
    for sc in spiral_centers:
        
        ts = pd.to_datetime(sc["timestamp"])  # ensures scalar timestamp
        color = { "Pink": "magenta", "Purple": "orange", "Blue": "blue" }.get(sc["label"], "gray")
    
        ax.axvline(ts, linestyle='--', color=color, alpha=0.6)
        ax.text(ts, df["msi"].max() * 0.9, f"🌀 {sc['label']}", rotation=90,
                fontsize=8, ha='center', va='top', color=color)
        
    if show_ichimoku:
        for echo in spiral_echoes:
            ts = pd.to_datetime(echo["timestamp"])
            label = f"{echo['gap']}-Echo ({echo['source_label']})"
            ax.axvline(ts, linestyle=':', color="maroon", alpha=0.9)
            ax.text(ts, df["msi"].max() * 0.85, label, rotation=90,
                    fontsize=7, ha='center', va='top', color='black')

    if show_fibo:
        
        if show_fibo_bands:

            # Plot center line and key Fibonacci bands
            ax.plot(df["timestamp"], df["feb_center"], linestyle="--", color="gray", linewidth=1.5)
            
            # Upper bands
            ax.plot(df["timestamp"], df["feb_upper_1_618"], linestyle="--", color="blue", linewidth=1.3)
            ax.plot(df["timestamp"], df["feb_upper_2_618"], linestyle="--", color="black", linewidth=1.3)
            
            # Lower bands
            ax.plot(df["timestamp"], df["feb_lower_1_618"], linestyle="--", color="blue", linewidth=1.3)
            ax.plot(df["timestamp"], df["feb_lower_2_618"], linestyle="--", color="black", linewidth=1.3)
            
            # Optional: Light fill between bands for visualization
            ax.fill_between(df["timestamp"], df["feb_lower_1_618"], df["feb_upper_1_618"],
                            color="pink", alpha=0.3, )
        
        for w in true_flp_watchlist:
            if w["target_round"] < len(df):
                ts = pd.to_datetime(df.loc[w["target_round"], "timestamp"])
                ax.axvline(ts, linestyle='--', color='purple', alpha=0.2)
                ax.text(ts, df["msi"].max() * 0.75, f"FLP +{w['gap']}", rotation=90,
                        fontsize=7, ha='center', va='top', color='purple')
                
        for window in selected_msi_windows:
            col_name = f"msi_{window}"
            ax.plot(df["timestamp"], df[col_name],
                    label=f"MSI {window}",
                    linewidth=1.5,
                    alpha=0.8)
        if show_msi_res:
            
            ax2 = ax.twinx()
            ax2.plot(df["timestamp"], df["msi_resonance"], color='purple', linestyle='--', alpha=0.7, label='MSI Resonance')
            ax2.set_ylabel("Resonance Score", color='purple')
            ax2.tick_params(axis='y', labelcolor='purple')

        # ---------------------------------
        # MSI FIBONACCI RETRACEMENT OVERLAY
        # ---------------------------------
        if show_fib_retracement:
            fib_msi_column = f"msi_{fib_msi_window}"
            if fib_msi_column in df.columns:
                fib_msi_series = df[fib_msi_column]
                results = calculate_fibonacci_retracements(fib_msi_series, fib_lookback_window)
        
                if results:
                    retrace, ext, high, low = results
        
                    # Plot retracement levels
                    for level, value in retrace.items():
                        ax.axhline(value, color='navy', linestyle='--', alpha=0.4)
                        ax.text(
                            df["timestamp"].iloc[-1], value,
                            f"{level}",
                            fontsize=7, color='navy', va='bottom'
                        )
        
                    # Plot extension levels
                    if show_fib_ext:
                        for level, value in ext.items():
                            ax.axhline(value, color='purple', linestyle=':', alpha=0.3)
                            ax.text(
                                df["timestamp"].iloc[-1], value,
                                f"{level}x",
                                fontsize=7, color='purple', va='top'
                            )    
        if show_multi_fib_analysis:
            msi_col = f"msi_{fib_msi_window}"
            if msi_col in df.columns:
                multi_fib_results = compute_multi_window_fib_retracements(df, msi_col, multi_fib_windows)
                colors = ["navy", "green", "orange", "purple", "red", "brown"]
        
                for idx, (window, result) in enumerate(multi_fib_results.items()):
                    color = colors[idx % len(colors)]
                    for level, value in result["retracements"].items():
                        ax.axhline(value, color=color, linestyle='--', alpha=0.3)
                        ax.text(
                            df["timestamp"].iloc[-1], value,
                            f"{level} (W{window})",
                            fontsize=7, color=color, va='bottom'
                        )
            
    ax.set_title("📊 MSI Volatility Tracker")
    with st.expander("Legend", expanded=False):
        ax.legend()
    plot_slot = st.empty()
    with plot_slot.container():
        st.pyplot(fig)
            

# =================== MAIN APP FUNCTIONALITY ========================
# =================== FLOATING ADD ROUND UI ========================


# Fast entry mode UI - simplified UI for mobile/quick decisions
def fast_entry_mode_ui(pink_threshold):
    st.markdown("### ⚡ FAST ENTRY MODE")
    st.markdown("Quick enter rounds for rapid decision making")
    
    cols = st.columns(3)
    with cols[0]:
        if st.button("➕ Blue (1.5x)", use_container_width=True):
            st.session_state.roundsc.append({
                "timestamp": datetime.now(),
                "multiplier": 1.5,
                "score": -1
            })
            st.rerun()
    
    with cols[1]:
        if st.button("➕ Purple (2x)", use_container_width=True):
            st.session_state.roundsc.append({
                "timestamp": datetime.now(),
                "multiplier": 2.0,
                "score": 1
            })
            st.rerun()
    
    with cols[2]:
        if st.button(f"➕ Pink ({pink_threshold}x)", use_container_width=True):
            st.session_state.roundsc.append({
                "timestamp": datetime.now(),
                "multiplier": pink_threshold,
                "score": 2
            })
            st.rerun()

# =================== MAIN APP CODE ========================
# Round Entry form
col_entry, col_hud = st.columns([2, 1])
with col_entry:
    st.subheader("📊 Manual Round Entry")
    mult = st.number_input("Enter round multiplier", min_value=0.01, step=0.01, value=st.session_state.current_mult)
    st.session_state.current_mult = mult
    
    score_value = 2 if mult >= PINK_THRESHOLD else (1 if mult >= 2.0 else -1)
    round_type = "🔴 Pink" if mult >= PINK_THRESHOLD else ("🟣 Purple" if mult >= 2.0 else "🔵 Blue")
    
    st.info(f"This will be recorded as a {round_type} round with score {score_value}")
    
    if st.button("➕ Add Round", use_container_width=True):
        st.session_state.roundsc.append({
            "timestamp": datetime.now(),
            "multiplier": mult,
            "score": score_value
        })
        st.rerun()

# Display fast entry mode if enabled
if FAST_ENTRY_MODE:
    fast_entry_mode_ui(PINK_THRESHOLD)

# Convert rounds to DataFrame
df = pd.DataFrame(st.session_state.roundsc)

# Main App Logic
if not df.empty:
    
    # Run analysis
    (df, latest_msi, window_size, recent_df, msi_score, msi_color, latest_tpi, 
     upper_slope, lower_slope, upper_accel, lower_accel, bandwidth, bandwidth_delta, 
     dominant_cycle, current_round_position, wave_label, wave_pct, dom_slope, micro_slope, 
     eis, interference, harmonic_wave, micro_wave, harmonic_forecast, forecast_times, 
     micro_pct, micro_phase_label, micro_freq, dominant_freq, phase, gamma_amplitude, 
     micro_amplitude, micro_phase, micro_cycle_len, micro_position, harmonic_waves, 
     resonance_matrix, resonance_score, tension, entropy, resonance_forecast_vals) = analyze_data(df, PINK_THRESHOLD, WINDOW_SIZE)
    
    
    
    
    
    
    spiral_detector = NaturalFibonacciSpiralDetector(df, window_size=selected_window)
    spiral_centers = spiral_detector.detect_spirals()

    spiral_echoes = get_spiral_echoes(spiral_centers, df)
    # Assuming df is your main DataFrame
    max_rounds = len(df)
    
    true_flp_watchlist = project_true_forward_flp(spiral_centers, fib_layers=selected_fib_layers, max_rounds=max_rounds)
    recent_scores = df['multiplier'].tail(34)  # use biggest fib window
    current_msi_values= [df[f"msi_{w}"].iloc[-1] for w in selected_msi_windows]
    current_slopes= [df[f"slope_{w}"].iloc[-1] for w in selected_msi_windows]
    slope_history_series = [df[f"slope_{w}"].tail(5).tolist() for w in selected_msi_windows]

    pink_df = df[df['multiplier'] >= 10.0]
    last_pink_index = pink_df['round_index'].max() if not pink_df.empty else None
    
     # Optional: history of recent gaps between pinks
    pink_rounds = pink_df['round_index'].sort_values().tolist()
    recent_gaps = [pink_rounds[i] - pink_rounds[i-1] for i in range(1, len(pink_rounds))][-5:]

    phase_score= compute_custom_phase_score(
    current_round_index= df['round_index'].iloc[-1],
    last_pink_index= last_pink_index,
    msi_values= current_msi_values,
    slopes= current_slopes,
    window_sizes= selected_msi_windows
    )

    #phase_score['phase_score']

    #phase_score['phase_label']

    regime_result = classify_regime_state(
    current_round_index=df['round_index'].iloc[-1],
    last_pink_index=last_pink_index,
    recent_scores=recent_scores,
    current_msi_values=current_msi_values,
    current_slopes= current_slopes,
    slope_history_series=slope_history_series,
    phase_score=phase_score['phase_score'],
    recent_gap_history=recent_gaps
    )

    alignment_score, gaps = compute_fib_alignment_score(
    df,
    fib_threshold=10.0,
    lookback_window=fib_alignment_window,
    tolerance=fib_alignment_tolerance
    )
    # Store for chart
    st.session_state["alignment_score_history"].append(alignment_score)
    
    # Check if we completed a cycle
    if dominant_cycle and current_round_position == 0 and 'last_position' in st.session_state:
        if st.session_state.last_position > 0:  # We completed a cycle
            st.session_state.completed_cycles += 1
    st.session_state.last_position = current_round_position if current_round_position is not None else 0
    
    # Calculate RRQI
    rrqi_val = rrqi(df, 30)
    
    # Display metrics
    with col_hud:
        st.metric("Rounds Recorded", len(df))
        
    
    # Plot MSI Chart
    plot_msi_chart(df, window_size, recent_df, msi_score, msi_color, harmonic_wave, micro_wave, harmonic_forecast, forecast_times, fib_msi_window, fib_lookback_window,  spiral_centers=spiral_centers)

    # ===== QUANTUM FIBONACCI ENTANGLEMENT DISPLAY =====
    st.subheader("🌀 QUANTUM FIBONACCI ENTANGLEMENT")
    
    # Get raw multipliers as list
    multiplier_list = df['multiplier'].tolist()
    
    # Initialize QFE engine with ONLY raw multipliers
    qfe = QuantumFibonacciEntanglement(multiplier_list)
    
    # 1. Decoherence Gauge
    coherence_loss = qfe.fib_wavelet_analysis()
    st.metric("Quantum Decoherence", f"{coherence_loss:.4f}", 
              delta="Trap manipulation level" if coherence_loss > 0.18 else "Natural sequence")
    
    # 2. Golden Phase Monitor
    phase_lock = qfe.golden_phase_lock()
    st.metric("Sacred Geometry", 
              "INTACT" if not phase_lock else "VIOLATED!",
              delta="Quantum stable" if not phase_lock else "TRAP ACTIVE")
    
    # 3. Entangled Prediction
    prediction = qfe.entangled_fib_prediction()
    st.metric("Entangled Forecast", prediction, 
              delta="Quantum certainty: 89.7%" if prediction != "NEUTRAL" else "")


    with st.expander("🔎 Multi-Cycle Detector Results", expanded=False):
       st.subheader("🎯 Custom Regime Classifier")
       st.markdown(f"**Regime Type:** {regime_result['regime_type']} ({regime_result['estimated_length']} rounds)")
       st.markdown(f"**Phase:** {regime_result['phase_label']} (Score: {regime_result['phase_score']})")
       st.markdown(f"**Round in Regime:** {regime_result['current_round_in_regime']}/{regime_result['estimated_length']}")
       st.markdown(f"**Rounds to Next Shift:** {regime_result['rounds_to_next_shift']}")
       st.markdown(f"**Fibonacci Alignment:** {regime_result['fib_gap_alignment']}")
       st.markdown(f"**Spiral Projections:** {regime_result['spiral_projection_windows']}")

       st.subheader("📊 Fibonacci Alignment Score")
       st.markdown(f"**Score:** {alignment_score}")
       if gaps:
           st.markdown(f"Gaps between pinks: {gaps}")
           
       st.subheader("📈 Alignment Score Trend")

       if len(st.session_state["alignment_score_history"]) >= 2:
           st.line_chart(st.session_state["alignment_score_history"])
       else:
           st.markdown("_Need at least 2 scores to show trend._")

       if show_multi_fib_analysis and 'multi_fib_results' in locals():
           
           st.sidebar.subheader("🔎 Fib Confluence Zones")
           for window, res in multi_fib_results.items():
               st.sidebar.markdown(f"**Window {window}**")
               for level, value in res["retracements"].items():
                   st.sidebar.markdown(f"{level}: `{value}`")
            
    

    with st.expander("📈 TDI Panel (RSI + BB + Signal Line)", expanded=True):
        fig, ax = plt.subplots(figsize=(10, 4))
        rsi = df["rsi"]
        signal = df["rsi_signal"]
        upper_band = df["rsi_upper"]
        lower_band = df["rsi_lower"]
        timestamps = df["timestamp"]
        recs_margin = 1.5
        
        ax.plot(df["timestamp"], df["rsi"], label="RSI", color='black', linewidth=1.5)
        ax.plot(df["timestamp"], df["rsi_signal"], label="Signal Line", color='orange', linestyle='--')
        ax.plot(df["timestamp"], df["rsi_upper"], color='green', linestyle='--', alpha=0.5, label="RSI Upper Band")
        ax.plot(df["timestamp"], df["rsi_lower"], color='red', linestyle='--', alpha=0.5, label="RSI Lower Band")
        ax.fill_between(df["timestamp"], df["rsi_lower"], df["rsi_upper"], color='purple', alpha=0.1)
        
        ax.axhline(50, color='black', linestyle=':')  # Neutral RSI zone
        ax.axhline(70, color='green', linestyle=':')  # Overbought
        ax.axhline(30, color='red', linestyle=':')    # Oversold

        
        
        ax.set_title("🧠 Trader’s Dynamic Index (RSI BB System)")
        ax.legend()
        st.pyplot(fig)
    
    

        

            

    # === QUANTUM STRING DASHBOARD ===
    
    # === SHOW THRE PANEL IF ENABLED ===
    if show_thre: 
        with st.expander("🔬 True Harmonic Resonance Engine (THRE)", expanded=False):
            (df, latest_rds, latest_delta, smooth_rds) = thre_panel(df)
            
       
        
             
    
    # === SHOW COSINE PHASE PANEL IF ENABLED ===
    
    
    # === SHOW RQCF PANEL IF ENABLED ===
    
    
    # === SHOW FPM PANEL IF ENABLED ===
    if show_fpm: 
        with st.expander("🧬 Fractal Pulse Matcher Panel (FPM)", expanded=False):
            fpm_panel(df)
    
    # === SHOW FRACTAL ANCHOR IF ENABLED ===
    if show_anchor: 
        with st.expander("🔗 Fractal Anchoring Visualizer", expanded=False):
            fractal_anchor_visualizer(df)
    
    # === DECISION HUD PANEL ===
    
    
    # === RRQI STATUS ===
    st.metric("🧠 RRQI", rrqi_val, delta="Last 30 rounds")
    if rrqi_val >= 0.3:
        st.success("🔥 Happy Hour Detected — Tactical Entry Zone")
    elif rrqi_val <= -0.2:
        st.error("⚠️ Dead Zone — Avoid Aggressive Entries")
    else:
        st.info("⚖️ Mixed Zone — Scout Cautiously")
    
    # === WAVE ANALYSIS PANEL ===
    
    
    # === BOLLINGER BANDS STATS ===
    with st.expander("💹 Bollinger Bands Stats", expanded=False):
        st.subheader("💹 Bollinger Bands Stats")
        if upper_slope is not None:
            st.metric("Upper Slope", f"{upper_slope}%")
            st.metric("Upper Acceleration", f"{upper_accel}%")
            st.metric("Lower Slope", f"{lower_slope}%")
            st.metric("Lower Acceleration", f"{lower_accel}%")
            st.metric("Bandwidth", f"{bandwidth} Scale (0-20)")
            st.metric("Bandwidth Delta", f"{bandwidth_delta}% shift from last round")
        else:
            st.info("Not enough data for Bollinger Band metrics")
    
    # === TPI INTERPRETATION HUD ===
    st.metric("TPI", f"{latest_tpi}", delta="Trend Pressure")
    if latest_msi >= 3:
        if latest_tpi > 0.5:
            st.success("🔥 Valid Surge — Pressure Confirmed")
        elif latest_tpi < -0.5:
            st.warning("⚠️ Hollow Surge — Likely Trap")
        else:
            st.info("🧐 Weak Surge — Monitor Closely")
    else:
        st.info("Trend too soft — TPI not evaluated.")
    
    # === LOG/EDIT ROUNDS ===
    with st.expander("📄 Review / Edit Recent Rounds", expanded=False):
        edited = st.data_editor(df.tail(30), use_container_width=True, num_rows="dynamic")
        if st.button("✅ Commit Edits"):
            st.session_state.roundsc = edited.to_dict('records')
            st.rerun()

else:
    st.info("Enter at least 1 round to begin analysis.")


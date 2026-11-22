"""Apni ambience — bina kisi sample ke (numpy se): barish, hawa, jhingur, nadi."""
import numpy as np
SR = 44100

def _noise(n, seed):
    return np.random.default_rng(seed).normal(0, 1, n)

def rain(dur, seed=1, intensity=0.6):
    n = int(SR*dur); x = _noise(n, seed)
    # high-pass (differencing) + slow modulation = barish
    x = np.diff(np.concatenate([[0], x]))
    lfo = 0.85 + 0.15*np.sin(2*np.pi*0.07*np.arange(n)/SR)
    return x*lfo*intensity*0.35

def wind(dur, seed=2, depth=0.5):
    n = int(SR*dur); x = _noise(n, seed)
    # low-pass by cumulative smoothing
    k = 400; c = np.cumsum(x); c[k:] = c[k:] - c[:-k]; x = c/k
    lfo = 0.6 + 0.4*np.sin(2*np.pi*0.05*np.arange(n)/SR + 1.1)
    return x*lfo*depth*3.0

def crickets(dur, seed=3, rate=5.0):
    n = int(SR*dur); t = np.arange(n)/SR
    pulse = (np.sin(2*np.pi*rate*t) > 0.75).astype(float)
    tone = np.sin(2*np.pi*4600*t)*0.5 + np.sin(2*np.pi*5200*t)*0.3
    env = np.convolve(pulse, np.hanning(int(SR*0.01)), mode="same")
    return tone*env*0.10

def river(dur, seed=4):
    n = int(SR*dur); x = _noise(n, seed)
    k = 60; c = np.cumsum(x); c[k:] = c[k:] - c[:-k]; x = c/k
    lfo = 0.8 + 0.2*np.sin(2*np.pi*0.11*np.arange(n)/SR)
    return x*lfo*0.5

def pad_chords(dur, freqs=(130.8, 164.8, 196.0), seed=5):
    n = int(SR*dur); t = np.arange(n)/SR; out = np.zeros(n)
    for i, f in enumerate(freqs):
        for det in (-0.003, 0, 0.003):
            out += np.sin(2*np.pi*f*(1+det)*t)*0.3
    env = np.minimum(1, t/2.0)*np.minimum(1, (dur-t)/2.0)
    return out*env/max(1, len(freqs))*0.35

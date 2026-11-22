"""Apni ambience — bina kisi sample ke (numpy se): barish, hawa, jhingur, nadi."""
import numpy as np
SR = 22050

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


def birds(dur, seed=9):
    """chidaiyan — chhote chirp bursts (random, high)."""
    import numpy as np
    n=int(SR*dur); t=np.arange(n)/SR
    out=np.zeros(n); rng=np.random.default_rng(seed)
    for _ in range(max(2,int(dur*1.2))):
        i=rng.integers(0,max(1,n-int(0.15*SR)))
        L=int(0.06*SR); tt=np.arange(L)/SR
        f0=rng.uniform(2200,3600)
        chirp=np.sin(2*np.pi*(f0+1200*tt/L*3)*tt)*np.exp(-tt*18)*0.10
        out[i:i+L]+=chirp
    return out

def footsteps(dur, seed=10, rate=1.8):
    """kadmon ki awaaz — dheeme thump (zameen par)."""
    import numpy as np
    n=int(SR*dur); out=np.zeros(n); rng=np.random.default_rng(seed)
    step=int(SR/rate)
    for i in range(0,n-step,step):
        L=int(0.09*SR); tt=np.arange(L)/SR
        th=np.sin(2*np.pi*(90+40*np.exp(-tt*30))*tt)*np.exp(-tt*22)*0.22
        th+=rng.normal(0,1,L)*np.exp(-tt*60)*0.04
        out[i:i+L]+=th
    return out


def air(dur, seed=12, level=0.030):
    """halka high-frequency air — recording ki natural chamak (bina chubhe)."""
    import numpy as np
    n=int(SR*dur); x=np.random.default_rng(seed).normal(0,1,n)
    x=np.diff(np.concatenate([[0],x]))          # high-pass
    x=np.diff(np.concatenate([[0],x]))
    lfo=0.8+0.2*np.sin(2*np.pi*0.06*np.arange(n)/SR)
    return x*lfo*level


# ---------- zameen ke hisaab se kadam (band-shaped: asli material jaisa)
def _band(x, lo, hi):
    """FFT band-limit — material ka character (mitti dull, patthar teekha)."""
    import numpy as np
    n=len(x); X=np.fft.rfft(x); f=np.fft.rfftfreq(n,1/SR)
    m=np.ones_like(f)
    m*= 1/(1+(lo/(f+1e-9))**4)          # high-pass at lo
    m*= 1/(1+(f/hi)**4)                 # low-pass at hi
    return np.fft.irfft(X*m,n)

def _steps(dur, rate, body_hz, band, noise_amt, decay, seed, squelch=0.0):
    import numpy as np
    n=int(SR*dur); out=np.zeros(n); rng=np.random.default_rng(seed)
    step=max(1,int(SR/rate))
    for i in range(0, max(1,n-step), step):
        L=int(min(0.22, 3.5/rate)*SR); t=np.arange(L)/SR
        thud=np.sin(2*np.pi*(body_hz+body_hz*0.4*np.exp(-t*30))*t)*np.exp(-t*decay)
        nz=rng.normal(0,1,L)
        if squelch:
            nz=np.convolve(nz,np.ones(30)/30,mode="same")*(1+squelch*np.sin(2*np.pi*9*t))
        nz=_band(nz, band[0], band[1])*noise_amt
        out[i:i+L]+=(thud*0.55+nz)*np.exp(-t*6)
    return out

def steps_dirt(dur, seed=21, rate=1.7):
    """kachchi mitti — dull thud, grit kam (centroid ~300–700)."""
    return _steps(dur, rate, 78, (60, 900), 0.22, 22, seed)

def steps_concrete(dur, seed=22, rate=1.9):
    """pakka farash — teekha click (centroid ~2500–4000)."""
    return _steps(dur, rate, 150, (900, 6000), 0.55, 60, seed)

def steps_leaves(dur, seed=23, rate=1.8):
    """sookhe patte — chhar-chhar (centroid ~4500–7000)."""
    return _steps(dur, rate, 110, (2500, 11000), 0.75, 18, seed)

def steps_grass(dur, seed=24, rate=1.7):
    """ghaas — soft swish (centroid ~1200–2200)."""
    return _steps(dur, rate, 95, (500, 2600), 0.45, 16, seed)

def steps_wood(dur, seed=25, rate=1.8):
    """lakdi/seedhi — resonant knock (centroid ~600–1100)."""
    return _steps(dur, rate, 260, (200, 1400), 0.28, 34, seed)

def steps_mud(dur, seed=26, rate=1.5):
    """keechad — geela squelch, dheema (centroid ~250–500)."""
    return _steps(dur, rate, 88, (60, 700), 0.35, 14, seed, squelch=1.0)

def steps_gravel(dur, seed=27, rate=1.9):
    """kankad — chhote patthar (centroid ~1800–3200)."""
    return _steps(dur, rate, 120, (700, 4200), 0.60, 40, seed)


def leaves(dur, seed=31, level=0.14):
    """patton ki sarsarahat — halki broadband rustle (wind ke saath)."""
    import numpy as np
    n=int(SR*dur); x=np.random.default_rng(seed).normal(0,1,n)
    x=np.diff(np.concatenate([[0],x]))
    lfo=0.6+0.4*np.abs(np.sin(2*np.pi*0.25*np.arange(n)/SR))
    return x*lfo*level

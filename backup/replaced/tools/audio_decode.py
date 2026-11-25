import numpy as np
def decode(path, sr=16000, secs=None):
    """kisi bhi format ko 16k mono float32 me laao (miniaudio -> soundfile fallback)."""
    try:
        import miniaudio
        d = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.FLOAT32,
                                  nchannels=1, sample_rate=sr)
        x = np.asarray(d.samples, dtype=np.float32)
        return np.ascontiguousarray(x[:sr*secs] if secs else x)
    except Exception:
        pass
    try:
        import av
        chunks=[]; rate=None
        with av.open(path) as c:
            if c.streams.audio:
                for fr in c.decode(c.streams.audio[0]):
                    a=fr.to_ndarray()
                    if a.ndim>1: a=a.mean(axis=0)
                    rate=fr.sample_rate; chunks.append(a.astype("float32"))
                    if secs and sum(len(x) for x in chunks)>rate*secs: break
        if chunks and rate:
            x=np.concatenate(chunks)
            if rate!=sr:
                idx=np.linspace(0,len(x)-1,int(len(x)*sr/rate)).astype(np.int64); x=x[idx]
            return np.ascontiguousarray(x[:sr*secs] if secs else x, dtype=np.float32)
    except Exception:
        pass
    try:
        import soundfile as sf
        x, r = sf.read(path, dtype="float32", always_2d=False)
        if x.ndim > 1: x = x.mean(axis=1)
        if r != sr:
            idx = np.linspace(0, len(x)-1, int(len(x)*sr/r)).astype(np.int64); x = x[idx]
        return np.ascontiguousarray(x[:sr*secs] if secs else x, dtype=np.float32)
    except Exception:
        return None

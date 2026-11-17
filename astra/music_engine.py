"""Original procedural music generator (12 moods) — ASTRA ke liye adapted.
Creates new note sequences and synthesized timbres; it does not sample or reproduce stock tracks.
This is a musical prototype engine, not a replacement for a neural composition model or human composer.
"""
from __future__ import annotations
import math, random, wave, struct
from pathlib import Path
AUDIO_DIR = Path(__file__).resolve().parent.parent / 'storage' / 'audio'
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

RATE=24000
SCALES={
 "minor":[0,2,3,5,7,8,10], "major":[0,2,4,5,7,9,11],
 "dorian":[0,2,3,5,7,9,10], "pentatonic":[0,2,4,7,9],
 "phrygian":[0,1,3,5,7,8,10]
}
PROFILES={
 "horror": {"bpm":72,"scale":"phrygian","root":45,"style":"dark","energy":.24,"layers":["pad","pulse","bell"]},
 "suspense":{"bpm":88,"scale":"minor","root":48,"style":"tension","energy":.32,"layers":["pad","pulse","plucks"]},
 "romance":{"bpm":76,"scale":"major","root":48,"style":"warm","energy":.32,"layers":["piano","strings","pad"]},
 "emotional":{"bpm":68,"scale":"minor","root":50,"style":"warm","energy":.30,"layers":["piano","strings","pad"]},
 "action":{"bpm":124,"scale":"minor","root":43,"style":"drive","energy":.52,"layers":["pulse","bass","drums","brass"]},
 "adventure":{"bpm":112,"scale":"major","root":50,"style":"bright","energy":.44,"layers":["plucks","strings","drums","brass"]},
 "fantasy":{"bpm":92,"scale":"dorian","root":48,"style":"mystic","energy":.34,"layers":["pad","bell","strings"]},
 "comedy":{"bpm":116,"scale":"major","root":55,"style":"playful","energy":.34,"layers":["plucks","piano","bass"]},
 "meditation":{"bpm":58,"scale":"pentatonic","root":48,"style":"calm","energy":.16,"layers":["pad","bell"]},
 "documentary":{"bpm":94,"scale":"major","root":48,"style":"neutral","energy":.28,"layers":["piano","pad","strings"]},
 "corporate":{"bpm":108,"scale":"major","root":52,"style":"bright","energy":.32,"layers":["piano","plucks","bass"]},
 "nature":{"bpm":70,"scale":"pentatonic","root":50,"style":"calm","energy":.18,"layers":["pad","plucks","bell"]}
}
def _freq(midi): return 440.0*2**((midi-69)/12)
def _env(t,d,attack=.04,release=.18):
    return min(1,t/max(.001,attack))*min(1,max(0,d-t)/max(.001,release))
def _voice(kind, freq, dur, seed, rate=RATE):
    rng=random.Random(seed); n=max(1,int(dur*rate)); a=[0.0]*n
    for i in range(n):
        t=i/rate; env=_env(t,dur, .08 if kind in ("pad","strings") else .008, .32 if kind in ("pad","strings") else .12)
        ph=2*math.pi*freq*t
        if kind=="pad": v=.58*math.sin(ph)+.22*math.sin(ph*2.01)+.10*math.sin(ph*.5)
        elif kind=="strings": v=.65*math.sin(ph)+.20*math.sin(ph*1.006)+.08*math.sin(ph*2)
        elif kind=="piano":
            v=math.sin(ph)*math.exp(-t*3.2)+.28*math.sin(ph*2.01)*math.exp(-t*6)
        elif kind=="bell":
            v=math.sin(ph)*math.exp(-t*2.6)+.35*math.sin(ph*2.76)*math.exp(-t*5.5)
        elif kind=="bass": v=.8*math.sin(ph)+.12*math.sin(ph*2)
        elif kind=="brass": v=.55*math.sin(ph)+.24*math.sin(ph*2)+.12*math.sin(ph*3)
        elif kind=="drums":
            v=(rng.random()*2-1)*math.exp(-t*24)+.35*math.sin(2*math.pi*55*t)*math.exp(-t*18)
        elif kind=="pulse":
            v=math.sin(ph)+.22*math.sin(ph*2)
            v*=.5+.5*math.sin(2*math.pi*2.0*t)**8
        else: v=math.sin(ph)
        a[i]=v*env
    return a
def generate_music(mood="suspense", seconds=30, intensity=None, seed=2026, bpm=None):
    if mood not in PROFILES: raise ValueError("Unknown mood. Choose: "+", ".join(PROFILES))
    if not 8<=seconds<=180: raise ValueError("Music duration must be 8..180 seconds")
    p=PROFILES[mood]; bpm=int(bpm or p["bpm"])
    if not 40<=bpm<=180: raise ValueError("BPM must be 40..180")
    energy=float(p["energy"] if intensity is None else max(.05,min(.8,float(intensity))))
    rng=random.Random(seed); total=int(seconds*RATE); left=[0.0]*total; right=[0.0]*total
    scale=SCALES[p["scale"]]; beat=60/bpm; bar=beat*4
    # New progression chosen for this render; no existing recording or song is sampled.
    progressions={
      "minor":[0,5,3,6],"major":[0,4,5,3],"dorian":[0,3,4,0],
      "pentatonic":[0,4,5,0],"phrygian":[0,1,5,6]
    }
    prog=progressions[p["scale"]]
    chord_events=[]
    for bi,start in enumerate([i*bar for i in range(int(seconds/bar)+1)]):
        degree=prog[bi%len(prog)]; chord=[p["root"]+scale[(degree+j)%len(scale)] for j in (0,2,4)]
        chord_events.append((start,chord))
    events=[]
    for bi,(start,chord) in enumerate(chord_events):
        d=min(bar+.04,seconds-start)
        if d<=0: continue
        # Slow harmonic bed, with evolving voicing and panning.
        for j,note in enumerate(chord):
            events.append((start,"pad",_freq(note+12),d*.99,.17,(-.35+j*.35),bi*31+j))
            if "strings" in p["layers"]:
                events.append((start,"strings",_freq(note+12),d*.92,.11,(j-1)*.32,bi*37+j))
        # Bass pulse / rhythmic foundation
        if "bass" in p["layers"] or p["style"] in ("drive","tension"):
            events.append((start,"bass",_freq(chord[0]-12),min(beat*.92,seconds-start),energy*.40,0,bi*41))
        # Melody motif, generated from scale and current chord
        if "piano" in p["layers"] or "plucks" in p["layers"] or "bell" in p["layers"]:
            step=beat*(.5 if p["style"] in ("playful","drive") else 1)
            count=max(1,int(bar/step))
            for k in range(count):
                at=start+k*step
                if at>=seconds: continue
                if mood=="horror" and rng.random()<.56: continue
                note=rng.choice(chord)+rng.choice([0,12,12,19])
                kind="bell" if "bell" in p["layers"] and (mood in ("horror","fantasy","meditation","nature")) else ("piano" if "piano" in p["layers"] else "plucks")
                length=min(step*.8,seconds-at)
                events.append((at,kind,_freq(note),length,energy*(.36 if kind=="bell" else .30),rng.uniform(-.7,.7),bi*101+k))
        # Drums only where appropriate
        if "drums" in p["layers"]:
            for k in range(4):
                at=start+k*beat
                if at<seconds:
                    events.append((at,"drums",_freq(35 if k%2==0 else 43),min(.22,seconds-at),energy*.36,0,bi*131+k))
    for start,kind,freq,dur,gain,pan,s in events:
        snd=_voice(kind,freq,dur,seed+s)
        off=int(start*RATE); pan=max(-1,min(1,pan))
        lg=math.sqrt((1-pan)/2); rg=math.sqrt((1+pan)/2)
        for j,v in enumerate(snd):
            ix=off+j
            if ix>=total: break
            # section envelope prevents abrupt musical edges
            fade=min(1,(ix/(RATE*.6)),((total-ix)/(RATE*.8)))
            v*=gain*fade*.32
            left[ix]+=v*lg; right[ix]+=v*rg
    path=AUDIO_DIR/f"music_{mood}_{seed}_{seconds}s.wav"
    with wave.open(str(path),"wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(RATE)
        frames=bytearray()
        for l,r in zip(left,right):
            frames += struct.pack("<hh",int(math.tanh(l*1.8)*32767),int(math.tanh(r*1.8)*32767))
        wf.writeframes(frames)
    return path, {"mood":mood,"bpm":bpm,"scale":p["scale"],"duration_seconds":seconds,"seed":seed,"layers":p["layers"]}

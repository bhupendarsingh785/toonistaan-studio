#!/usr/bin/env python3
"""Hindi awaaz banao. Kram: edge-tts (free, internet) -> warna khamosh placeholder + saaf sandesh.
python tts.py "Namaste dosto" out.mp3 [voice] [rate]
Voices: hi-IN-SwaraNeural (ladki), hi-IN-MadhurNeural (ladka). Rate jaise "-5%" ya "+10%".
Behtar bhaav ke liye: Indic Parler-TTS (GPU/Colab) - colab_parler.md dekho."""
import sys, subprocess, shutil, asyncio

def edge(text, out, voice, rate):
    import edge_tts
    async def go(): await edge_tts.Communicate(text, voice, rate=rate).save(out)
    asyncio.run(go())

def silence(out, secs):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(secs), out], check=True)

def speak(text, out, voice="hi-IN-MadhurNeural", rate="+0%"):
    try:
        edge(text, out, voice, rate); return "edge-tts"
    except ImportError:
        msg = "edge-tts install nahi (pip install edge-tts --break-system-packages, internet chahiye)"
    except Exception as e:
        msg = f"edge-tts fail: {e}"
    secs = max(1.2, len(text.split()) * 0.42)
    silence(out, secs)
    print(f"⚠️ {msg}. Placeholder khamoshi ({secs:.1f}s) lagayi.")
    return "silence"

if __name__ == "__main__":
    a = sys.argv[1:]
    print(speak(a[0], a[1], *(a[2:4])))

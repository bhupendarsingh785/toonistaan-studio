
"""Optional FFmpeg assembly for mixed per-character audio chunks and natural pauses."""
import subprocess, shutil, wave, struct


def _ffmpeg():
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


from pathlib import Path

def make_silence(path, duration_ms, sample_rate=24000):
    n=int(sample_rate*duration_ms/1000)
    with wave.open(str(path),"wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sample_rate)
        block=struct.pack("<h",0)*min(n,24000)
        remaining=n
        while remaining:
            take=min(remaining,24000)
            w.writeframes(block[:take*2]); remaining-=take

def assemble_wav(parts, output_path, sample_rate=24000):
    ffmpeg=_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg not installed; individual chunks remain available.")
    output=Path(output_path); output.parent.mkdir(parents=True,exist_ok=True)
    normalized=[]
    for i,part in enumerate(parts):
        p=Path(part)
        wav=output.parent/f".norm_{i:05d}.wav"
        subprocess.run([ffmpeg,"-y","-loglevel","error","-i",str(p),"-ac","1","-ar",str(sample_rate),"-c:a","pcm_s16le",str(wav)],check=True,timeout=90)
        normalized.append(wav)
    concat=output.parent/".concat_list.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in normalized),encoding="utf-8")
    try:
        subprocess.run([ffmpeg,"-y","-loglevel","error","-f","concat","-safe","0","-i",str(concat),"-c:a","pcm_s16le",str(output)],check=True,timeout=180)
    finally:
        for p in normalized:
            try:p.unlink()
            except OSError:pass
        try:concat.unlink()
        except OSError:pass
    if not output.exists() or output.stat().st_size<100:
        raise RuntimeError("Audio assembly did not produce a valid WAV.")
    return str(output)

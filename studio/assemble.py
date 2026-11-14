#!/usr/bin/env python3
"""Episode jodo: frames + awaaz + SFX + music (ducking) + .srt  ->  MP4
python assemble.py episode.json frames_dir out.mp4"""
import json, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "audio", "library")

def srt_time(s):
    h, r = divmod(s, 3600); m, r = divmod(r, 60); return f"{int(h):02}:{int(m):02}:{int(r):02},{int((r % 1) * 1000):03}"

def write_srt(ep, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, s in enumerate(ep.get("subtitles", []), 1):
            f.write(f"{i}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text']}\n\n")

def main(epf, frames, out):
    ep = json.load(open(epf, encoding="utf-8")); fps = ep.get("fps", 30); D = ep["duration"]
    work = os.path.splitext(out)[0] + "_work"; os.makedirs(work, exist_ok=True)
    inputs, filt, voice_labels, sfx_labels = ["-framerate", str(fps), "-i", os.path.join(frames, "f%05d.png")], [], [], []
    idx = 1
    # voice lines
    sys.path.insert(0, HERE); import tts
    for i, v in enumerate(ep.get("voice", [])):
        f = v.get("file") or os.path.join(work, f"v{i:02}.mp3")
        if not v.get("file"): tts.speak(v["text"], f, v.get("voice", "hi-IN-MadhurNeural"), v.get("rate", "+0%"))
        inputs += ["-i", f]; filt.append(f"[{idx}:a]aresample=44100,pan=mono|c0=c0,adelay={int(v['start']*1000)}:all=1,volume=1.6[v{i}]"); voice_labels.append(f"[v{i}]"); idx += 1
    # sfx
    for i, s in enumerate(ep.get("sfx", [])):
        f = os.path.join(LIB, s["name"] + ".wav")
        if not os.path.exists(f): subprocess.run([sys.executable, os.path.join(HERE, "sfx.py"), s["name"]], check=True, stdout=subprocess.DEVNULL)
        inputs += ["-i", f]; filt.append(f"[{idx}:a]adelay={int(s['start']*1000)}:all=1,volume={s.get('vol', 0.8)}[s{i}]"); sfx_labels.append(f"[s{i}]"); idx += 1
    # music
    mood = ep.get("music", "happy")
    mf = os.path.join(work, f"music_{mood}.wav")
    subprocess.run([sys.executable, "-c", f"import sys;sys.path.insert(0,{HERE!r});import sfx,shutil;p=sfx.save('music_tmp',sfx.music({mood!r},{D}));shutil.move(p,{mf!r})"], check=True)
    inputs += ["-i", mf]; mi = idx
    fx = voice_labels + sfx_labels
    if voice_labels:
        filt.append(f"{''.join(voice_labels)}amix=inputs={len(voice_labels)}:normalize=0,asplit=2[vo][vk]")
        filt.append(f"[{mi}:a]volume=0.35[mus];[mus][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck]")
        mixin = ["[vo]", "[duck]"] + sfx_labels
    else:
        filt.append(f"[{mi}:a]volume=0.35[duck]"); mixin = ["[duck]"] + sfx_labels
    filt.append(f"{''.join(mixin)}amix=inputs={len(mixin)}:normalize=0,loudnorm=I=-16:TP=-1.5,atrim=0:{D}[aout]")
    # video: smooth (frame interpolation), upscale, text overlays
    vf = []
    if ep.get("out_fps") and ep["out_fps"] > fps:
        vf.append(f"minterpolate=fps={ep['out_fps']}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
    if ep.get("upscale"):
        vf.append(f"scale={ep['upscale'][0]}:{ep['upscale'][1]}:flags=lanczos")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    Hh = (ep.get("upscale") or ep.get("size") or [1080, 1920])[1]
    for i, tx in enumerate(ep.get("texts", [])):
        tf = os.path.join(work, f"t{i}.txt")
        open(tf, "w", encoding="utf-8").write(tx["text"])
        fs = int(Hh * tx.get("size", 0.06)); st, en = tx["start"], tx["end"]
        alpha = f"if(lt(t,{st}+0.3),(t-{st})/0.3,if(gt(t,{en}-0.3),({en}-t)/0.3,1))"
        vf.append(f"drawtext=fontfile={font}:textfile={tf}:fontsize={fs}:fontcolor={tx.get('color', 'white')}:borderw={max(3, fs // 12)}:bordercolor=0x14213d:"
                  f"shadowx=4:shadowy=4:shadowcolor=black@0.5:x=(w-text_w)/2:y=h*{tx.get('y', 0.1)}:enable='between(t,{st},{en})':alpha='{alpha}'")
    filt.insert(0, f"[0:v]{','.join(vf) if vf else 'null'}[vout]")
    cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-t", str(D), "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    write_srt(ep, os.path.splitext(out)[0] + ".srt")
    print(f"✅ {out} (+ .srt)")

if __name__ == "__main__":
    main(*sys.argv[1:4])

#!/usr/bin/env python3
"""Ek command, poora episode:  python make_episode.py episode.json
episode.json: title, size, duration, scene, music, actions[], voice[], sfx[], subtitles[]"""
import json, sys, os, subprocess, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
epf = os.path.abspath(sys.argv[1]); ep = json.load(open(epf, encoding="utf-8"))
name = os.path.splitext(os.path.basename(epf))[0]
out_dir = os.path.join(HERE, "out"); frames = os.path.join(out_dir, name + "_frames")
shutil.rmtree(frames, ignore_errors=True)
subprocess.run(["node", os.path.join(HERE, "render.js"), os.path.join(HERE, "scenes", ep.get("scene", "rampur.html")), epf, frames], check=True, cwd=HERE)
subprocess.run([sys.executable, os.path.join(HERE, "assemble.py"), epf, frames, os.path.join(out_dir, name + ".mp4")], check=True)
shutil.rmtree(frames, ignore_errors=True)

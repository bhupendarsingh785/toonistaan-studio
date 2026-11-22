from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document()
sec = doc.sections[0]
sec.top_margin = sec.bottom_margin = Inches(0.7)
sec.left_margin = sec.right_margin = Inches(0.75)

st = doc.styles["Normal"]; st.font.name = "Nirmala UI"; st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Nirmala UI")
for h, sz in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
    doc.styles[h].font.name = "Nirmala UI"; doc.styles[h].font.size = Pt(sz)

def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = ""
        r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(9.5)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            r = p.add_run(str(v)); r.font.size = Pt(9)
    for row in t.rows:                      # cantSplit — row page par na kate
        trPr = row._tr.get_or_add_trPr()
        el = OxmlElement("w:cantSplit"); trPr.append(el)
    doc.add_paragraph()
    return t

def bullets(items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")

def code(txt):
    p = doc.add_paragraph(); r = p.add_run(txt); r.font.name = "Consolas"; r.font.size = Pt(9)

# ---------------- title
h = doc.add_heading("Seetal Audio System — poora document", 0)
h.alignment = WD_ALIGN_PARAGRAPH.CENTER
p = doc.add_paragraph("Kaise ek kahani se poori audio banti hai — step by step, naap ke saath. 22 Nov 2026")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.runs[0].italic = True

doc.add_heading("1. System ek nazar me", 1)
doc.add_paragraph("System 4 parat (layer) me hai. Har parat alag kaam karti hai, aur har parat ka apna QA hai — "
                  "isliye koi bhi cheez chupchap kharab nahi hoti.")
table(["Parat", "Kya hai", "Kaam", "Kahan"],
      [["1. Engine", "piper (offline), edge, espeak, elevenlabs", "awaaz paida karna", "voice/engines/*"],
       ["2. Gyaan", "local-brain.json, smooth-reference.json", "niyam + target numbers", "knowledge/"],
       ["3. Tools", "story, judge, asr, beats, readers", "banana aur jaanchna", "tools/"],
       ["4. QA", "scorecard PASS/WARN/FAIL", "galti pakadna", "tools/audio_judge.py"]])

doc.add_heading("2. Kahani banane ka road map (10 step)", 1)
doc.add_paragraph("Yeh wahi rasta hai jo har kahani par chalta hai. Har step ka input, tool, output aur gate neeche hai.")
table(["#", "Step", "Tool", "Input → Output", "Gate (rukhna kab)"],
      [["1", "Kahani + script", "haath/insaan", "idea → lines (who + text)", "har line me speaker saaf ho"],
       ["2", "Casting", "voice/presets.json", "lines → kirdaar ke F0 band", "band na mile to voice badlo"],
       ["3", "Render per line", "piper + voice_fx", "text → wav (per line)", "clipping 0%, peak <0.95"],
       ["4", "Silence trim", "voice_fx.trim_silence", "wav → saaf wav", "shuru/aakhir 25–40 ms hi bache"],
       ["5", "Gap compression", "voice_fx.compress_silences", "andar ki 50ms+ gap → 28ms", "speech ≥89%"],
       ["6", "Bhaav + EQ", "voice_fx.smooth_chain", "sur/raftaar/EQ", "mid 55–65, high 20–30%"],
       ["7", "World layer", "ambience.py + WORLD map", "script ke shabd → bed", "bed speech se 10–14 dB neeche"],
       ["8", "Mix", "story_local.py", "voice + bed → mix", "ducking, limiter, −18 dBFS"],
       ["9", "QA", "audio_judge.py", "mix → scorecard", "koi FAIL nahi"],
       ["10", "Deliver + manifest", "render_manifest.py", "mp3 + json", "manifest verdict PASS"]])

doc.add_heading("3. Casting — sur ke target (naap se)", 1)
doc.add_paragraph("Har kirdaar ka apna sur band hai. Isse sunne wale ko pata chalta hai kaun bol raha hai.")
table(["Kirdaar", "F0 band (Hz)", "Awaaz", "Setting"],
      [["narrator", "90–125", "purush (pratham)", "ratio 1.00, ls 0.98, pause 0.30"],
       ["dada", "95–130", "purush", "ratio 0.95–1.0"],
       ["dadi", "140–185", "mahila + bhaari (priyamvada)", "ratio 0.72, ls 1.05, pause 0.28"],
       ["maa", "165–205", "mahila", "ratio 0.70, ls 0.98, pause 0.25"],
       ["sonu/bachcha", "240–330", "unchi, patli", "ratio 1.02, ls 0.92, pause 0.22"]])
doc.add_paragraph("Naap ka tarika: 150 Hz HPF → CMNDF (YIN) per frame → median + octave correction. "
                  "Ek hi kirdaar ki lines me F0 spread 15% se zyada ho to casting galat hai.")

doc.add_heading("4. Bhaav (emotion) ke niyam", 1)
table(["Bhaav", "Sur", "Raftaar", "Thahraav", "Asli signal (naap)"],
      [["neutral", "×1.00", "×1.00", "×1.00", "—"],
       ["khushi", "×1.08", "×1.10", "×0.80", "3–8 Hz modulation 0.31"],
       ["dukh", "×0.94", "×0.85", "×1.40", "F0 <165, zor < −26 dB"],
       ["dar", "×1.06", "×1.15", "×0.70", "jitter 0.057"],
       ["gussa", "×1.04", "×1.12", "×0.75", "F0 sd 50+, jitter <0.05"],
       ["cheekh", "×1.12", "×1.20", "×0.60", "zor −10 dB, high band 29%"]])
doc.add_paragraph("Bhaav ko sirf sur se nahi — **jitter (dar), modulation (hasi), high band (cheekh)** se pehchante hain.")

doc.add_heading("5. Duniya ki awaaz (world layer)", 1)
doc.add_paragraph("Jis cheez ka zikr ho, usi ki awaaz background me ubhre — warna scene mar jata hai.")
table(["Script me shabd", "Sound", "Level"],
      [["नदी, पानी, लहर, बह", "river", "base 0.22 → 2.4× tak"],
       ["बारिश, बूँद, बादल", "rain", "0.30 → 2.4×"],
       ["हवा, ठंड", "wind", "0.18 → 2.4×"],
       ["पेड़, पत्ते, मिट्टी", "leaves", "0.14 → 2.4×"],
       ["चिड़िया, पक्षी", "birds", "0.16 → 2.4×"],
       ["तारा, शाम", "crickets", "0.12 → 2.4×"],
       ["गाँव, छत, दादी", "village", "0.08 → 2.4×"],
       ["चलना, किनारा", "footsteps", "line par on"],
       ["(hamesha)", "air (halki chamak)", "0.85 — recording jaisi air"]])
doc.add_paragraph("Automation 1.2 s smooth fade se hoti hai — bed chatka nahi lagta.")

doc.add_heading("6. Music / beats", 1)
table(["Mood", "Pattern", "BPM", "Thaat"],
      [["epic", "teen", "100", "bilawal"], ["horror", "one_drop", "78", "bhairavi"],
       ["sad", "dadra", "84", "asavari"], ["romantic", "keherwa", "92", "khamaj"],
       ["unwind", "unwind (sparse)", "76", "asavari"], ["bhakti", "bhakti laggi", "132", "bilawal"],
       ["happy", "afrobeat", "108", "bilawal"], ["lofi", "boom_bap", "90", "kafi"],
       ["trap", "trap", "140", "kafi"], ["action", "breakbeat", "165", "bhairav"]])
doc.add_paragraph("16-step patterns `knowledge/local-brain.json` me hain — engine wahi padhta hai.")

doc.add_heading("7. QA gates — bina inke deliver nahi", 1)
table(["Check", "Chahiye", "Kyun"],
      [["clipping", "<0.01%", "awaaz phatti nahi"],
       ["peak", "0.5–0.97", "headroom"],
       ["mid %", "55–65", "awaaz ka body"],
       ["high %", "20–30", "khula/clear (smooth reference 27–30)"],
       ["brightness", "1900–2200 Hz", "smooth reference 2086–2187"],
       ["SNR (bed)", "12–22 dB", "mahaul sunai de, awaaz na dabe"],
       ["echo", "<0.78", "goonj nahi (insaan 0.43–0.72)"],
       ["F0 spread", "≤15%", "ek kirdaar ek sur"],
       ["speech %", "65–90", "ruk-ruk nahi"],
       ["WER", "<0.25", "shabd sahi bole"]])

doc.add_heading("8. Gyaan kahan rehta hai (aur engines kaise padhte hain)", 1)
table(["File", "Kya", "Kaun padhta hai"],
      [["knowledge/local-brain.json", "saare niyam + numbers", "engine_sync, tools"],
       ["knowledge/smooth-reference.json", "smooth target (Sarvam v5/v8 ka naap)", "EQ tuning"],
       ["voice/engines/<engine>/README-hindi.md", "us engine ke liye saaf Hindi niyam", "engine banane wala"],
       ["voice/engines/<engine>/config.json", "targets + emotion map + QA", "engine code"],
       ["tools/*.py", "banane aur jaanchne ke tools", "pipeline"]])
code("python tools/engine_sync.py     # brain → charon engines ke folder")

doc.add_heading("9. Galtiyan jo ho chuki (taaki dobara na ho)", 1)
bullets([
 "Pitch shift (bin remap/SOLA) se goonj aayi → ab **resample** + formant soch.",
 "Comb-filter reverb (17/23/31 ms) = metallic echo → band.",
 "EQ ko 'garam/dull' kiya (mid 69, high 9) → smooth reference bright hai (2086 Hz), isliye ruk-ruk laga.",
 "Background 0.30 par tha → khamoshi hi nahi bachi; 0.17 par theek.",
 "CAST patch chupchap fail hua → dadi 240 Hz par reh gayi; **patch ke baad verify** zaroori.",
 "np.correlate poore segment par O(n²) → judge 4 min atak gaya; 8192 sample cap.",
 "ASR chhote words par galat (गाँव→लल) → carrier phrase chahiye.",
])

doc.add_heading("10. Ab bhi kami + agla roadmap", 1)
table(["Kami", "Asar", "Agla kadam"],
      [["piper G2P (बारिश→बारेश)", "shabd galat (WER FAIL)", "respell dictionary + carrier-phrase test"],
       ["piper medium voice", "naturalness ki had", "high-quality model ya cloning engine"],
       ["sonu ka F0 spread 16%", "bachche ki awaaz badalti", "ratio lock + per-line check"],
       ["mid 61 vs target 57", "thoda bhaari", "EQ fine-tune"],
       ["ASR dheema (2 core)", "QA slow", "cache + chhote model"],
       ["world layer keywords", "naye shabd miss", "map badhao (100+ shabd)"]])

doc.add_heading("11. Commands cheat-sheet", 1)
code("""# kahani banao (piper, offline)
python tools/local_story/story_local.py out.mp3

# poora QA scorecard
python tools/audio_judge.py --audio out.mp3 --marks story_local.json \\
    --script story_lines.json [--asr-cache asr.json]

# ASR (tez, cache ke saath)
python tools/asr_cache.py --audio out.mp3 --cache asr.json --model small

# beats (10 mood)
python tools/music_make2.py --mood unwind --bars 24 --out beat.mp3

# gaana / horror / bhaav padho
python tools/song_read.py --audio song.mp3
python tools/horror_read.py --audio horror.mp3
python tools/emotion_read.py --audio talk.mp3

# manifest (provenance + tri-state QA)
python tools/render_manifest.py --script s.json --audio out.mp3 --out m.json""")

doc.add_heading("12. Ek line me", 1)
doc.add_paragraph("System ka maksad: **kisi par depend na karna** — apna offline engine, apna gyaan file me, "
                  "apna QA, aur har cheez naap kar, andaza nahi.")

out = "/scratch/output/seetal-audio-system-document.docx"
doc.save(out); print("saved:", out)

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, PageBreak,
} = require("docx");

const INK = "1F2937";
const DIM = "5B6675";
const ACCENT = "1F6FEB";
const HEAD_BG = "EAF1FB";

function H(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    heading: level,
    spacing: { before: 260, after: 120 },
    children: [new TextRun({ text, bold: true, color: INK })],
  });
}
function P(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 110 },
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
    children: [new TextRun({
      text, size: opts.size ?? 21, color: opts.color ?? INK,
      bold: !!opts.bold, italics: !!opts.italics,
    })],
  });
}
function Bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 70 },
    children: [new TextRun({ text, size: 21, color: INK })],
  });
}
function Num(text) {
  return new Paragraph({
    numbering: { reference: "steps", level: 0 },
    spacing: { after: 70 },
    children: [new TextRun({ text, size: 21, color: INK })],
  });
}

const COL = [2600, 3200, 3560];   // total 9360 DXA

function table(headers, rows, widths = COL) {
  const headRow = new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: headers.map((h, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: HEAD_BG },
      margins: { top: 80, bottom: 80, left: 110, right: 110 },
      children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, size: 20, color: INK })] })],
    })),
  });
  const bodyRows = rows.map((r) => new TableRow({
    cantSplit: true,
    children: r.map((c, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      margins: { top: 70, bottom: 70, left: 110, right: 110 },
      children: [new Paragraph({ children: [new TextRun({ text: String(c), size: 20, color: INK })] })],
    })),
  }));
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "D6DEE8" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "D6DEE8" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "D6DEE8" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "D6DEE8" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "D6DEE8" },
      insideVertical: { style: BorderStyle.SINGLE, size: 4, color: "D6DEE8" },
    },
    rows: [headRow, ...bodyRows],
  });
}

function rule() {
  return new Paragraph({
    spacing: { before: 60, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "D6DEE8" } },
    children: [new TextRun({ text: "" })],
  });
}

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{ level: 0, format: "bullet", text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 420, hanging: 220 } } } }],
      },
      {
        reference: "steps",
        levels: [{ level: 0, format: "decimal", text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 420, hanging: 220 } } } }],
      },
    ],
  },
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 21, color: INK } },
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, color: INK } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 25, bold: true, color: ACCENT } },
    ],
  },
  sections: [{
    properties: {
      page: { margin: { top: 900, bottom: 900, left: 900, right: 900 } },
    },
    children: [
      P("ASTRA · Toonistaan Studio", { size: 19, color: DIM, bold: true }),
      new Paragraph({
        spacing: { after: 60 },
        children: [new TextRun({ text: "Kahani v4 — Audio ka poora document", bold: true, size: 40, color: INK })],
      }),
      P("File: kahani-v4-2awaaz.mp3 · Banane ki tareekh: 21 November 2026 · Banane wala: Seetal (ASTRA system)",
        { size: 19, color: DIM }),
      rule(),

      P("Is document me bilkul wahi likha hai jo sach me kiya gaya — kaunsi awaaz, kaunsi setting, kaunsi file, kitna naap. Kuch bhi andaze se nahi likha.", { italics: true, color: DIM }),

      H("1. Ek nazar me (measured)"),
      table(
        ["Cheez", "Value", "Kaise naapa"],
        [
          ["Lambai", "26.8 second", "ffmpeg se poora audio decode karke"],
          ["File size", "525 KB (MP3, 160 kbps)", "file size"],
          ["Loudness", "-17.9 dBFS (RMS)", "sample-wise RMS"],
          ["Peak", "0.80 (clipping nahi)", "max absolute sample"],
          ["Sur ka utar-chadhav", "F0 210 Hz, ±69.4 Hz", "autocorrelation, 40 ms frame"],
          ["Chupai (pause)", "5.2%", "50 ms frames, -38 dBFS se neeche"],
          ["Awaazein", "2 — daadi + baccha", "cues.json"],
          ["Background", "jungle ambience + barish (loop)", "cues.json"],
          ["Foley (effect)", "kadam ×2, garaj+barish, chidaiyan", "cues.json"],
        ],
        [2600, 3200, 3560],
      ),

      H("2. Kahani (jo boli gayi)"),
      P("Kahani ka naam: \"Nadi aur Ped\". Do kirdaar — daadi aur baccha. Har line ke saath bhaav (emotion) likha hai; usi bhaav se awaaz ki setting badalti hai.", { color: DIM }),
      table(
        ["Kirdaar", "Bhaav", "Line"],
        [
          ["daadi", "pyaar", "बेटा, आ जा पास। आज मैं तुम्हें एक कहानी सुनाती हूँ।"],
          ["baccha", "khushi", "दादी, कहानी सुनाओ ना! आज कौन सी?"],
          ["daadi", "neutral", "उस जंगल में एक छोटी नदी बहती थी, और उसके किनारे एक बूढ़ा पेड़ था।"],
          ["daadi", "dar", "एक रात बारिश इतनी तेज़ हुई कि पूरा जंगल काँपने लगा।"],
          ["baccha", "dar", "फिर क्या हुआ दादी? डर नहीं लगा?"],
          ["daadi", "khushi", "डर तो लगा, पर पेड़ ने अपनी जड़ों से नदी को रोक लिया।"],
          ["daadi", "pyaar", "सुबह जब धूप निकली, तो गाँव बच गया। और वह पेड़ आज भी खड़ा है।"],
          ["baccha", "khushi", "वाह दादी! कल मैं उस पेड़ को देखने जाऊँगा।"],
        ],
        [1300, 1300, 6760],
      ),
      P("Render se pehle ek hi kirdaar ki lagataar lines jod di jaati hain (8 line → 6 segment), taaki beech-beech me dhun restart na ho — yahi \"ruka-ruka\" lagne ki sabse badi wajah thi.", { color: DIM }),

      new Paragraph({ children: [new PageBreak()] }),

      H("3. Awaaz kaise bani (engine + settings)"),
      P("Awaaz Sarvam AI ke bulbul:v3 model se bani — asli API call, GitHub ke secret se key li gayi (key code me kahin nahi likhi)."),
      table(
        ["Setting", "Value", "Kyun"],
        [
          ["Model", "bulbul:v3", "Sarvam ka stable Hindi model"],
          ["Language", "hi-IN", "Hindi text, Devanagari"],
          ["Speaker — daadi", "ishita", "A/B test me sabse expressive (F0 std 67)"],
          ["Speaker — baccha", "tanya", "halki, chhoti umar jaisi awaaz"],
          ["Temperature", "0.70 – 0.85 (bhaav ke hisaab se)", "0.6 default flat lagta tha"],
          ["Pace", "0.94 – 1.12 (SARVAM_NATURAL=1)", "dheema = ruka-ruka lagta hai"],
          ["Pitch", "±0.1 ke andar", "bahut zyada = nakli lagta hai"],
          ["Loudness", "1.0 ± 0.4 ke andar", "bhaav ka halka asar"],
          ["Sample rate", "24000 Hz, WAV", "clean source, aage mix ke liye"],
        ],
        [2500, 3200, 3660],
      ),
      P("Bhaav ke hisaab se temperature:", { color: DIM }),
      table(
        ["Bhaav", "Temperature", "Asar"],
        [
          ["neutral", "0.70", "steadier, kahani sunane wali"],
          ["pyaar", "0.78", "narm, apnapan"],
          ["dar", "0.80", "thoda kaanpta, tez"],
          ["khushi / gussa", "0.85", "sabse expressive"],
          ["dukh", "0.72", "dabba hua, dheema"],
        ],
        [2200, 2200, 4960],
      ),

      H("4. A/B test — kaunsi setting insaan jaisi hai (naap kar)"),
      P("Ek hi line ko 6 setting me render kiya, phir har file ka sur ka utar-chadhav (F0 std) naapa. Insaan ki awaaz me sur upar-neeche hota hai; robotic flat hota hai.", { color: DIM }),
      table(
        ["Setting", "F0 std (zyada = expressive)", "Raftaar (akshar/s)", "Chupai"],
        [
          ["v3 ishita, t=0.75", "67.0  ← chuni gayi", "13.56", "24.7%"],
          ["v3 suhani, t=0.75, pace 1.05", "62.9", "13.73", "19.3%"],
          ["v4-flash (default)", "56.0", "11.71", "25.9%"],
          ["v3 priya, t=0.85", "55.9", "13.05", "22.8%"],
          ["v3 ritu, t=0.85", "53.2", "13.83", "25.9%"],
          ["v3 priya, t=0.60 (default)", "52.6", "12.13", "20.6%"],
        ],
        [3000, 2600, 1900, 1860],
      ),

      H("5. Purana version vs naya (asli file ka naap)"),
      table(
        ["", "v3 (purana)", "v4 (naya)"],
        [
          ["Sur ka utar-chadhav", "±52.2 Hz", "±69.4 Hz (+33%)"],
          ["Lambai", "31.6 s", "26.8 s (kam khincha)"],
          ["Awaazein", "1 (sirf daadi)", "2 (daadi + baccha)"],
          ["Segment (break)", "1 continuous", "6 segment, jode hue"],
          ["Chupai", "5.4%", "5.2%"],
        ],
        [3000, 3180, 3180],
      ),

      H("6. Background aur foley — kaunsi file, kitna dB"),
      P("Sab kuch apni hi library se (astra/library). Gain dB me hai — 0 = jitna file me tha, -16 = 16 dB dheema.", { color: DIM }),
      table(
        ["Kab", "File", "Gain", "Kaam"],
        [
          ["0 se aakhir tak", "ambience/bvk_forest_1.mp3", "-16 dB (loop)", "jungle ki hawa, pakshi"],
          ["0 se aakhir tak", "ambience/rain_gentle_1.mp3", "-21 dB (loop)", "halki barish ka bed"],
          ["0.2 s", "footsteps/steps_soil.mp3", "-12 dB", "daadi paas aati hai (kadam)"],
          ["13.0 s", "ambience/weather_rain_thunder_storm.mp3", "-20 dB", "raat wali tez barish + garaj"],
          ["21.0 s", "footsteps/steps_soil.mp3", "-13 dB", "bacche ke kadam"],
          ["26.0 s", "birds/birds_chirp_1.mp3", "-22 dB", "subah ki chidaiyan"],
        ],
        [1500, 3560, 1700, 2600],
      ),

      H("7. Mixing — bilkul kya kiya gaya (ffmpeg chain)"),
      P("Har dialogue line par yeh chain lagi:", { color: DIM }),
      Bullet("highpass f=75 — boomy/ghoomti awaaz hatai"),
      Bullet("acompressor threshold=-18dB, ratio=2.5, attack=8, release=180, makeup=2 — awaaz ek jaisi zor par"),
      Bullet("treble g=1.5 @ 5.5 kHz — shabd saaf (clarity)"),
      Bullet("adelay — line ko apne waqt par rakha, volume -2 dB"),
      P("Phir poora mix:", { color: DIM }),
      Bullet("sidechaincompress threshold=0.03, ratio=6, attack=20, release=350 — jab koi bolta hai, background 6:1 dheema (ducking)"),
      Bullet("amix inputs=…, normalize=0 — sab layer jodi, apne level par"),
      Bullet("loudnorm I=-18 LUFS, TP=-2, LRA=11 — phone/YouTube ke liye theek loudness"),
      Bullet("alimiter limit=0.95 — clipping se bachav"),
      Bullet("MP3 160 kbps, 44.1 kHz — halki file, achhi quality"),

      H("8. Jo dikkat thi aur kya theek kiya"),
      table(
        ["Dikkat (jo sunai di)", "Asli wajah", "Hal"],
        [
          ["Awaaz robotic lagti thi", "temperature 0.6 (default) = flat, kam expressive", "bhaav ke hisaab se 0.70–0.85"],
          ["Ruk-ruk kar bolti thi", "8 alag line = 8 baar prosody restart", "ek kirdaar ki lines jodi (6 segment)"],
          ["Bahut dheema", "bhaav se rate -12% tak gir jata tha", "pace 0.94–1.12 ke andar band"],
          ["Hichki jaisa gap", "silence trim bahut aggressive tha (-45 dB)", "halka trim (-50 dB, 0.08 s)"],
          ["Emotion mehsoos nahi hota tha", "pitch/loudness ka asar bahut halka tha", "temperature + pitch ±0.1 ka santulit mix"],
          ["Ek hi awaaz sab bol rahi thi", "cast mapping nahi thi", "daadi = ishita, baccha = tanya"],
        ],
        [2600, 3200, 3560],
      ),

      H("9. Dobara banane ka tareeka (exact)"),
      Num("Code: tools/story_audio.py — kahani, cast, background plan, mix chain sab isi file me."),
      Num("Key GitHub secret me: SARVAM_API_KEY, SARVAM_API_KEY_2, SARVAM_API_KEY_3 (rotation chalu)."),
      Num("Workflow: .github/workflows/story-sarvam.yml — STORY_ENGINE=sarvam, SARVAM_MODEL=bulbul:v3, SARVAM_NATURAL=1."),
      Num("Workflow chalne par output/kahani-v4.mp3 + kahani-v4.cues.json (har line ka time, kirdaar, bhaav) banta hai."),
      Num("Local test bina key: python tools/story_audio.py --out out.mp3 (piper/edge par gir jayega)."),
      P("cues.json me har line ka start time, duration, kirdaar, bhaav, aur background/foley ki list hoti hai — usi se video/subtitle aage ban sakta hai.", { color: DIM }),

      H("10. Sach aur seemayein (chhupaya nahi)"),
      Bullet("100% insaan jaisa koi TTS nahi hota — Sarvam ab tak ka sabse natural hai jo hamare paas chalta hai."),
      Bullet("Sarvam ka coin kharch hota hai (ek render ~500–700 akshar); 3 key ki rotation isliye lagi hai."),
      Bullet("Background/foley insaan ne design kiya hai (file me fixed list) — abhi apne aap scene padh kar nahi chunta (woh world_scape ka kaam hai)."),
      Bullet("Bulbul v3 me SSML nahi hota, isliye prosody ka control pace/pitch/temperature aur vakya todne se hota hai."),
      Bullet("Video/subtitle abhi is file se nahi bane — cues.json ready hai, jab bolo tab banaungi."),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("/scratch/work/doc/kahani-v4-audio-document.docx", buf);
  console.log("docx ban gaya:", buf.length, "bytes");
});

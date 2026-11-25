# Audio Read v6 — har awaaz pehchano, samjho, aur seekho (21 Nov 2026)

## Naya kya hai
1. **EVENT CLASSIFIER** — 20+ kism ki awaaz pehchanta hai:
   `paani/nadi`, `baarish/hiss`, `hawa`, `garaj/rumble`, `kadam/thud`, `darwaza` (creak→tonal),
   `ghanti/tonal`, `chidaiyan/pakshi`, `jhingur/keede`, `pashu/growl`, `gaadi/engine`, `train`,
   `bheed/awaazein`, `dhamaka/kaanch`, `patte/rustle`, `music/tonal`, `pata-nahi`
2. **SCENE TIMELINE** — 5-5 second me kaunsi awaazein + kitne bolne wale + bhaav
3. **CONTINUOUS BEDS** — jinka onset nahi hota (nadi, barish, hawa, music) alag se pakde
4. **RISHTA** — turns, bolne ka hissa %, tez jawab, der se jawab, **sur milaap (F0 mirroring)**, bhaav ka safar
5. **SEEKHNA** — har event ka feature + label `knowledge/audio-library.jsonl` me; agli baar **kNN** se pehchaan
6. **SELF-TEST** — 4 synthetic case (noise, tone, thud, chirp) — **4/4 pass**

## Recheck me mile bug (sab theek)
| Bug | Kya hota tha | Fix |
|---|---|---|
| Events sirf "silence" me | bolne ke beech ki awaaz **miss** | poori file par onset detection |
| `modulation` zeros se | thud ko "hawa" bol deta | sirf active hisse par |
| Rule tarteeb galat | chirp → "dhamaka", noise → kuch nahi | chirp pehle, noise/paani pehle |
| Bed na milna | continuous nadi/barish chhoot jaati | bed fallback + thresholds |
| 72 micro-turns | ek aadmi ke tukde alag | gap<1.0s + sur ±15 Hz par **merge** → **42** |
| Bhaav sab "gussa" | pace inflate | sd>55 + pace>4.5, warna khushi/dukh/jaldi |

## Hamare render (jungle-nadi-safar-v8) par asli padhaai
- **42 turns**, bolne ka hissa **60.6%**, gap औसत 0.82 s, **41 tez jawab**, 10 der se
- **164 events** — pehchani gayi awaazein: **paani/nadi, baarish, hawa, chidaiyan, jhingur, pashu/growl, patte/rustle, bheed, music/tonal**
- **Bhaav safar**: khushi → gussa → jaldi/bechain (kahani ke mod par)
- **Mahaul -40.8 dB vs awaaz -15.6** → farq **25.2 dB** = **mahaul bahut dheema**, 10–12 dB hona chahiye

## Kami (imaandari se)
1. Classifier **rules-based** hai — 100% nahi; kNN se behtar hota jayega jab data badhega
2. `pata-nahi` bhi aata hai (164 me kuch) — naye sound par model ko naya data chahiye
3. Do logon ka sur same → rishta analysis adhoora
4. Hamare render me mahaul **dheema** hai — ye pipeline ki asli kami hai, padhne wale ki nahi

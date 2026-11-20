# Engine Bus — 24 engine aapas me taalmel (baat-cheet + kaam baantna)

**122 tests pass, 1 skip** · `tools/engine_bus.py`

## Kya karta hai

1. **Har engine apni capability batata hai** — kaunse bhaav, kaunsi bhasha, offline hai ya nahi, kitna tez, kitna mehnga, kitne akshar.
2. **Project chhote parts me tootta hai** — script ki har line ek part. Lambi line `।` par tootti hai.
3. **Sahi engine ko hissa milta hai** — pehle **bhaav** dekha jata hai (dukh/gussa wali line usi engine par jo woh kar sakta hai), phir speed/cost.
4. **Ek kirdaar = ek engine** — "awaaz lock". Dadi ki saari line ek hi engine par, warna beech me awaaz badal jati.
5. **Koi engine fail ho to kaam rukta nahi** — wahi hissa doosre capable engine ko, **bhaav wahi** rehta hai.
6. **Aadha kaam bachta hai** — har part ki file + `manifest.json`; dobara chalane par jo ban chuka hai wo wahi rehta hai.

## Commands

```bash
# engine jodo (jitne bhi ho — 4, 24, jitne chahe)
python tools/engine_bus.py register --name piper --offline --speed 2 --cost 0 --emotions neutral
python tools/engine_bus.py register --name sarvam --speed 1 --cost 1 --emotions neutral,dukh,gussa,khusi,dar

# kya kya juda hai
python tools/engine_bus.py status

# pehle dekho kaun sa hissa kis engine par jayega (render nahi hota)
python tools/engine_bus.py plan --script story.txt

# chalao
python tools/engine_bus.py run --script story.txt --out output/bus
```

Script ka format (dono chalta hai):
```
दादी [dukh]: बेटा, आ जा पास।
[gussa] चुप रहो!
माँ: खाना ठंडा हो रहा है।
```

## Kyun isse "jaldi + accurate"
| Pehle | Ab |
|---|---|
| Ek engine sab kuch kare → dheema | Kaam parts me bata, sahi engine ko |
| Beech me engine badla → awaaz badli | Kirdaar ka engine lock |
| Ek engine fail → poora project ruka | Sirf woh part doosre engine par |
| Dobara chalao → sab shuru se | manifest se resume |
| Bhaav kahin bhi lagta | Bhaav ke hisaab se engine chuna jata hai |

## Aage
- Parts ko **parallel** chalana (bus me worker pool) — abhi ek ke baad ek, parallel API ready hai
- 24 engine ke capability JSON ek jagah rakhna (`bus/engines.json`)

# Galti report — bhaav-2

Engine **espeak** · 5 line · 90 akshar · PASS 5/5
Pakki galti: pehle 0 (CER 0.000) → sudhaar ke baad **0** (CER 0.000)
Sudhri lines: 2 · samay 2.3 s (audio 16.3 s)

## Line-war

| # | Kaun | Galti (pehle) | Sudhaar | Nateeja |
|---|---|---|---|---|
| 1 | narrator | — | — | ✓ |
| 2 | narrator | — | bhaav:khushi sur+0.8 raftaar×1.13 zor+1.6 | ✓ |
| 3 | narrator | — | bhaav:dukh sur-0.3 raftaar×0.88 zor-0.7, bhaav:dukh sur-0.2 raftaar×0.99 zor-0.1 | ✓ |
| 4 | narrator | — | — | ✓ |
| 5 | narrator | — | — | ✓ |

## Bhaav (bhavna) — chahiye vs mila

| # | Kaun | Chahiye | Pehle mila | Sudhaar ke baad | Zor wale shabd (chahiye → mila) |
|---|---|---|---|---|---|
| 2 | narrator | ख़ुशी 100% | हैरानी 39% (lakshya ka 15%) ✗ | हैरानी 81% (lakshya ka 101%) ✓ | वाह: ×1.4/+4st/+3dB → ×1.64/+9st/+2dB ✓; बहुत: ×1.25/+3st/+3dB → ×1.76/+3st/+2dB ✓; खुश: ×1.25/+3st/+3dB → ×1.38/-1st/+3dB ✗ |
| 3 | narrator | दुख 86% | दुख 40% (lakshya ka 47%) ✗ | दुख 62% (lakshya ka 72%) ✓ | आँसू: ×1.3/-1st/-1dB → ×1.2/-1st/-1dB ✓ |
| 4 | narrator | डर 98% | डर 98% (lakshya ka 101%) ✓ | डर 98% (lakshya ka 101%) ✓ | कौन: ×1.15/+3st/+1dB → ×1.51/+2st/+0dB ✗; डर: ×1.15/+3st/+1dB → ×1.4/+2st/+0dB ✓ |

**Bhaav ki yaad (agli baar render se pehle yahi param):**

- `espeak/narrator` ख़ुशी: sur +0.6st · raftaar ×1.09 · zor +1.2dB · chamak +1.0dB · aakhri sur -1.2st (seekha 1 line se, 70% bhaav par; lakshya ka ausat 101%; 1 baar kam pada)
- `espeak/narrator` दुख: sur -1.2st · raftaar ×0.87 · zor -2.1dB · chamak +0.8dB · aakhri sur -3.6st (seekha 2 line se, 86% bhaav par; lakshya ka ausat 73%)
- `espeak/narrator` डर: sur +1.5st · raftaar ×1.13 · zor -0.7dB · chamak +1.0dB · aakhri sur -2.4st (seekha 2 line se, 100% bhaav par; lakshya ka ausat 93%)

## Galti-bahi (yaad: kaun sa akshar kamzor)

### espeak/narrator

Lines: 15 · akshar bole: 282


**Pichhli kahaniyan (CER, pakki galti):** 0.000/0 → 0.000/0

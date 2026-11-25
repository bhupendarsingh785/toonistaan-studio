# ASTRA — Universal Sound Creation Engine

Kisi bhi cheez ki awaaz banao — **offline, bina internet, bina API key** (numpy se procedural synthesis).

## Chalao
```
python3 astra/astra.py banao "sukha patta pair ke neeche kuchal raha hai" -o out.wav
python3 astra/astra.py banao "mitti par bhaari kadam, paas se" -o out.wav --dur 3
python3 astra/astra.py banao "purana lakdi ka darwaza khul raha hai" -o out.wav --reverb 0.4
python3 astra/astra.py banao "rakshas ki dahaad, door se" -o out.wav --dist 20 --pan -0.5
python3 astra/astra.py list
python3 astra/astra.py pack -o pack/     # 12 demo sounds
```

## Departments (31 generators)
- **human**: footsteps (soil/gravel/stone/wood/snow/wet/leaves/concrete), laugh, cry, breath, scream, leaf_crush
- **animal**: dog, cat, bird, cricket, monster
- **nature**: leaves, rain, wind, water, water_drop, fire, thunder
- **object**: door (wood/metal), glass, metal, wood, paper, coins
- **machine**: engine, train, helicopter, machine
- **fictional**: magic, laser, explosion, monster

## Text se params apne aap
"sukha / geela / barf / patthar / lakdi / mitti" → material
"bhaari / dheere / tez" → weight + speed
"paas / door" → distance (lowpass + volume)
"baayein / daayein" → pan
"reverb" → kamre ki goonj

## Processing
distance → reverb (5-tap Schroeder) → EQ-free normalize → stereo pan → QA (peak, clipping, silence) → memory/index.json

## Niyam
- Sab kuch **local** — koi upload nahi, koi key nahi
- Koi generator internet par depend nahi karta
- Awaaz ka metadata `astra/memory/index.json` me jata hai (dobara kaam aata hai)

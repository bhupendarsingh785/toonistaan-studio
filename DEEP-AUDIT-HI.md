# Deep audit — naye tarike se poora system check (21 Nov 2026)

**system_check 19/19 · tests 193 pass · deep audit: 0 problem (chaaron engine)**

## Naye 7 tarike (`tools/deep_audit.py`)
| Tarika | Kya karta hai |
|---|---|
| **FUZZ** | 10 ajeeb text: emoji, HTML `<script>`, JSON, control chars `\x00`, mixed script, 5000 akshar, 200 emoji, sirf "।।।" |
| **IDEMPOTENT** | ek hi text do baar → **bilkul same file (bytes)** |
| **RACE** | 8 thread ek saath + state file ek saath likhna |
| **INJECTION** | `$(rm -rf /)`, `` `whoami` ``, `../../etc/passwd`, SQL, `%s%n` |
| **IMPORT** | 12 module, circular import + import time |
| **LEAK** | temp folder 200 MB se bada ho gaya? |
| **DISK** | 500 MB se kam jagah? |

## Mile 3 asli bug (sabse bada cache wala)
| # | Bug | Hal |
|---|---|---|
| 1 | **Cache kabhi hit hi nahi hota tha** — cache key me **file ka path** shamil tha, isliye har call naya key banata tha (0.93 s har baar, cache ka fayda zero) | key se `out` hataya → ab **0.09 s**, bytes same |
| 2 | **Cache hit par file maangi hui jagah par nahi aati thi** | `want=` param + copy (SameFile safe) |
| 3 | **Control chars (`\x00\x01`) par render fail** | naya `clean_text()` — control chars saaf, newline/tab rakhe |

## Nateeja (chaar engine)
| Engine | fuzz | idempotent | race | injection |
|---|---|---|---|---|
| free | ✅ | ✅ | ✅ | ✅ |
| espeak | ✅ | ✅ | ✅ | ✅ |
| piper | ✅ | ✅ | ✅ | ✅ |
| edge | ✅ | ✅ | ✅ | ✅ |

**Cache ka asar:** pehli call 0.93 s → dobara **0.09 s** (10x), file **byte-for-byte same**.

## Sach
- piper ka fuzz 54 s leta hai (10 test, 2 core) — sabse dheema.
- Injection test me system **safe** raha — shell/JSON/HTML kuch nahi chala.

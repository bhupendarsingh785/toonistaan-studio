# Vachak (narrator) ka andaaz — Swag ke niyam

1. **Awaaz ki nakal vachak nahi karega.**
   - Galat: "नदी कल-कल बह रही थी।"
   - Sahi:  "नदी बह रही थी।"  (कल-कल background layer se sunai dega)
2. **Detail utni hi, jitni background aur kirdaar nibha sakein.** Zyada likha to sunne wale ko
   kuch samajh nahi aata — jo likha hai wo awaaz me hona chahiye.
3. **Background ka kaam bolna hai, vachak ka nahi**: nadi, hawa, patte, kadam, bhediya — sab
   `world-map.json` ke keywords se ubharte hain, vachak ke shabdon se nahi.
4. **Doori/disha shabdon se aati hai** — "दूर कहीं", "पास", "पीछे से" likho to engine usi hisaab se
   level, dhundhlapan aur goonj lagata hai.
5. **Chhoti chhoti baatein yaad rakho**: kirdaar ka naam, jagah (जंगल/हॉल/गुफा), samay, mausam —
   inhi se scene banta hai.

Tool: `tools/narration_clean.py` — vachak ki line se nakal ke shabd hata deta hai
(`कल-कल, छन-छन, टप-टप, सरसर, गड़गड़, झरझर, फड़फड़ ...`) aur sutradhar me apne aap lagta hai.

# YouTube Studio Autopilot

Video ko queue mein daalo, aur yeh unhe aapke bataye samay (IST) par apne aap scheduled upload kar deta hai.
Ek se zyada channel, alag-alag Google ID par bhi chal jaate hain. Sirf Python chahiye, koi extra package nahi.

## Ek baar ka setup (har Google ID ke liye)

1. **console.cloud.google.com** kholein. Usi Google ID se login karein jiska channel hai.
2. Naya project banayein → **APIs & Services → Library** → "YouTube Data API v3" → **Enable**
3. **OAuth consent screen**: External chunein, app ka naam aur email bharein, phir **Publish app (In production)** dabayein.
   (Testing mode mein login 7 din mein expire ho jaata hai.)
4. **Credentials → Create credentials → OAuth client ID → Desktop app** → JSON download karein
5. Us file ko `secrets/client_secret.json` naam se rakhein. Ya Claude ko file bhej dein, wo rakh dega.

## Channel jodna

```
python studio.py add-channel kahani
python studio.py auth-url kahani        # link milega
```
Link kholein → sahi Google ID chunein → sahi **channel** chunein → Allow dabayein.
"Google hasn't verified this app" dikhe to **Advanced → Go to (app)** dabayein, kyunki yeh aapka hi app hai.
Uske baad page "nahi khula" dikhayega. **Address bar ka poora link** copy karein:
```
python studio.py auth-finish kahani "http://localhost/"
```

## Roz ka kaam

```
python studio.py enqueue kahani video.mp4 meta.json thumb.jpg subs.srt
python studio.py plan kahani --dry-run   # dekho kab-kab jayega
python studio.py plan kahani             # upload (scheduled)
python studio.py status
```

`config.json` mein har channel ke liye:
- `slots_ist`: upload ka samay, jaise `["10:00","14:00","18:00"]`
- `max_uploads_per_day`: rozana kitne video (free quota mein lagbhag 6 tak)
- `made_for_kids`, `category_id` (1 = Film & Animation), `default_tags`

## Zaroori niyam

- **Private lock:** naye (bina audit wale) API project se upload hue video private rehte hain.
  Public karne ke liye YouTube API audit form bharein. Tab tak YouTube Studio se khud public karein.
- **Custom thumbnail:** iske liye channel phone number se verified hona chahiye (youtube.com/verify).
- `secrets/` folder kabhi kisi ko na bhejein, aur GitHub par na daalein (`.gitignore` mein pehle se hai).
- AI awaaz/visuals wale video `contains_synthetic_media: true` ke saath jaate hain.

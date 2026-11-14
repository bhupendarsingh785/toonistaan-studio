---
name: "youtube-autopilot"
description: "Plans, builds and uploads videos to Arjun's YouTube channel on a schedule via the YouTube Data API. Use when asked to upload to YouTube, schedule uploads, or run the channel automatically."
---

# YouTube Autopilot

Arjun ke YouTube channel ko chalao: video banao (cartoon-movie-agent se), title/description/tags/thumbnail banao, aur tay samay par upload karo. Jawab simple Hinglish mein.

## Ek baar ka setup (user ke saath)
1. Google Cloud Console mein project, **YouTube Data API v3** enable, OAuth consent screen, OAuth Client (Desktop/Web).
2. User khud login karke Allow kare; milne wala **refresh token** sirf secret/env variable mein rakho — chat, repo ya file mein kabhi mat likho ya dikhao.
3. **Zaroori**: Google ka niyam — bina audit wale (unverified) API project se upload hue video **private lock** rehte hain. Public ke liye project ka **YouTube API audit** form bharwao. Jab tak audit na ho: video private/scheduled upload karo aur user ko YouTube Studio mein public karne ko kaho.
4. Quota: rozana 10,000 units; ek upload ~1,600 units, yaani lagbhag 6 upload/din. Zyada chahiye to quota badhane ka form.

## Channel plan
- User se lo: channel link, vishay/series, rozana kitne video, kis samay (IST).
- `channel/plan.md` mein likho: schedule, series, agle 7 din ke episode ideas.

## Har upload ka tarika
1. Plan se agla episode chuno; cartoon-movie-agent se video banao (series bible follow karo).
2. Title (Hindi + kuch English keywords), description (kahani, credits.md se music/SFX credit, hashtags), tags, Hindi subtitles (.srt), thumbnail (1280x720, bada Hindi text, kirdaar ka chehra).
3. Shorts ho to 9:16, 60s se kam, title/description mein #Shorts.
4. `videos.insert` se upload; samay ho to `status.publishAt` (UTC) ke saath private-scheduled. Thumbnail `thumbnails.set`, captions `captions.insert`.
5. Video ID, link, samay `channel/log.md` mein likho; user ko ek line ki report.
6. Fail ho (quota, token expire, upload error) to ek baar retry; phir user ko saaf batao kya karna hai.

## Automatic chalana
- User ke bataye samay ke liye scheduled task banao (har run nayi session hai, isliye prompt mein channel, series, plan file ka path, aur yeh skill use karne ki baat likho).
- Network access aur Google secret us environment mein hone chahiye; na ho to user ko batao.

## Channel ki suraksha (strike/demonetize se bachao)
- Har video naya ho — ek jaisa dohraaya content YouTube ki "repetitive/inauthentic content" policy mein phans sakta hai.
- AI awaaz/visuals use ho to upload mein "altered or synthetic content" disclosure sahi bharo.
- Sirf licence-wala music/SFX; credits description mein.
- Bachchon ke liye content ho to "Made for Kids" sahi set karo.
- Kisi aur ka video, kirdaar ya awaaz nahi.
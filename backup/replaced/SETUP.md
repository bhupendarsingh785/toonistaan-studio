# Toonistaan Studio — setup (Cloud Shell / server)

## Sabse aasan: Google Cloud Shell

1. Kholo: https://shell.cloud.google.com
2. Ye poora block paste karo:

```
git clone --depth 1 https://github.com/bhupendarsingh785/toonistaan-studio.git ~/ts
cd ~/ts
sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg python3-pip fonts-noto-devanagari
pip install -q requests edge-tts pillow numpy opencv-python-headless
mkdir -p studio/models
curl -sL -o studio/models/face_yunet.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
echo TAIYAR
```

3. Check:

```
cd ~/ts
python3 studio/story_video.py --help
python3 studio/gen_assets.py --help
```

## Blender (3D kirdaar) — optional

```
sudo mkdir -p /opt/blender && cd /tmp
curl -sL -o b.tar.xz https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz
sudo tar -xJf b.tar.xz -C /opt/blender --strip-components=1
/opt/blender/blender -b --python-expr 'print("BLENDER_OK")'
```

## Dhyan ki baatein

- Cloud Shell **20-60 min** me band ho jata hai — chhoti video (1-2 min) aaram se, lambi nahi
- **Lambi video (10+ min)** ke liye GitHub Actions ya apna computer behtar
- `youtube_studio/secrets/` me YouTube ki chaabi hoti hai — **kabhi GitHub par na daalo**
- Models (26MB) repo me nahi hain — upar wale command se aate hain

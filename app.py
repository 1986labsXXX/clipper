import streamlit as st
import edge_tts
import asyncio
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip
from moviepy.video.tools.subtitles import SubtitlesClip
from groq import Groq
import os
import time
import json
import re
import PIL.Image
from PIL import ImageDraw, ImageFont
import numpy as np
import yt_dlp

# --- 🛠️ FIX BUG MOVIEPY ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# --- SETUP HALAMAN ---
st.set_page_config(page_title="AI Reddit Storyteller", page_icon="💀", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    h1 { color: #FF5252; text-align: center; font-family: 'Courier New', monospace; }
    .stTextArea textarea { background-color: #1E1E1E; color: white; }
    .stButton>button { width: 100%; font-weight: bold; border-radius: 8px; }
    .success-box { padding: 15px; background-color: #1B5E20; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("💀 AI REDDIT STORYTELLER")
st.caption("Teks Cerita -> Video Shorts Viral (Minecraft Gameplay + TTS)")

# --- KONFIGURASI ---
DEFAULT_API_KEY = "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" 

if 'data' not in st.session_state:
    st.session_state.data = {}

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Konfigurasi")
    
    # 1. API Key
    custom_key = st.text_input("🔑 API Key Groq (Opsional)", type="password")
    active_key = custom_key if custom_key else DEFAULT_API_KEY
    
    st.markdown("---")
    
    # 2. Pilih Suara
    st.subheader("🎙️ Suara Narator")
    voice_option = st.selectbox("Pilih Karakter Suara:", [
        ("en-US-ChristopherNeural", "Cowok (Deep/Thriller)"),
        ("en-US-AnaNeural", "Cewek (Lembut)"),
        ("en-US-EricNeural", "Cowok (Casual)"),
        ("en-GB-SoniaNeural", "Cewek (British Accent)")
    ])
    selected_voice = voice_option[0]

    st.markdown("---")
    
    # 3. Background Video
    st.subheader("🎮 Background Gameplay")
    bg_file = st.file_uploader("Upload Video (Minecraft/GTA)", type=["mp4"])
    
    if st.button("⬇️ Download Stok Minecraft (Gratis)"):
        with st.spinner("Mendownload Gameplay No-Copyright..."):
            try:
                # Link video Minecraft Parkour No Copyright
                stock_url = "https://www.youtube.com/watch?v=n_Dv4JMiwK8" 
                ydl_opts = {
                    'format': 'best[height<=720][ext=mp4]',
                    'outtmpl': 'background_gameplay.mp4',
                    'quiet': True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([stock_url])
                st.success("✅ Background Siap! (background_gameplay.mp4)")
                st.session_state.has_bg = True
            except Exception as e:
                st.error(f"Gagal download: {e}")

# --- FUNGSI 1: AI REWRITE (BIKIN NASKAH) ---
def rewrite_story(raw_text, api_key):
    client = Groq(api_key=api_key)
    prompt = """
    You are a professional TikTok storyteller.
    Rewrite the following Reddit story into a script for a 60-second viral video.
    
    RULES:
    1. Language: English (Engaging & Suspenseful).
    2. Hook: Start with a crazy hook line immediately.
    3. Structure: No "Intro/Outro". Just the story.
    4. Length: Approx 150-180 words (for 1 minute speech).
    5. Clean text only, no emojis, no hashtags.
    
    STORY:
    """ + raw_text[:5000]
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.7
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error AI: {str(e)}"

# --- FUNGSI 2: TTS (TEXT TO SPEECH) ---
async def generate_tts(text, voice, output_file="narration.mp3"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    return output_file

# --- FUNGSI 3: GENERATOR SUBTITLE POP-UP ---
def pil_word_generator(txt):
    video_width = 720
    canvas_height = 200 
    font_size = 75 # Gedein lagi biar jelas di HP
    stroke_width = 8
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()

    img = PIL.Image.new('RGBA', (video_width, canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    bbox = draw.textbbox((0, 0), txt, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x_pos = (video_width - text_w) / 2
    y_pos = (canvas_height - text_h) / 2
    
    # Stroke Hitam Tebal
    for adj_x in range(-stroke_width, stroke_width+1):
        for adj_y in range(-stroke_width, stroke_width+1):
             draw.text((x_pos+adj_x, y_pos+adj_y), txt, font=font, fill="black")
    
    # Teks Putih (Warna khas Reddit Stories)
    draw.text((x_pos, y_pos), txt, font=font, fill="white")
    
    return ImageClip(np.array(img))

# --- FUNGSI 4: EDITOR VIDEO OTOMATIS ---
def create_reddit_video(script_text, audio_path, bg_video_path, output_name):
    try:
        # 1. Load Audio
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # 2. Load Background & Loop if necessary
        bg_clip = VideoFileClip(bg_video_path)
        
        # Potong background random biar gak bosen (start dari detik random)
        import random
        max_start = max(0, bg_clip.duration - duration - 5)
        random_start = random.uniform(0, max_start)
        
        bg_clip = bg_clip.subclip(random_start, random_start + duration)
        
        # Resize ke 9:16 (720x1280) - Center Crop
        w, h = bg_clip.size
        target_ratio = 9/16
        new_w = h * target_ratio
        if new_w <= w:
             bg_clip = bg_clip.crop(x1=w/2 - new_w/2, width=new_w, height=h)
        bg_clip = bg_clip.resize(newsize=(720, 1280))
        
        # Set Audio
        final_video = bg_clip.set_audio(audio_clip)
        
        # 3. Generate Subtitle (Estimasi Waktu)
        words = script_text.replace('\n', ' ').split()
        time_per_word = duration / len(words)
        
        subs_data = []
        current_time = 0
        
        for word in words:
            # Bersihkan kata dari tanda baca aneh
            clean_word = re.sub(r'[^\w\s\']', '', word).upper()
            if clean_word:
                start = current_time
                end = current_time + time_per_word
                subs_data.append(((start, end), clean_word))
            current_time += time_per_word
            
        # Burn Subtitles
        subtitles = SubtitlesClip(subs_data, pil_word_generator)
        subtitles = subtitles.set_position(('center', 'center'))
        
        final_result = CompositeVideoClip([final_video, subtitles])
        
        # Render
        final_result.write_videofile(output_name, codec='libx264', audio_codec='aac', preset='ultrafast', fps=24)
        return True, None

    except Exception as e:
        return False, str(e)

# --- UI UTAMA ---
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("1. Masukkan Cerita")
    raw_story = st.text_area("Paste Cerita Reddit Disini (Bahasa Inggris/Indo):", height=300, placeholder="I found a secret door in my basement...")
    
    if st.button("✨ PROSES NASKAH (AI)"):
        if not raw_story:
            st.error("Isi ceritanya dulu Bos!")
        else:
            with st.spinner("AI sedang merangkum cerita..."):
                script = rewrite_story(raw_story, active_key)
                st.session_state.data['script'] = script
                st.success("Naskah Jadi!")

with col_right:
    st.subheader("2. Preview & Render")
    
    # Edit Naskah Manual jika perlu
    if 'script' in st.session_state.data:
        final_script = st.text_area("Naskah Final (Bisa diedit):", value=st.session_state.data['script'], height=200)
        
        # Cek Background
        bg_path = None
        if bg_file:
            with open("temp_bg.mp4", "wb") as f: f.write(bg_file.getbuffer())
            bg_path = "temp_bg.mp4"
        elif os.path.exists("background_gameplay.mp4"):
            bg_path = "background_gameplay.mp4"
        
        if st.button("🎬 RENDER VIDEO SHORTS"):
            if not bg_path:
                st.error("⚠️ Background Video belum ada! Upload atau klik tombol 'Download Stok' di sidebar.")
            else:
                out_file = f"Reddit_Story_{int(time.time())}.mp4"
                
                # 1. Generate Audio
                with st.spinner("🎙️ Membuat Suara Narator..."):
                    asyncio.run(generate_tts(final_script, selected_voice))
                
                # 2. Render Video
                with st.spinner("🔥 Menggabungkan Video & Subtitle..."):
                    success, err = create_reddit_video(final_script, "narration.mp3", bg_path, out_file)
                
                if success:
                    st.success("✅ VIDEO JADI BOS!")
                    st.video(out_file)
                    with open(out_file, "rb") as f:
                        st.download_button("⬇️ DOWNLOAD MP4", f, file_name=out_file)
                    # Cleanup
                    try: os.remove("narration.mp3"); os.remove(out_file)
                    except: pass
                else:
                    st.error(f"Gagal Render: {err}")

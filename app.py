import streamlit as st
# --- OBAT KUAT ANTIALIAS ---
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ---------------------------

import pandas as pd
from moviepy.editor import *
import edge_tts 
import asyncio 
import tempfile
import os
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap
from io import StringIO

st.set_page_config(page_title="Survival Shorts Maker", layout="wide")
st.title("💀 Survival Shorts Maker (Fix 0-Byte Download)")

# --- PASTIKAN FOLDER OUTPUT ADA ---
OUTPUT_DIR = "outputs"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Konfigurasi Suara")
    voice_option = st.selectbox(
        "Pilih Karakter Suara:",
        ["Christopher (Cowok Deep/Thriller)", "Eric (Cowok Intense/Tegas)", "Ana (Cewek/Anak Kecil Creepy)"],
        index=0
    )
    voice_map = {
        "Christopher (Cowok Deep/Thriller)": "en-US-ChristopherNeural",
        "Eric (Cowok Intense/Tegas)": "en-US-EricNeural",
        "Ana (Cewek/Anak Kecil Creepy)": "en-US-AnaNeural"
    }
    selected_voice = voice_map[voice_option]
    
    st.write("---")
    st.header("2. Upload Bahan")
    bg_video_file = st.file_uploader("Upload Background Video (.mp4)", type=["mp4"])
    font_file = st.file_uploader("Upload Font (.ttf)", type=["ttf"])
    music_file = st.file_uploader("Upload Musik Horror (.mp3)", type=["mp3"])
    sfx_file = st.file_uploader("Upload SFX Jumpscare (.mp3)", type=["mp3"])

def clean_filename(text):
    clean = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', clean)

st.header("3. Data Kuis")
quiz_data_text = st.text_area("Paste CSV lo di sini", height=150)

df = pd.DataFrame() 
if quiz_data_text:
    try:
        df = pd.read_csv(StringIO(quiz_data_text))
        df.columns = [c.strip() for c in df.columns]
    except: pass

if not df.empty:
    nomor_soal = st.number_input(f"Pilih Soal (1 - {len(df)})", 1, len(df), 1)
    selected_row = df.iloc[nomor_soal-1]
    base_name = clean_filename(str(selected_row['Pertanyaan']))
    final_filename = f"{base_name}.mp4"

# --- CORE FUNCTIONS ---
async def get_edge_voice(text, filename, voice_id):
    communicate = edge_tts.Communicate(text, voice_id, rate="-10%", volume="+20%")
    await communicate.save(filename)

def create_text_clip_pil(text, font_path, fontsize, video_w, duration, is_answer=False):
    W, H = int(video_w), int(video_w * 0.8)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try: font = ImageFont.truetype(font_path, fontsize)
    except: font = ImageFont.load_default()
    wrapped_text = textwrap.fill(text, width=int((video_w*0.85)/(fontsize*0.5)))
    l, t, r, b = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_x, text_y = (W-(r-l))/2, (H-(b-t))/2
    box_color = (139, 0, 0, 200) if is_answer else (0, 0, 0, 180)
    draw.rectangle([text_x-25, text_y-25, text_x+(r-l)+25, text_y+(b-t)+25], fill=box_color)
    draw.multiline_text((text_x+4, text_y+4), wrapped_text, font=font, fill='black', align='center')
    draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill='white', align='center')
    return ImageClip(np.array(img.crop((0, int(text_y-35), W, int(text_y+(b-t)+35))))).set_duration(duration)

# --- GENERATE BUTTON & DOWNLOAD AT TOP ---
st.write("---")
download_placeholder = st.empty()

if st.button("💀 Generate Video", use_container_width=True):
    if not bg_video_file or not font_file or df.empty:
        st.error("Bahan belum lengkap!")
    else:
        with st.spinner(f"Rendering: {final_filename}..."):
            # Simpan input ke file sementara
            t_bg = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            t_bg.write(bg_video_file.read())
            t_bg.close()

            f_path = tempfile.NamedTemporaryFile(delete=False, suffix='.ttf')
            f_path.write(font_file.read())
            f_path.close()

            # Proses Video
            dq, da = 10, 4
            total = dq + da
            bg_clip = VideoFileClip(t_bg.name)
            video = bg_clip.subclip(0, total).resize(height=1920).crop(x_center=bg_clip.w/2, width=1080, height=1920)
            
            # Voice
            tts_f = os.path.join(OUTPUT_DIR, "temp_voice.mp3")
            asyncio.run(get_edge_voice(str(selected_row['Pertanyaan']), tts_f, selected_voice))
            audio_clips = [AudioFileClip(tts_f)]
            
            if music_file:
                t_m = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                t_m.write(music_file.read())
                t_m.close()
                audio_clips.append(AudioFileClip(t_m.name).subclip(0, total).volumex(0.4))
            
            if sfx_file:
                t_s = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                t_s.write(sfx_file.read())
                t_s.close()
                audio_clips.append(AudioFileClip(t_s.name).set_start(dq))
            
            video = video.set_audio(CompositeAudioClip(audio_clips).set_duration(total))
            
            # Overlay
            q = create_text_clip_pil(selected_row['Pertanyaan'], f_path.name, 75, 1080, total).set_position(('center', 350))
            a = create_text_clip_pil(f"A. {selected_row['Pilihan A']}", f_path.name, 65, 1080, total).set_position(('center', 850))
            b = create_text_clip_pil(f"B. {selected_row['Pilihan B']}", f_path.name, 65, 1080, total).set_position(('center', 1100))
            ans = create_text_clip_pil(f"Answer: {selected_row['Jawaban Benar']}", f_path.name, 85, 1080, da, True).set_start(dq).set_position(('center', 1350))
            
            final_video = CompositeVideoClip([video, q, a, b, ans])
            
            # PATH TETAP (Bukan Temp agar tidak terhapus)
            render_out = os.path.join(OUTPUT_DIR, final_filename)
            final_video.write_videofile(render_out, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast')
            
            # BACA ULANG FILE UNTUK DOWNLOAD
            with open(render_out, "rb") as f:
                video_bytes = f.read() # Baca ke memory
                download_placeholder.download_button(
                    label=f"📥 DOWNLOAD: {final_filename}",
                    data=video_bytes,
                    file_name=final_filename,
                    mime="video/mp4",
                    use_container_width=True,
                    type="primary"
                )
            
            st.success(f"✅ Selesai Render Soal {nomor_soal}!")
            st.video(render_out)

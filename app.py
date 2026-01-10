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
st.title("💀 Survival Shorts Maker (UX Optimized)")
st.markdown("Fitur: **Tombol Download di Atas** + Auto-Naming File.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Konfigurasi Suara")
    voice_option = st.selectbox(
        "Pilih Karakter Suara:",
        [
            "Christopher (Cowok Deep/Thriller)", 
            "Eric (Cowok Intense/Tegas)", 
            "Ana (Cewek/Anak Kecil Creepy)"
        ],
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
    font_file = st.file_uploader("Upload Font (.ttf) - WAJIB TEBAL", type=["ttf"])
    music_file = st.file_uploader("Upload Musik Horror (.mp3)", type=["mp3"])
    sfx_file = st.file_uploader("Upload SFX Jumpscare (.mp3)", type=["mp3"])

# --- FUNGSI MEMBERSIHKAN NAMA FILE ---
def clean_filename(text):
    clean = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', clean)

st.header("3. Data Kuis (Survival/Horror)")
example_csv = """Pertanyaan,Pilihan A,Pilihan B,Jawaban Benar
You wake up in a coffin.,Scream for help,Stay calm & conserve oxygen,Stay calm & conserve oxygen
A rabid dog chases you!,Run away,Stand ground & yell,Stand ground & yell"""
quiz_data_text = st.text_area("Paste SEMUA CSV lo di sini", value=example_csv, height=150)

# --- PILIH SOAL ---
df = pd.DataFrame() 
try:
    df = pd.read_csv(StringIO(quiz_data_text))
    df.columns = [c.strip() for c in df.columns]
except: pass

total_soal = len(df) if not df.empty else 1
st.write("---")
col1, col2 = st.columns([1, 3])
with col1:
    nomor_soal = st.number_input(f"Pilih Soal (1 - {total_soal})", min_value=1, max_value=total_soal, value=1)
with col2:
    if not df.empty and nomor_soal <= len(df):
        selected_row = df.iloc[nomor_soal-1]
        st.info(f"📝 Preview Soal: **{selected_row['Pertanyaan']}**")
        base_name = clean_filename(str(selected_row['Pertanyaan']))
        final_filename = f"{base_name}.mp4"

# --- FUNGSI SUARA ---
async def get_edge_voice(text, filename, voice_id):
    communicate = edge_tts.Communicate(text, voice_id, rate="-10%", volume="+20%")
    await communicate.save(filename)

# --- FUNGSI VISUAL ---
def create_text_clip_pil(text, font_path, fontsize, video_w, duration, is_answer=False):
    W, H = int(video_w), int(video_w * 0.8) 
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try: font = ImageFont.truetype(font_path, fontsize)
    except: font = ImageFont.load_default()
    
    wrapped_text = textwrap.fill(text, width=int((video_w*0.85)/(fontsize*0.5)))
    l, t, r, b = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    tx, ty = (W-(r-l))/2, (H-(b-t))/2
    
    box_color = (139, 0, 0, 200) if is_answer else (0, 0, 0, 180)
    draw.rectangle([tx-25, ty-25, tx+(r-l)+25, ty+(b-t)+25], fill=box_color)
    draw.multiline_text((tx+4, ty+4), wrapped_text, font=font, fill='black', align='center')
    draw.multiline_text((tx, ty), wrapped_text, font=font, fill='white', align='center')
    
    return ImageClip(np.array(img.crop((0, int(ty-10), W, int(ty+(b-t)+10))))).set_duration(duration)

# --- LOGIC UTAMA ---
def generate_video(row, bg_clip, font_path, music_path, sfx_path, voice_id, status_placeholder):
    dq, da = 9, 3
    total = dq + da
    video = (bg_clip.subclip(0, total) if bg_clip.duration > total else bg_clip.loop(duration=total))
    video = video.resize(height=1920).crop(x_center=video.w/2, width=1080, height=1920)
    
    # Audio
    tts_f = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    asyncio.run(get_edge_voice(str(row['Pertanyaan']), tts_f, voice_id))
    audio_clips = [AudioFileClip(tts_f)]
    if music_path: audio_clips.append(AudioFileClip(music_path).subclip(0, total).volumex(0.4))
    if sfx_path: audio_clips.append(AudioFileClip(sfx_path).set_start(dq))
    video = video.set_audio(CompositeAudioClip(audio_clips).set_duration(total))

    # Overlays
    q = create_text_clip_pil(row['Pertanyaan'], font_path, 75, 1080, total).set_position(('center', 350))
    a = create_text_clip_pil(f"A. {row['Pilihan A']}", font_path, 65, 1080, total).set_position(('center', 900))
    b = create_text_clip_pil(f"B. {row['Pilihan B']}", font_path, 65, 1080, total).set_position(('center', 1150))
    ans = create_text_clip_pil(f"Answer: {row['Jawaban Benar']}", font_path, 85, 1080, da, True).set_start(dq).set_position(('center', 1450))

    return CompositeVideoClip([video, q, a, b, ans])

# --- EKSEKUSI ---
st.write("---")
# PLACEHOLDER UNTUK TOMBOL DOWNLOAD (BIAR DI ATAS VIDEO)
download_placeholder = st.empty()

if st.button("💀 Generate Video", use_container_width=True):
    if not bg_video_file or not font_file:
        st.error("Bahan belum lengkap!")
    else:
        try:
            with st.spinner("Merakit video horor..."):
                t_bg = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                t_bg.write(bg_video_file.read())
                t_font = tempfile.NamedTemporaryFile(delete=False, suffix='.ttf')
                t_font.write(font_file.read())
                
                m_path = None
                if music_file:
                    t_m = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    t_m.write(music_file.read())
                    m_path = t_m.name
                
                s_path = None
                if sfx_file:
                    t_s = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    t_s.write(sfx_file.read())
                    s_path = t_s.name
                
                clip = generate_video(selected_row, VideoFileClip(t_bg.name), t_font.name, m_path, s_path, selected_voice, st.empty())
                
                out_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
                clip.write_videofile(out_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast')
                
                st.success("✅ Berhasil Render!")
                
                # TOMBOL DOWNLOAD MUNCUL DI ATAS
                with open(out_path, "rb") as f:
                    download_placeholder.download_button(
                        label=f"📥 DOWNLOAD: {final_filename}",
                        data=f,
                        file_name=final_filename,
                        mime="video/mp4",
                        type="primary",
                        use_container_width=True
                    )
                
                # Preview Video di bawah
                st.video(out_path)
                
        except Exception as e:
            st.error(f"Error: {e}")

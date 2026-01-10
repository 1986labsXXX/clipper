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
from io import StringIO, BytesIO

st.set_page_config(page_title="Survival Shorts Maker", layout="wide")
st.title("💀 Survival Shorts Maker (Fix Korup & 0B)")

# --- FUNGSI MEMBERSIHKAN NAMA FILE ---
def clean_filename(text):
    clean = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', clean)

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
    
    st.header("2. Upload Bahan")
    bg_video_file = st.file_uploader("Upload BG Video (.mp4)", type=["mp4"])
    font_file = st.file_uploader("Upload Font (.ttf)", type=["ttf"])
    music_file = st.file_uploader("Upload Musik (.mp3)", type=["mp3"])
    sfx_file = st.file_uploader("Upload SFX (.mp3)", type=["mp3"])

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
    final_filename = f"{clean_filename(str(selected_row['Pertanyaan']))}.mp4"

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
    tx, ty = (W-(r-l))/2, (H-(b-t))/2
    box_color = (139, 0, 0, 200) if is_answer else (0, 0, 0, 180)
    draw.rectangle([tx-25, ty-25, tx+(r-l)+25, ty+(b-t)+25], fill=box_color)
    draw.multiline_text((tx+4, ty+4), wrapped_text, font=font, fill='black', align='center')
    draw.multiline_text((tx, ty), wrapped_text, font=font, fill='white', align='center')
    return ImageClip(np.array(img.crop((0, int(ty-35), W, int(ty+(b-t)+35))))).set_duration(duration)

# --- GENERATE ---
st.write("---")
download_placeholder = st.empty()

if st.button("💀 Generate Video", use_container_width=True):
    if not bg_video_file or not font_file or df.empty:
        st.error("Bahan belum lengkap!")
    else:
        with st.spinner("Sedang merakit video... (Jangan pindah tab)"):
            dq, da = 10, 4
            total_dur = dq + da
            
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Save Inputs
                t_bg = os.path.join(tmpdirname, "bg.mp4")
                with open(t_bg, "wb") as f: f.write(bg_video_file.getbuffer())
                
                f_path = os.path.join(tmpdirname, "font.ttf")
                with open(f_path, "wb") as f: f.write(font_file.getbuffer())

                # Video & Audio Logic
                bg_clip = VideoFileClip(t_bg)
                video = (bg_clip.loop(duration=total_dur) if bg_clip.duration < total_dur else bg_clip.subclip(0, total_dur))
                video = video.resize(height=1920).crop(x_center=video.w/2, width=1080, height=1920)
                
                audio_clips = []
                tts_f = os.path.join(tmpdirname, "voice.mp3")
                asyncio.run(get_edge_voice(str(selected_row['Pertanyaan']), tts_f, selected_voice))
                audio_clips.append(AudioFileClip(tts_f))
                
                if music_file:
                    m_f = os.path.join(tmpdirname, "music.mp3")
                    with open(m_f, "wb") as f: f.write(music_file.getbuffer())
                    audio_clips.append(afx.audio_loop(AudioFileClip(m_f), duration=total_dur).volumex(0.3))
                
                if sfx_file:
                    s_f = os.path.join(tmpdirname, "sfx.mp3")
                    with open(s_f, "wb") as f: f.write(sfx_file.getbuffer())
                    audio_clips.append(AudioFileClip(s_f).set_start(dq))
                
                video = video.set_audio(CompositeAudioClip(audio_clips).set_duration(total_dur))
                
                # Overlays
                q = create_text_clip_pil(selected_row['Pertanyaan'], f_path, 75, 1080, total_dur).set_position(('center', 350))
                a = create_text_clip_pil(f"A. {selected_row['Pilihan A']}", f_path, 65, 1080, total_dur).set_position(('center', 850))
                b = create_text_clip_pil(f"B. {selected_row['Pilihan B']}", f_path, 65, 1080, total_dur).set_position(('center', 1100))
                ans = create_text_clip_pil(f"Answer: {selected_row['Jawaban Benar']}", f_path, 85, 1080, da, True).set_start(dq).set_position(('center', 1350))
                
                final_v = CompositeVideoClip([video, q, a, b, ans])
                
                # Render (Fixing Codec & FPS)
                render_path = os.path.join(tmpdirname, "final.mp4")
                final_v.write_videofile(render_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', logger=None, ffmpeg_params=["-pix_fmt", "yuv420p"])
                
                # BACA FILE KE MEMORY UNTUK TOMBOL DOWNLOAD
                with open(render_path, "rb") as f:
                    file_data = f.read()
                    
                download_placeholder.download_button(
                    label=f"📥 DOWNLOAD SEKARANG: {final_filename}",
                    data=file_data,
                    file_name=final_filename,
                    mime="video/mp4",
                    use_container_width=True,
                    type="primary"
                )
                
                st.success("✅ Berhasil! Silakan klik tombol download di atas.")
                st.video(file_data) # Preview pake data memory biar stabil

                # Cleanup
                bg_clip.close()
                final_v.close()

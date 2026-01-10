import streamlit as st
# --- OBAT KUAT ANTIALIAS ---
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ---------------------------

import pandas as pd
from moviepy.editor import *
from gtts import gTTS
import tempfile
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap

st.set_page_config(page_title="Tiktok Quiz Generator (Visual Fix)", layout="wide")
st.title("⚡ TikTok Quiz Generator (Edisi Ganteng Maksimal)")
st.markdown("Perbaikan: Teks pasti putih terang & Font lebih jelas.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Bahan")
    bg_video_file = st.file_uploader("Upload Background Video (.mp4)", type=["mp4"])
    font_file = st.file_uploader("Upload Font (.ttf) - PAKE YANG TEBAL!", type=["ttf"])
    music_file = st.file_uploader("Upload Musik (.mp3)", type=["mp3"])

st.header("2. Data Kuis")
example_csv = """Pertanyaan,Pilihan A,Pilihan B,Jawaban Benar
Apa warna pisang?,Kuning,Biru,Kuning
Ibukota Indonesia?,Jakarta,Bandung,Jakarta"""
quiz_data_text = st.text_area("Masukkan Data Kuis", value=example_csv, height=150)

# --- FUNGSI VISUAL (YANG DIPERBAIKI) ---
def create_text_clip_pil(text, font_path, fontsize, video_w, duration, is_answer=False):
    W = int(video_w)
    H = int(video_w * 0.8) 
    
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Cek Font
    font_loaded = False
    try:
        font = ImageFont.truetype(font_path, fontsize)
        font_loaded = True
    except:
        font = ImageFont.load_default()
    
    # Kalo font gagal, kasih tau user!
    if not font_loaded:
        st.warning(f"⚠️ Font jelek? Itu karena file .ttf lo gagal dibaca. Pake font default.")

    avg_char_width = fontsize * 0.5 
    if not font_loaded: avg_char_width = fontsize * 0.3 # Font default lebih kurus
    max_chars = int((video_w * 0.85) / avg_char_width) 
    wrapped_text = textwrap.fill(text, width=max_chars)

    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_width = right - left
    text_height = bottom - top
    
    center_x = W / 2
    center_y = H / 2
    
    text_x = center_x - (text_width / 2)
    text_y = center_y - (text_height / 2)

    # --- PERBAIKAN VISUAL DI SINI ---
    padding = 25 # Padding lebih lega
    box_left = text_x - padding
    box_top = text_y - padding
    box_right = text_x + text_width + padding
    box_bottom = text_y + text_height + padding
    
    # Warna Box: Lebih transparan biar gak terlalu gelap
    if is_answer:
        box_color = (0, 150, 0, 200) # Hijau lebih terang dikit
    else:
        box_color = (0, 0, 0, 130) # Hitam lebih bening (tadinya 160)
        
    draw.rectangle([box_left, box_top, box_right, box_bottom], fill=box_color, outline=None)

    # Text Shadow & Main (WARNA DIPAKSA PUTIH SEMUA)
    shadow_offset = 4 # Shadow lebih tebal dikit
    # Shadow Hitam Pekat
    draw.multiline_text((text_x + shadow_offset, text_y + shadow_offset), wrapped_text, font=font, fill='black', align='center')
    # Teks Utama PUTIH MUTLAK
    draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill='white', align='center')
    
    final_img = img.crop((0, int(box_top)-10, W, int(box_bottom)+10))
    
    numpy_img = np.array(final_img)
    clip = ImageClip(numpy_img).set_duration(duration)
    return clip

# --- LOGIC UTAMA ---
def generate_video(row, bg_clip, font_path, music_path):
    duration_q = 5
    duration_ans = 2
    total_duration = duration_q + duration_ans
    
    import random
    if bg_clip.duration > total_duration:
        start_t = random.uniform(0, bg_clip.duration - total_duration)
        video = bg_clip.subclip(start_t, start_t + total_duration)
    else:
        video = bg_clip.subclip(0, total_duration)
        
    target_ratio = 9/16
    current_ratio = video.w / video.h
    if current_ratio > target_ratio:
        new_width = int(video.h * target_ratio)
        if new_width % 2 != 0: new_width -= 1
        video = video.crop(x1=video.w/2 - new_width/2, width=new_width, height=video.h)
    video = video.resize(newsize=(1080, 1920)) 
    
    tts = gTTS(text=row['Pertanyaan'], lang='id')
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts.save(fp.name)
        audio_clip = AudioFileClip(fp.name)
    
    if music_path:
        bg_music = AudioFileClip(music_path).subclip(0, total_duration).volumex(0.1)
        final_audio = CompositeAudioClip([audio_clip, bg_music])
    else:
        final_audio = audio_clip
    video = video.set_audio(final_audio)

    # --- LAYOUT & WARNA BARU ---
    # Semua teks dipaksa jadi PUTIH ('white') di fungsi create_text_clip_pil
    # Posisi digeser dikit biar lebih lega
    clip_q = create_text_clip_pil(row['Pertanyaan'], font_path, 75, 1080, total_duration)
    clip_q = clip_q.set_position(('center', 350))
    
    clip_a = create_text_clip_pil(f"A. {row['Pilihan A']}", font_path, 65, 1080, total_duration)
    clip_a = clip_a.set_position(('center', 950)) # Turun dikit
    
    clip_b = create_text_clip_pil(f"B. {row['Pilihan B']}", font_path, 65, 1080, total_duration)
    clip_b = clip_b.set_position(('center', 1250)) # Turun & jarakin
    
    clip_c = create_text_clip_pil(f"Jawab: {row['Jawaban Benar']}", font_path, 85, 1080, duration_ans, is_answer=True)
    clip_c = clip_c.set_start(duration_q).set_position(('center', 1600))

    final = CompositeVideoClip([video, clip_q, clip_a, clip_b, clip_c])
    return final

# --- EKSEKUSI ---
if st.button("🚀 Generate Video (Visual Fix)"):
    if not bg_video_file or not font_file:
        st.error("Upload Background Video & Font dulu Bos!")
    else:
        # ... (SAMA KAYAK SEBELUMNYA)
        try:
            with st.spinner('Sedang merakit video...'):
                tfile_bg = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                tfile_bg.write(bg_video_file.read())
                tfile_font = tempfile.NamedTemporaryFile(delete=False, suffix='.ttf')
                tfile_font.write(font_file.read())
                music_path = None
                if music_file:
                    tfile_music = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    tfile_music.write(music_file.read())
                    music_path = tfile_music.name
                
                bg_clip = VideoFileClip(tfile_bg.name)
                from io import StringIO
                df = pd.read_csv(StringIO(quiz_data_text))
                first_row = df.iloc[0] 
                
                result_clip = generate_video(first_row, bg_clip, tfile_font.name, music_path)
                
                output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
                result_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', threads=4, ffmpeg_params=['-pix_fmt', 'yuv420p'])
                
                st.success("✅ Video Jadi! Harusnya udah ganteng sekarang.")
                st.video(output_path)
                with open(output_path, "rb") as file:
                    st.download_button("Download Video MP4", file, "quiz_visual_fix.mp4", mime="video/mp4")     
        except Exception as e:
            st.error(f"Error: {e}")

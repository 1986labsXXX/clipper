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

st.set_page_config(page_title="Tiktok Quiz Generator (Final Fix Genap)", layout="wide")
st.title("⚡ TikTok Quiz Generator (Anti-Ganjil)")
st.markdown("Mesin sudah dikalibrasi: Resolusi pasti Genap (1080x1920).")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Bahan")
    bg_video_file = st.file_uploader("Upload Background Video (.mp4)", type=["mp4"])
    font_file = st.file_uploader("Upload Font (.ttf)", type=["ttf"])
    music_file = st.file_uploader("Upload Musik (.mp3)", type=["mp3"])

st.header("2. Data Kuis")
example_csv = """Pertanyaan,Pilihan A,Pilihan B,Jawaban Benar
Apa warna pisang?,Kuning,Biru,Kuning
Ibukota Indonesia?,Jakarta,Bandung,Jakarta"""
quiz_data_text = st.text_area("Masukkan Data Kuis", value=example_csv, height=150)

# --- FUNGSI VISUAL (PILLOW) ---
def create_text_clip_pil(text, font_path, fontsize, color, video_w, duration, is_answer=False):
    W = int(video_w)
    H = int(video_w * 0.8) 
    
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype(font_path, fontsize)
    except:
        font = ImageFont.load_default()

    avg_char_width = fontsize * 0.5 
    max_chars = int((video_w * 0.8) / avg_char_width) 
    wrapped_text = textwrap.fill(text, width=max_chars)

    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_width = right - left
    text_height = bottom - top
    
    center_x = W / 2
    center_y = H / 2
    
    text_x = center_x - (text_width / 2)
    text_y = center_y - (text_height / 2)

    # Box Background
    padding = 20
    box_left = text_x - padding
    box_top = text_y - padding
    box_right = text_x + text_width + padding
    box_bottom = text_y + text_height + padding
    
    if is_answer:
        box_color = (0, 100, 0, 180) # Hijau
    else:
        box_color = (0, 0, 0, 160) # Hitam
        
    draw.rectangle([box_left, box_top, box_right, box_bottom], fill=box_color, outline=None)

    # Text Shadow & Main
    shadow_offset = 3
    draw.multiline_text((text_x + shadow_offset, text_y + shadow_offset), wrapped_text, font=font, fill='black', align='center')
    draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill=color, align='center')
    
    final_img = img.crop((0, int(box_top)-10, W, int(box_bottom)+10))
    
    numpy_img = np.array(final_img)
    clip = ImageClip(numpy_img).set_duration(duration)
    return clip

# --- LOGIC UTAMA (DENGAN FIX RESIZE) ---
def generate_video(row, bg_clip, font_path, music_path):
    duration_q = 5
    duration_ans = 2
    total_duration = duration_q + duration_ans
    
    # 1. Potong Durasi
    import random
    if bg_clip.duration > total_duration:
        start_t = random.uniform(0, bg_clip.duration - total_duration)
        video = bg_clip.subclip(start_t, start_t + total_duration)
    else:
        video = bg_clip.subclip(0, total_duration)
        
    # 2. RESIZE & CROP (INI YANG DIPERBAIKI)
    # Target: 9:16
    target_ratio = 9/16
    current_ratio = video.w / video.h
    
    if current_ratio > target_ratio:
        # Video terlalu lebar, kita crop sampingnya
        new_width = int(video.h * target_ratio)
        # FORCE GENAP: Pastikan lebar habis dibagi 2
        if new_width % 2 != 0:
            new_width -= 1
            
        video = video.crop(x1=video.w/2 - new_width/2, width=new_width, height=video.h)
    
    # Resize ke HD 1080x1920
    # Kita paksa ukurannya fix biar gak ada koma-komaan lagi
    video = video.resize(newsize=(1080, 1920)) 
    
    # 3. Audio
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

    # 4. Layer Teks
    # Adjust ukuran font biar proporsional sama 1080px
    clip_q = create_text_clip_pil(row['Pertanyaan'], font_path, 70, 'white', 1080, total_duration)
    clip_q = clip_q.set_position(('center', 400))
    
    clip_a = create_text_clip_pil(f"A. {row['Pilihan A']}", font_path, 60, '#f0f0f0', 1080, total_duration)
    clip_a = clip_a.set_position(('center', 900))
    
    clip_b = create_text_clip_pil(f"B. {row['Pilihan B']}", font_path, 60, '#f0f0f0', 1080, total_duration)
    clip_b = clip_b.set_position(('center', 1150))
    
    clip_c = create_text_clip_pil(f"Jawab: {row['Jawaban Benar']}", font_path, 80, 'white', 1080, duration_ans, is_answer=True)
    clip_c = clip_c.set_start(duration_q).set_position(('center', 1500))

    final = CompositeVideoClip([video, clip_q, clip_a, clip_b, clip_c])
    return final

# --- EKSEKUSI ---
if st.button("🚀 Generate Video (Fix Genap)"):
    if not bg_video_file or not font_file:
        st.error("Upload Background Video & Font dulu Bos!")
    else:
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
                
                # Render
                result_clip.write_videofile(
                    output_path, 
                    codec='libx264', 
                    audio_codec='aac', 
                    fps=24, 
                    preset='ultrafast', 
                    threads=4,
                    ffmpeg_params=['-pix_fmt', 'yuv420p']
                )
                
                st.success("✅ Video Jadi! 100% Works!")
                st.video(output_path)
                
                with open(output_path, "rb") as file:
                    st.download_button("Download Video MP4", file, "quiz_final_fixed.mp4", mime="video/mp4")
                    
        except Exception as e:
            st.error(f"Error: {e}")

import streamlit as st
# --- OBAT KUAT ANTIALIAS (WAJIB DITARUH PALING ATAS) ---
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# -------------------------------------------------------

import pandas as pd
from moviepy.editor import *
from gtts import gTTS
import tempfile
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap

st.set_page_config(page_title="Tiktok Quiz Generator (Final Fix)", layout="wide")

st.title("⚡ TikTok Quiz Generator (Final Version)")
st.markdown("Mesin sudah di-patch. Siap gaspol.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Bahan")
    bg_video_file = st.file_uploader("Upload Background Video (.mp4)", type=["mp4"])
    font_file = st.file_uploader("Upload Font (.ttf)", type=["ttf"])
    music_file = st.file_uploader("Upload Musik (.mp3)", type=["mp3"])

# --- INPUT DATA ---
st.header("2. Data Kuis")
example_csv = """Pertanyaan,Pilihan A,Pilihan B,Jawaban Benar
Apa warna pisang?,Kuning,Biru,Kuning
Ibukota Indonesia?,Jakarta,Bandung,Jakarta"""
quiz_data_text = st.text_area("Masukkan Data Kuis", value=example_csv, height=150)

# --- FUNGSI PIL TEXT (ANTI ERROR IMAGEMAGICK) ---
def create_text_clip_pil(text, font_path, fontsize, color, stroke_width, video_w, duration):
    W, H = int(video_w), int(video_w)
    img = Image.new('RGBA', (W, H), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype(font_path, fontsize)
    except:
        font = ImageFont.load_default()
    
    avg_char_width = fontsize * 0.5 
    max_chars = int((video_w * 0.9) / avg_char_width)
    wrapped_text = textwrap.fill(text, width=max_chars)

    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_width = right - left
    text_height = bottom - top
    
    x = (W - text_width) / 2
    y = (H - text_height) / 2
    
    draw.multiline_text((x, y), wrapped_text, font=font, fill=color, 
                        stroke_width=stroke_width, stroke_fill='black', align='center')
    
    final_img = img.crop((0, int(y)-10, W, int(y+text_height)+20))
    
    numpy_img = np.array(final_img)
    clip = ImageClip(numpy_img).set_duration(duration)
    return clip

# --- LOGIC UTAMA ---
def generate_video(row, bg_clip, font_path, music_path):
    duration_q = 5
    duration_ans = 2
    total_duration = duration_q + duration_ans
    
    # 1. Background
    import random
    if bg_clip.duration > total_duration:
        start_t = random.uniform(0, bg_clip.duration - total_duration)
        video = bg_clip.subclip(start_t, start_t + total_duration)
    else:
        video = bg_clip.subclip(0, total_duration)
        
    # Resize (DISINI YANG TADINYA ERROR, SKRG UDAH DI-PATCH)
    target_ratio = 9/16
    current_ratio = video.w / video.h
    if current_ratio > target_ratio:
        new_width = int(video.h * target_ratio)
        video = video.crop(x1=video.w/2 - new_width/2, width=new_width, height=video.h)
    video = video.resize(height=1920)
    
    # 2. Audio TTS
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

    # 3. Layer Teks
    clip_q = create_text_clip_pil(row['Pertanyaan'], font_path, 70, 'white', 4, video.w, total_duration)
    clip_q = clip_q.set_position(('center', 400))
    
    clip_a = create_text_clip_pil(f"A. {row['Pilihan A']}", font_path, 60, 'white', 3, video.w, total_duration)
    clip_a = clip_a.set_position(('center', 900))
    
    clip_b = create_text_clip_pil(f"B. {row['Pilihan B']}", font_path, 60, 'white', 3, video.w, total_duration)
    clip_b = clip_b.set_position(('center', 1100))
    
    clip_c = create_text_clip_pil(f"Jawab: {row['Jawaban Benar']}", font_path, 80, '#00ff00', 4, video.w, duration_ans)
    clip_c = clip_c.set_start(duration_q).set_position(('center', 1400))

    final = CompositeVideoClip([video, clip_q, clip_a, clip_b, clip_c])
    return final

# --- EKSEKUSI ---
if st.button("🚀 Generate Video (Bismillah Final)"):
    if not bg_video_file or not font_file:
        st.error("Upload dulu Video Background sama Font-nya, Bos!")
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
                result_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', threads=4)
                
                st.success("✅ Video Jadi Bos! Gak ada error lagi!")
                st.video(output_path)
                
                with open(output_path, "rb") as file:
                    st.download_button("Download Video MP4", file, "quiz_final.mp4", mime="video/mp4")
                    
        except Exception as e:
            st.error(f"Error: {e}")

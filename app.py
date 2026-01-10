import streamlit as st
import pandas as pd
from moviepy.editor import *
from gtts import gTTS
import tempfile
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap

st.set_page_config(page_title="Tiktok Quiz Generator (PIL Version)", layout="wide")

st.title("⚡ TikTok Quiz Generator (Anti-Error Version)")
st.markdown("Mesin baru: Tanpa ImageMagick, Tanpa Sakit Kepala.")

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

# --- FUNGSI BARU: BIKIN TEKS PAKE PILLOW (BYPASS IMAGEMAGICK) ---
def create_text_clip_pil(text, font_path, fontsize, color, stroke_width, video_w, duration):
    # 1. Siapkan Kanvas Kosong Transparan
    # Kita bikin lebar kanvas agak lebar biar aman, tinggi cukup buat teks
    W, H = int(video_w), int(video_w) # Tinggi sementara persegi
    img = Image.new('RGBA', (W, H), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # 2. Load Font
    try:
        font = ImageFont.truetype(font_path, fontsize)
    except:
        font = ImageFont.load_default()
        st.warning("Font gagal load, pake default.")

    # 3. Auto-Wrap Teks (Biar gak kepotong ke samping)
    # Hitung kira2 berapa karakter muat per baris based on width
    avg_char_width = fontsize * 0.5 
    max_chars = int((video_w * 0.9) / avg_char_width)
    wrapped_text = textwrap.fill(text, width=max_chars)

    # 4. Hitung Posisi Tengah (Center)
    # Pake bbox buat dapet ukuran teks akurat
    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_width = right - left
    text_height = bottom - top
    
    # Koordinat X, Y biar pas di tengah kanvas img
    x = (W - text_width) / 2
    y = (H - text_height) / 2
    
    # 5. Gambar Teks dengan Outline (Stroke)
    draw.multiline_text((x, y), wrapped_text, font=font, fill=color, 
                        stroke_width=stroke_width, stroke_fill='black', align='center')
    
    # 6. Crop Kanvas biar pas seukuran teks aja (biar enteng)
    # Kita kasih padding dikit
    final_img = img.crop((0, int(y)-10, W, int(y+text_height)+20))
    
    # 7. Convert ke MoviePy ImageClip
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
        
    # Resize 9:16
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

    # 3. Bikin Layer Teks (PAKE FUNGSI BARU)
    # Pertanyaan (Posisi Y: 400 dari atas)
    clip_q = create_text_clip_pil(row['Pertanyaan'], font_path, 70, 'white', 4, video.w, total_duration)
    clip_q = clip_q.set_position(('center', 400))
    
    # Pilihan A (Posisi Y: 900)
    clip_a = create_text_clip_pil(f"A. {row['Pilihan A']}", font_path, 60, 'white', 3, video.w, total_duration)
    clip_a = clip_a.set_position(('center', 900))
    
    # Pilihan B (Posisi Y: 1100)
    clip_b = create_text_clip_pil(f"B. {row['Pilihan B']}", font_path, 60, 'white', 3, video.w, total_duration)
    clip_b = clip_b.set_position(('center', 1100))
    
    # Jawaban Benar (Muncul belakangan, warna Hijau)
    clip_c = create_text_clip_pil(f"Jawab: {row['Jawaban Benar']}", font_path, 80, '#00ff00', 4, video.w, duration_ans)
    clip_c = clip_c.set_start(duration_q).set_position(('center', 1400))

    # Gabung
    final = CompositeVideoClip([video, clip_q, clip_a, clip_b, clip_c])
    return final

# --- TOMBOL ---
if st.button("🚀 Generate Video (Anti-Gagal)"):
    if not bg_video_file or not font_file:
        st.error("Upload dulu Video Background sama Font-nya, Bos!")
    else:
        try:
            with st.spinner('Sedang merakit video dengan teknologi Pillow...'):
                # Save temp files
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
                first_row = df.iloc[0] # Test 1 video dulu
                
                result_clip = generate_video(first_row, bg_clip, tfile_font.name, music_path)
                
                output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
                # Pake preset ultrafast biar cepet di cloud
                result_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', threads=4)
                
                st.success("✅ Video Jadi Bos! Tanpa Error ImageMagick!")
                st.video(output_path)
                
                with open(output_path, "rb") as file:
                    st.download_button("Download Video MP4", file, "quiz_final.mp4", mime="video/mp4")
                    
        except Exception as e:
            st.error(f"Masih error juga? Keterlaluan: {e}")

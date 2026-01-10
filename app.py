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

st.set_page_config(page_title="Tiktok Quiz Generator (Pro)", layout="wide")
st.title("⚡ TikTok Quiz Generator (Versi Ganteng)")
st.markdown("Fitur Baru: Visual lebih rapi & Support Windows Player.")

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

# --- FUNGSI VISUAL BARU (LEBIH RAPI + KOTAK BACKGROUND) ---
def create_text_clip_pil(text, font_path, fontsize, color, video_w, duration, is_answer=False):
    # 1. Setup Kanvas
    W = int(video_w)
    # Estimasi tinggi (agak longgar biar aman)
    H = int(video_w * 0.8) 
    
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 2. Load Font (Cek error)
    try:
        font = ImageFont.truetype(font_path, fontsize)
    except:
        # Fallback ke default kalau font gagal
        font = ImageFont.load_default()
        st.toast("⚠️ Font gagal load, pake default ya.")

    # 3. Wrapping Text
    # Hitung karakter per baris (empiris)
    avg_char_width = fontsize * 0.5 
    max_chars = int((video_w * 0.8) / avg_char_width) 
    wrapped_text = textwrap.fill(text, width=max_chars)

    # 4. Hitung Ukuran & Posisi
    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_width = right - left
    text_height = bottom - top
    
    center_x = W / 2
    center_y = H / 2
    
    # Koordinat pojok kiri atas teks
    text_x = center_x - (text_width / 2)
    text_y = center_y - (text_height / 2)

    # 5. GAMBAR BACKGROUND BOX (BIAR JELAS)
    # Kotak hitam transparan di belakang teks
    padding = 20
    box_left = text_x - padding
    box_top = text_y - padding
    box_right = text_x + text_width + padding
    box_bottom = text_y + text_height + padding
    
    # Warna Box: Hitam transparan (Alpha 150)
    # Kalau jawaban benar, box-nya Hijau transparan
    if is_answer:
        box_color = (0, 100, 0, 180) # Hijau Gelap
    else:
        box_color = (0, 0, 0, 160) # Hitam
        
    draw.rectangle([box_left, box_top, box_right, box_bottom], fill=box_color, outline=None)

    # 6. GAMBAR TEKS
    # Shadow effect (Hitam pekat) biar stroke gak pecah
    shadow_offset = 3
    draw.multiline_text((text_x + shadow_offset, text_y + shadow_offset), wrapped_text, font=font, fill='black', align='center')
    
    # Main Text
    draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill=color, align='center')
    
    # 7. Crop Sesuai Box
    final_img = img.crop((0, int(box_top)-10, W, int(box_bottom)+10))
    
    numpy_img = np.array(final_img)
    clip = ImageClip(numpy_img).set_duration(duration)
    return clip

# --- LOGIC UTAMA ---
def generate_video(row, bg_clip, font_path, music_path):
    duration_q = 5
    duration_ans = 2
    total_duration = duration_q + duration_ans
    
    # Background Logic
    import random
    if bg_clip.duration > total_duration:
        start_t = random.uniform(0, bg_clip.duration - total_duration)
        video = bg_clip.subclip(start_t, start_t + total_duration)
    else:
        video = bg_clip.subclip(0, total_duration)
        
    # Resize Logic
    target_ratio = 9/16
    current_ratio = video.w / video.h
    if current_ratio > target_ratio:
        new_width = int(video.h * target_ratio)
        video = video.crop(x1=video.w/2 - new_width/2, width=new_width, height=video.h)
    video = video.resize(height=1920)
    
    # Audio Logic
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

    # --- SETUP VISUAL BARU ---
    # Pertanyaan (Font Gede, Posisi Atas)
    clip_q = create_text_clip_pil(row['Pertanyaan'], font_path, 80, 'white', video.w, total_duration)
    clip_q = clip_q.set_position(('center', 300)) # Agak ke atas
    
    # Pilihan A
    clip_a = create_text_clip_pil(f"A. {row['Pilihan A']}", font_path, 65, '#f0f0f0', video.w, total_duration)
    clip_a = clip_a.set_position(('center', 900))
    
    # Pilihan B
    clip_b = create_text_clip_pil(f"B. {row['Pilihan B']}", font_path, 65, '#f0f0f0', video.w, total_duration)
    clip_b = clip_b.set_position(('center', 1150)) # Jarakin dikit
    
    # Jawaban Benar (Hijau + Box Hijau)
    clip_c = create_text_clip_pil(f"Jawab: {row['Jawaban Benar']}", font_path, 90, 'white', video.w, duration_ans, is_answer=True)
    clip_c = clip_c.set_start(duration_q).set_position(('center', 1500))

    final = CompositeVideoClip([video, clip_q, clip_a, clip_b, clip_c])
    return final

# --- EKSEKUSI ---
if st.button("🚀 Generate Video (Versi Fix Player)"):
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
                
                # --- BAGIAN KRUSIAL: SETTING ENCODING WINDOWS ---
                result_clip.write_videofile(
                    output_path, 
                    codec='libx264', 
                    audio_codec='aac', 
                    fps=24, 
                    preset='ultrafast', 
                    threads=4,
                    ffmpeg_params=['-pix_fmt', 'yuv420p'] # <--- INI OBAT ERROR PLAYBACKNYA
                )
                
                st.success("✅ Video Jadi! Coba play sekarang!")
                st.video(output_path)
                
                with open(output_path, "rb") as file:
                    st.download_button("Download Video MP4", file, "quiz_fixed.mp4", mime="video/mp4")
                    
        except Exception as e:
            st.error(f"Error: {e}")

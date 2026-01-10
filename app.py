import streamlit as st
import pandas as pd
from moviepy.editor import *
from moviepy.config import change_settings
from gtts import gTTS
import tempfile
import os
import PIL.Image

# --- 1. PERBAIKAN BUG ANTIALIAS (YANG TADI) ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# --- 2. PERBAIKAN SECURITY POLICY (YANG BARU) ---
# Kita kasih tau ImageMagick: "Woi, baca aturan dari folder ini aja!"
os.environ['MAGICK_CONFIGURE_PATH'] = os.getcwd()

# --- 3. KONFIGURASI BINARY ---
if os.path.exists("/usr/bin/convert"):
    change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})

# ... (lanjut ke st.set_page_config dst)

st.set_page_config(page_title="Tiktok Quiz Generator by M", layout="wide")

st.title("⚡ TikTok Quiz Generator (Cloud Version)")
st.markdown("Upload bahan, klik generate, jadi duit.")

# --- SIDEBAR: UPLOAD BAHAN BAKU ---
with st.sidebar:
    st.header("1. Upload Bahan")
    
    # Upload Background Video
    bg_video_file = st.file_uploader("Upload Background Video (.mp4)", type=["mp4"])
    
    # Upload Font (WAJIB biar gak error di Linux)
    font_file = st.file_uploader("Upload Font (.ttf)", type=["ttf"])
    
    # Upload Musik (Opsional)
    music_file = st.file_uploader("Upload Musik (.mp3)", type=["mp3"])

# --- KOLOM UTAMA: DATA KUIS ---
st.header("2. Data Kuis")

# Template CSV
example_csv = """Pertanyaan,Pilihan A,Pilihan B,Jawaban Benar
Apa warna pisang?,Kuning,Biru,Kuning
Ibukota Indonesia?,Jakarta,Bandung,Jakarta"""

quiz_data_text = st.text_area("Masukkan Data Kuis (Format CSV: Pertanyaan, A, B, Jawaban)", value=example_csv, height=150)

# --- FUNGSI GENERATOR ---
def generate_video(row, bg_clip, font_path, music_path):
    # Setup Durasi
    duration_q = 5 # Detik pertanyaan muncul
    duration_ans = 2 # Detik jawaban muncul
    total_duration = duration_q + duration_ans
    
    # 1. Potong Background (Random Start biar unik)
    import random
    if bg_clip.duration > total_duration:
        start_t = random.uniform(0, bg_clip.duration - total_duration)
        video = bg_clip.subclip(start_t, start_t + total_duration)
    else:
        video = bg_clip.subclip(0, total_duration) # Kalau video pendek, ambil dari awal
    
    # Resize ke 9:16 (Shorts) kalau belum
    target_ratio = 9/16
    current_ratio = video.w / video.h
    
    # Simple Center Crop
    if current_ratio > target_ratio:
        new_width = int(video.h * target_ratio)
        video = video.crop(x1=video.w/2 - new_width/2, width=new_width, height=video.h)
    
    video = video.resize(height=1920) # Paksa HD
    
    # 2. Bikin Audio Pertanyaan (Text to Speech)
    tts = gTTS(text=row['Pertanyaan'], lang='id') # Ganti 'en' kalau mau Inggris
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts.save(fp.name)
        audio_clip = AudioFileClip(fp.name)
    
    # Gabung Audio TTS + Musik Background
    if music_path:
        bg_music = AudioFileClip(music_path).subclip(0, total_duration).volumex(0.1) # Volume kecil
        final_audio = CompositeAudioClip([audio_clip, bg_music])
    else:
        final_audio = audio_clip
        
    video = video.set_audio(final_audio)

    # 3. Bikin Teks (Layering)
    # Style Teks
    txt_color = 'white'
    stroke_color = 'black'
    stroke_width = 3
    fontsize = 70
    
    # Clip Pertanyaan
    txt_q = TextClip(row['Pertanyaan'], font=font_path, fontsize=fontsize, color=txt_color, 
                     stroke_color=stroke_color, stroke_width=stroke_width, method='caption', 
                     size=(video.w*0.9, None)).set_position(('center', 400)).set_duration(total_duration)
    
    # Clip Pilihan A
    txt_a = TextClip(f"A. {row['Pilihan A']}", font=font_path, fontsize=60, color='white', 
                     stroke_color='black', stroke_width=2, method='caption',
                     size=(video.w*0.8, None)).set_position(('center', 900)).set_duration(total_duration)

    # Clip Pilihan B
    txt_b = TextClip(f"B. {row['Pilihan B']}", font=font_path, fontsize=60, color='white', 
                     stroke_color='black', stroke_width=2, method='caption',
                     size=(video.w*0.8, None)).set_position(('center', 1100)).set_duration(total_duration)
    
    # Clip Jawaban (Muncul belakangan)
    txt_correct = TextClip(f"Jawab: {row['Jawaban Benar']}", font=font_path, fontsize=80, color='green', 
                           stroke_color='white', stroke_width=3, method='caption',
                           size=(video.w*0.9, None)).set_position(('center', 1400)).set_start(duration_q).set_duration(duration_ans)

    # Composite (Tumpuk semua layer)
    final = CompositeVideoClip([video, txt_q, txt_a, txt_b, txt_correct])
    return final

# --- TOMBOL EKSEKUSI ---
if st.button("🚀 Generate Video"):
    if not bg_video_file or not font_file:
        st.error("Woi Bos! Upload dulu Video Background sama Font-nya!")
    else:
        try:
            with st.spinner('Lagi masak video... sabar ya...'):
                # Simpan file upload ke temp biar bisa dibaca MoviePy
                tfile_bg = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                tfile_bg.write(bg_video_file.read())
                
                tfile_font = tempfile.NamedTemporaryFile(delete=False, suffix='.ttf')
                tfile_font.write(font_file.read())
                
                music_path = None
                if music_file:
                    tfile_music = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    tfile_music.write(music_file.read())
                    music_path = tfile_music.name
                
                # Load Video Utama
                bg_clip = VideoFileClip(tfile_bg.name)
                
                # Parse Data CSV
                from io import StringIO
                df = pd.read_csv(StringIO(quiz_data_text))
                
                # Generate Row Pertama Aja (Buat Test Drive)
                # Kalo mau loop semua, nanti kita update lagi. Skrg 1 dulu biar cepet.
                first_row = df.iloc[0]
                
                result_clip = generate_video(first_row, bg_clip, tfile_font.name, music_path)
                
                # Render ke file
                output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
                result_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', threads=4)
                
                # Tampilin
                st.success("✅ Video Jadi Bos!")
                st.video(output_path)
                
                # Tombol Download
                with open(output_path, "rb") as file:
                    st.download_button("Download Video MP4", file, "quiz_result.mp4", mime="video/mp4")
                    
        except Exception as e:
            st.error(f"Gagal Bos: {e}")

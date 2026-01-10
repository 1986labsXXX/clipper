import streamlit as st
# --- OBAT KUAT ANTIALIAS (WAJIB) ---
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# -----------------------------------

import pandas as pd
from moviepy.editor import *
from gtts import gTTS
import tempfile
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap
from io import StringIO

st.set_page_config(page_title="YouTube Shorts Factory", layout="wide")
st.title("🟥 YouTube Shorts Generator (Audio Fix)")
st.markdown("Update: Musik lebih kencang (30%) & Jawaban muncul di detik ke-6.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Konfigurasi")
    tts_lang = st.selectbox("Bahasa Suara (TTS)", ["en", "id"], index=0, help="Pilih 'en' buat target US.")
    
    st.header("2. Upload Bahan")
    bg_video_file = st.file_uploader("Upload Background Video (.mp4)", type=["mp4"])
    font_file = st.file_uploader("Upload Font (.ttf) - WAJIB TEBAL", type=["ttf"])
    music_file = st.file_uploader("Upload Musik (.mp3)", type=["mp3"])
    sfx_file = st.file_uploader("Upload SFX Jawaban 'Ting' (.mp3)", type=["mp3"])

st.header("3. Data Kuis")
example_csv = """Pertanyaan,Pilihan A,Pilihan B,Jawaban Benar
Capital of New York?,New York City,Albany,Albany
What has keys but no locks?,A Piano,A Map,A Piano"""
quiz_data_text = st.text_area("Masukkan Data Kuis (Format CSV)", value=example_csv, height=150)

# --- FUNGSI VISUAL (PILLOW) ---
def create_text_clip_pil(text, font_path, fontsize, video_w, duration, is_answer=False):
    W = int(video_w)
    H = int(video_w * 0.8) 
    
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font_loaded = False
    try:
        font = ImageFont.truetype(font_path, fontsize)
        font_loaded = True
    except:
        font = ImageFont.load_default()
    
    if not font_loaded:
        st.toast(f"⚠️ Font default dipake.")

    avg_char_width = fontsize * 0.5 
    if not font_loaded: avg_char_width = fontsize * 0.3
    max_chars = int((video_w * 0.85) / avg_char_width) 
    wrapped_text = textwrap.fill(text, width=max_chars)

    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
    text_width = right - left
    text_height = bottom - top
    
    center_x = W / 2
    center_y = H / 2
    
    text_x = center_x - (text_width / 2)
    text_y = center_y - (text_height / 2)

    padding = 25
    box_left = text_x - padding
    box_top = text_y - padding
    box_right = text_x + text_width + padding
    box_bottom = text_y + text_height + padding
    
    if is_answer:
        box_color = (0, 150, 0, 200) # Hijau
    else:
        box_color = (0, 0, 0, 130) # Hitam Transparan
        
    draw.rectangle([box_left, box_top, box_right, box_bottom], fill=box_color, outline=None)

    shadow_offset = 4
    draw.multiline_text((text_x + shadow_offset, text_y + shadow_offset), wrapped_text, font=font, fill='black', align='center')
    draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill='white', align='center')
    
    final_img = img.crop((0, int(box_top)-10, W, int(box_bottom)+10))
    
    numpy_img = np.array(final_img)
    clip = ImageClip(numpy_img).set_duration(duration)
    return clip

# --- LOGIC UTAMA (Updated Timing & Volume) ---
def generate_video(row, bg_clip, font_path, music_path, sfx_path, lang_code):
    # UPDATE TIMING DI SINI
    duration_q = 6 # Detik ke-6 baru jawaban muncul (sebelumnya 5)
    duration_ans = 2
    total_duration = duration_q + duration_ans
    
    # 1. Video Processing
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
    
    # 2. Audio Processing
    audio_clips = []
    
    # TTS
    tts = gTTS(text=str(row['Pertanyaan']), lang=lang_code)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts.save(fp.name)
        tts_clip = AudioFileClip(fp.name)
        audio_clips.append(tts_clip)
    
    # Music (UPDATE VOLUME)
    if music_path:
        # Volumex dinaikin jadi 0.3 (30%) biar kedengeran
        bg_music = AudioFileClip(music_path).subclip(0, total_duration).volumex(0.3)
        audio_clips.append(bg_music)
        
    # SFX (UPDATE TIMING)
    if sfx_path:
        # Muncul pas duration_q (detik ke-6)
        sfx = AudioFileClip(sfx_path).set_start(duration_q)
        audio_clips.append(sfx)
    
    final_audio = CompositeAudioClip(audio_clips)
    video = video.set_audio(final_audio)

    # 3. VISUAL LAYOUT (YOUTUBE SAFE ZONE)
    
    clip_q = create_text_clip_pil(str(row['Pertanyaan']), font_path, 75, 1080, total_duration)
    clip_q = clip_q.set_position(('center', 300))
    
    clip_a = create_text_clip_pil(f"A. {row['Pilihan A']}", font_path, 65, 1080, total_duration)
    clip_a = clip_a.set_position(('center', 850))
    
    clip_b = create_text_clip_pil(f"B. {row['Pilihan B']}", font_path, 65, 1080, total_duration)
    clip_b = clip_b.set_position(('center', 1100))
    
    # Jawaban muncul pas duration_q (detik ke-6)
    clip_c = create_text_clip_pil(f"Answer: {row['Jawaban Benar']}", font_path, 85, 1080, duration_ans, is_answer=True)
    clip_c = clip_c.set_start(duration_q).set_position(('center', 1350))

    final = CompositeVideoClip([video, clip_q, clip_a, clip_b, clip_c])
    return final

# --- EKSEKUSI ---
if st.button("🚀 Generate Shorts (Fix Audio & Timing)"):
    if not bg_video_file or not font_file:
        st.error("⚠️ Upload Bahan Wajib: Video & Font!")
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
                
                sfx_path = None
                if sfx_file:
                    tfile_sfx = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    tfile_sfx.write(sfx_file.read())
                    sfx_path = tfile_sfx.name
                
                try:
                    df = pd.read_csv(StringIO(quiz_data_text))
                    df.columns = [c.strip() for c in df.columns]
                except:
                    st.error("❌ Format CSV Salah.")
                    st.stop()
                
                if df.empty: st.stop()

                bg_clip = VideoFileClip(tfile_bg.name)
                first_row = df.iloc[0] 
                
                result_clip = generate_video(first_row, bg_clip, tfile_font.name, music_path, sfx_path, tts_lang)
                
                output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
                result_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', threads=4, ffmpeg_params=['-pix_fmt', 'yuv420p'])
                
                st.success("✅ Shorts Jadi! Cek suara musik & SFX-nya.")
                st.video(output_path)
                with open(output_path, "rb") as file:
                    st.download_button("Download Shorts MP4", file, "shorts_audio_fix.mp4", mime="video/mp4")
                    
        except Exception as e:
            st.error(f"Error: {e}")

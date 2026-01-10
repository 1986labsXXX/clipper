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
st.title("💀 Survival Shorts Maker (Download at Top)")
st.markdown("Fitur: **3 Suara (Boost +20%)** + **Auto-Naming File**.")

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
    # Buang karakter aneh agar tidak error saat save di Windows/Linux
    clean = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', clean)

st.header("3. Data Kuis (Survival/Horror)")
example_csv = """Pertanyaan,Pilihan A,Pilihan B,Jawaban Benar
You wake up in a coffin.,Scream for help,Stay calm & conserve oxygen,Stay calm & conserve oxygen
A rabid dog chases you!,Run away,Stand ground & yell,Stand ground & yell"""
quiz_data_text = st.text_area("Paste SEMUA CSV lo di sini (50 baris gass!)", value=example_csv, height=150)

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
    nomor_soal = st.number_input(f"Pilih Soal Nomor Berapa? (1 - {total_soal})", min_value=1, max_value=total_soal, value=1)
with col2:
    if not df.empty and nomor_soal <= len(df):
        selected_row = df.iloc[nomor_soal-1]
        st.info(f"📝 Preview Soal {nomor_soal}: **{selected_row['Pertanyaan']}**")
        # Generate nama file dinamis
        base_name = clean_filename(str(selected_row['Pertanyaan']))
        final_filename = f"{base_name}.mp4"
        st.write(f"📁 Nama file download: `{final_filename}`")

# --- FUNGSI SUARA (EDGE TTS + BOOST) ---
async def get_edge_voice(text, filename, voice_id):
    # VOLUME NAIK 20%, SPEED TURUN 10% (BIAR LEBIH JELAS & DRAMATIS)
    communicate = edge_tts.Communicate(text, voice_id, rate="-10%", volume="+20%")
    await communicate.save(filename)

# --- FUNGSI VISUAL ---
def create_text_clip_pil(text, font_path, fontsize, video_w, duration, is_answer=False):
    W = int(video_w)
    H = int(video_w * 0.8) 
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, fontsize)
    except:
        font = ImageFont.load_default()
    
    avg_char_width = fontsize * 0.5 
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
        box_color = (139, 0, 0, 200) # Merah Darah
    else:
        box_color = (0, 0, 0, 180) # Hitam Pekat
        
    draw.rectangle([box_left, box_top, box_right, box_bottom], fill=box_color, outline=None)
    shadow_offset = 4
    draw.multiline_text((text_x + shadow_offset, text_y + shadow_offset), wrapped_text, font=font, fill='black', align='center')
    draw.multiline_text((text_x, text_y), wrapped_text, font=font, fill='white', align='center')
    final_img = img.crop((0, int(box_top)-10, W, int(box_bottom)+10))
    numpy_img = np.array(final_img)
    clip = ImageClip(numpy_img).set_duration(duration)
    return clip

# --- LOGIC UTAMA ---
def generate_video(row, bg_clip, font_path, music_path, sfx_path, voice_id, status_placeholder):
    duration_q = 9  
    duration_ans = 3
    total_duration = duration_q + duration_ans
    
    status_placeholder.text("🌑 Menyiapkan Video...")
    import random
    if bg_clip.duration > total_duration:
        start_t = random.uniform(0, bg_clip.duration - total_duration)
        video = bg_clip.subclip(start_t, start_t + total_duration)
    else:
        video = bg_clip.loop(duration=total_duration)
        
    target_ratio = 9/16
    current_ratio = video.w / video.h
    if current_ratio > target_ratio:
        new_width = int(video.h * target_ratio)
        if new_width % 2 != 0: new_width -= 1
        video = video.crop(x1=video.w/2 - new_width/2, width=new_width, height=video.h)
    video = video.resize(newsize=(1080, 1920)) 
    
    status_placeholder.text(f"🎙️ Recording voice: {voice_id}...")
    audio_clips = []
    
    tts_filename = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    asyncio.run(get_edge_voice(str(row['Pertanyaan']), tts_filename, voice_id))
    
    tts_clip = AudioFileClip(tts_filename)
    audio_clips.append(tts_clip)
    
    if music_path:
        try:
            m_clip = AudioFileClip(music_path)
            cut_duration = min(m_clip.duration, total_duration)
            bg_music = m_clip.subclip(0, cut_duration).volumex(0.4) 
            audio_clips.append(bg_music)
        except: pass
        
    if sfx_path:
        try:
            s_clip = AudioFileClip(sfx_path)
            sfx = s_clip.set_start(duration_q)
            audio_clips.append(sfx)
        except: pass
    
    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips).set_duration(total_duration)
        video = video.set_audio(final_audio)

    status_placeholder.text("💀 Merakit Visual...")
    clip_q = create_text_clip_pil(str(row['Pertanyaan']), font_path, 75, 1080, total_duration).set_position(('center', 350))
    clip_a = create_text_clip_pil(f"A. {row['Pilihan A']}", font_path, 65, 1080, total_duration).set_position(('center', 900))
    clip_b = create_text_clip_pil(f"B. {row['Pilihan B']}", font_path, 65, 1080, total_duration).set_position(('center', 1150))
    clip_c = create_text_clip_pil(f"Answer: {row['Jawaban Benar']}", font_path, 85, 1080, duration_ans, is_answer=True).set_start(duration_q).set_position(('center', 1450))

    final = CompositeVideoClip([video, clip_q, clip_a, clip_b, clip_c])
    return final

# --- EKSEKUSI ---
# PLACEHOLDER UNTUK TOMBOL DOWNLOAD DI ATAS
download_area = st.empty()

if st.button("💀 Generate Video", use_container_width=True):
    status_text = st.empty()
    
    if not bg_video_file or not font_file:
        st.error("⚠️ Bahan belum lengkap Bos!")
    else:
        try:
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
            
            if df.empty:
                st.error("Data CSV Kosong!")
                st.stop()

            row_index = nomor_soal - 1
            selected_row = df.iloc[row_index]
            
            bg_clip = VideoFileClip(tfile_bg.name)
            
            result_clip = generate_video(selected_row, bg_clip, tfile_font.name, music_path, sfx_path, selected_voice, status_text)
            
            status_text.text(f"🩸 Rendering: {final_filename}...")
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
            result_clip.write_videofile(
                output_path, 
                codec='libx264', 
                audio_codec='aac', 
                fps=24, 
                preset='ultrafast', 
                threads=4,
                ffmpeg_params=['-pix_fmt', 'yuv420p']
            )
            
            status_text.text("✅ Selesai!")
            st.success(f"✅ Video Soal {nomor_soal} Selesai!")
            
            # TAMPILKAN TOMBOL DOWNLOAD DI ATAS
            with open(output_path, "rb") as file:
                download_area.download_button(
                    label=f"📥 DOWNLOAD SEKARANG: {final_filename}",
                    data=file,
                    file_name=final_filename,
                    mime="video/mp4",
                    type="primary",
                    use_container_width=True
                )
            
            # Video Preview tetap di bawah
            st.video(output_path)
                
        except Exception as e:
            st.error(f"Error: {e}")

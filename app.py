import streamlit as st
import yt_dlp
from moviepy.video.io.VideoFileClip import VideoFileClip
import os
import time

# --- SETUP HALAMAN ---
st.set_page_config(page_title="YT Clipper Gratis", page_icon="✂️", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h1 { color: #FF4B4B; text-align: center; }
    .stButton>button { width: 100%; background-color: #FF4B4B; color: white; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("✂️ YT CLIPPER PRO (FREE)")
st.caption("Download & Potong Video Youtube Tanpa Watermark")

# --- FUNGSI DOWNLOADER ---
@st.cache_resource(show_spinner=False)
def download_video(url):
    # Buat folder temp
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    
    # Settingan yt-dlp (Ambil format MP4 terbaik yang ringan / max 720p biar server kuat)
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info['title'], info['duration']

# --- UI INPUT ---
url = st.text_input("🔗 Tempel Link YouTube di sini:", placeholder="https://youtube.com/watch?v=...")

if url:
    try:
        with st.spinner("⏳ Sedang menyedot video dari YouTube... (Tunggu ya)"):
            file_path, title, duration = download_video(url)
        
        st.success(f"✅ Video Terambil: **{title}**")
        
        # --- PREVIEW VIDEO ASLI ---
        # st.video(file_path) # Opsional: Dimatikan biar hemat kuota server, nyalakan kalau perlu
        
        st.markdown("---")
        st.markdown("### ✂️ Pilih Bagian yang Mau Dipotong")
        
        # SLIDER PEMOTONG
        # Konversi durasi ke menit:detik buat display
        start_time, end_time = st.slider(
            "Geser untuk memilih rentang waktu (Detik):",
            0, duration, (0, min(duration, 60)) # Default 60 detik pertama
        )
        
        st.info(f"⏱️ Durasi Klip: **{end_time - start_time} detik** (Dari detik ke-{start_time} sampai {end_time})")

        # --- TOMBOL EKSEKUSI ---
        if st.button("✂️ POTONG & DOWNLOAD KLIP"):
            output_filename = f"clip_{int(time.time())}.mp4"
            
            with st.spinner("🔪 Sedang menggunting video..."):
                try:
                    # Proses Potong Pakai MoviePy
                    with VideoFileClip(file_path) as video:
                        new_clip = video.subclipped(start_time, end_time)
                        new_clip.write_videofile(output_filename, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True, logger=None)
                    
                    # Tampilkan Hasil
                    st.success("✨ Selesai! Silakan download di bawah.")
                    st.video(output_filename)
                    
                    # Tombol Download
                    with open(output_filename, "rb") as file:
                        btn = st.download_button(
                            label="⬇️ DOWNLOAD MP4",
                            data=file,
                            file_name=f"Klip_{title[:10]}.mp4",
                            mime="video/mp4"
                        )
                    
                    # Bersih-bersih file temp (Opsional)
                    # os.remove(output_filename) 
                    
                except Exception as e:
                    st.error(f"Gagal memotong: {e}")
                    
    except Exception as e:
        st.error(f"Error Download: {e}. Pastikan link valid atau video tidak diprivate.")

st.markdown("---")
st.caption("⚠️ Catatan: Maksimal resolusi diset ke 720p agar server gratisan tidak meledak.")

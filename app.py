import streamlit as st
import yt_dlp
from moviepy.video.io.VideoFileClip import VideoFileClip
import os
import time

# --- SETUP HALAMAN ---
st.set_page_config(page_title="YT Clipper Pro", page_icon="✂️", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h1 { color: #FF4B4B; text-align: center; }
    .stButton>button { width: 100%; background-color: #FF4B4B; color: white; font-weight: bold; }
    .stSuccess { background-color: #1b5e20; }
</style>
""", unsafe_allow_html=True)

st.title("✂️ YT CLIPPER PRO")
st.caption("Solusi Download Video YouTube yang Kena Blokir 403")

# --- SIDEBAR: KUNCI RAHASIA (COOKIES) ---
with st.sidebar:
    st.header("🔐 Kunci Anti-Blokir")
    st.info("YouTube sering memblokir server cloud (Error 403). Solusinya: Upload Cookies asli dari browser kamu.")
    uploaded_cookie = st.file_uploader("Upload file 'cookies.txt' di sini:", type=["txt"])

# --- FUNGSI DOWNLOADER ---
def download_video(url, cookie_path=None):
    # Buat folder temp
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    
    # Settingan yt-dlp dengan User Agent & Cookies
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # NIPU YOUTUBE BIAR DIKIRA BROWSER ASLI:
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'referer': 'https://www.youtube.com/',
    }
    
    # Jika ada cookies, pasang!
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info['title'], info['duration']

# --- UI UTAMA ---
url = st.text_input("🔗 Tempel Link YouTube:", placeholder="https://youtube.com/watch?v=...")

if url:
    # Cek Cookie dulu
    cookie_temp_path = None
    if uploaded_cookie is not None:
        cookie_temp_path = "temp_cookies.txt"
        with open(cookie_temp_path, "wb") as f:
            f.write(uploaded_cookie.getbuffer())
        st.toast("🍪 Cookies berhasil dimuat! Mencoba menembus YouTube...", icon="🔓")
    
    try:
        with st.spinner("⏳ Sedang download video (Bismillah tembus)..."):
            # Panggil fungsi download dengan atau tanpa cookie
            file_path, title, duration = download_video(url, cookie_temp_path)
        
        st.success(f"✅ SUKSES: **{title}**")
        
        st.markdown("---")
        st.markdown("### ✂️ Editor Pemotong")
        
        # SLIDER (Batas max 300 detik biar gak crash servernya)
        max_preview = min(duration, 300) 
        
        start_time, end_time = st.slider(
            "Pilih Durasi Potong (Detik):",
            0, duration, (0, 30) 
        )
        
        durasi_klip = end_time - start_time
        st.info(f"⏱️ Durasi Klip: **{durasi_klip} detik**")

        if st.button("✂️ POTONG SEKARANG"):
            output_filename = f"clip_{int(time.time())}.mp4"
            
            with st.spinner("🔪 Sedang menggunting..."):
                try:
                    with VideoFileClip(file_path) as video:
                        new_clip = video.subclipped(start_time, end_time)
                        # Preset ultrafast biar server gak berat
                        new_clip.write_videofile(output_filename, codec="libx264", audio_codec="aac", preset="ultrafast", temp_audiofile='temp-audio.m4a', remove_temp=True, logger=None)
                    
                    st.success("✨ Video Siap!")
                    
                    with open(output_filename, "rb") as file:
                        st.download_button(
                            label="⬇️ DOWNLOAD HASILNYA",
                            data=file,
                            file_name=f"Klip_{title[:10]}.mp4",
                            mime="video/mp4"
                        )
                    
                    # Cleanup
                    if os.path.exists(output_filename):
                        os.remove(output_filename)
                        
                except Exception as e:
                    st.error(f"Gagal memotong: {e}")
                    
    except Exception as e:
        if "403" in str(e):
            st.error("🛑 MASIH DIBLOKIR YOUTUBE (403).")
            st.warning("👉 Solusi: Kamu WAJIB upload file 'cookies.txt' di menu sebelah kiri agar YouTube mengenali kamu sebagai manusia.")
        else:
            st.error(f"Error Lain: {e}")

    # Hapus cookie temp setelah pakai biar aman
    if cookie_temp_path and os.path.exists(cookie_temp_path):
        os.remove(cookie_temp_path)

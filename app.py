import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
from youtube_transcript_api import YouTubeTranscriptApi
from groq import Groq
import os
import time
import json
import re

# --- SETUP HALAMAN ---
st.set_page_config(page_title="AI Viral Clipper", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h1 { color: #00C853; text-align: center; }
    .stButton>button { width: 100%; background-color: #00C853; color: white; font-weight: bold; border-radius: 8px; }
    .clip-box { background-color: #1F2937; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #374151; }
</style>
""", unsafe_allow_html=True)

st.title("🎬 AI VIRAL CLIPPER (9:16)")
st.caption("Ubah Video Panjang Jadi Shorts Otomatis Berdasarkan Analisa AI")

# --- SIDEBAR: KONFIGURASI ---
with st.sidebar:
    st.header("⚙️ Konfigurasi")
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except:
        api_key = st.text_input("🔑 Masukkan API Key Groq:", type="password")
    
    st.info("ℹ️ Upload 'cookies.txt' jika video diblokir YouTube.")
    uploaded_cookie = st.file_uploader("Upload Cookies", type=["txt"])

# --- FUNGSI 1: AMBIL TRANSKRIP ---
def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['id', 'en'])
        formatter = ""
        for i in transcript:
            # Ambil teks setiap 10 detik biar gak kepanjangan buat AI
            formatter += f"{int(i['start'])}s: {i['text']}\n"
        return formatter
    except Exception as e:
        return None

# --- FUNGSI 2: ANALISA AI (GROQ) ---
def analyze_virality(transcript_text, api_key):
    client = Groq(api_key=api_key)
    
    prompt = """
    Kamu adalah Video Editor profesional untuk TikTok/Shorts.
    Tugasmu: Cari 3-5 momen PALING MENARIK/VIRAL dari transkrip video di bawah ini.
    Kriteria Viral: Lucu, Debat Panas, Fakta Mengejutkan, atau Motivasi Tinggi.
    
    Output WAJIB format JSON murni seperti ini (tanpa markdown):
    [
        {"start": 120, "end": 150, "title": "Judul Menarik 1", "reason": "Alasan viral"},
        {"start": 300, "end": 340, "title": "Judul Menarik 2", "reason": "Alasan viral"}
    ]
    
    Durasi klip per item: Minimal 20 detik, Maksimal 60 detik.
    
    TRANSKRIP:
    """ + transcript_text[:15000] # Batasi karakter biar gak error token limit
    
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.5
    )
    
    content = completion.choices[0].message.content
    # Bersihkan markdown json kalau ada
    content = re.sub(r'```json', '', content).replace('```', '').strip()
    return json.loads(content)

# --- FUNGSI 3: DOWNLOAD VIDEO ---
def download_video(url, cookie_path=None):
    if not os.path.exists("downloads"): os.makedirs("downloads")
    
    ydl_opts = {
        'format': 'best[ext=mp4]', # Download satu file yg ada video+audio langsung biar aman editnya
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    if cookie_path: ydl_opts['cookiefile'] = cookie_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info['title']

# --- FUNGSI 4: CROP 9:16 (VERTICAL) ---
def process_clip(video_path, start, end, output_name):
    try:
        with VideoFileClip(video_path) as clip:
            # 1. Potong durasi
            subclip = clip.subclip(start, end)
            
            # 2. Logika Crop 9:16 (Center Crop)
            w, h = subclip.size
            target_ratio = 9/16
            
            # Hitung lebar baru biar rasionya 9:16
            new_w = h * target_ratio
            
            # Kalau lebar video asli lebih lebar dari target (Landscape ke Portrait)
            if new_w <= w:
                x_center = w / 2
                x1 = x_center - (new_w / 2)
                x2 = x_center + (new_w / 2)
                # Crop tengah
                cropped_clip = subclip.crop(x1=x1, y1=0, x2=x2, y2=h)
            else:
                # Kalau video aslinya aneh, resize aja
                cropped_clip = subclip.resize(height=1280) 
            
            # 3. Resize ke HD Mobile (720x1280) biar ringan di server
            final_clip = cropped_clip.resize(newsize=(720, 1280))
            
            final_clip.write_videofile(output_filename=output_name, codec='libx264', audio_codec='aac', preset='ultrafast', logger=None)
            return True
    except Exception as e:
        st.error(f"Error Processing: {e}")
        return False

# --- UI UTAMA ---
url = st.text_input("🔗 Link YouTube Panjang:", placeholder="https://youtube.com/watch?v=...")

if st.button("🚀 ANALISA & BUAT SHORTS"):
    if not url or not api_key:
        st.error("⚠️ Masukkan Link URL & API Key Groq dulu.")
    else:
        # Setup Cookie
        cookie_path = None
        if uploaded_cookie:
            with open("temp_cookies.txt", "wb") as f: f.write(uploaded_cookie.getbuffer())
            cookie_path = "temp_cookies.txt"

        # 1. Ambil Video ID
        video_id = ""
        if "v=" in url: video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be" in url: video_id = url.split("/")[-1]
        
        # 2. Ambil Transkrip
        with st.status("🔍 Sedang membaca transkrip video...", expanded=True) as status:
            transcript_text = get_transcript(video_id)
            
            if not transcript_text:
                status.error("❌ Gagal ambil transkrip. Pastikan video ada CC/Subtitle.")
                st.stop()
            
            status.write("✅ Transkrip terbaca. Mengirim ke AI...")
            
            # 3. Analisa AI
            try:
                viral_moments = analyze_virality(transcript_text, api_key)
                status.write(f"✅ AI menemukan {len(viral_moments)} momen viral!")
            except Exception as e:
                status.error(f"❌ Error AI: {e}")
                st.stop()
            
            # 4. Download Video Fisik
            status.write("⬇️ Sedang download video asli (sabar ya)...")
            try:
                video_path, title = download_video(url, cookie_path)
            except Exception as e:
                status.error("❌ Gagal download video (Coba pakai Cookies).")
                st.stop()
                
            status.update(label="✅ Analisa Selesai!", state="complete", expanded=False)

        # 5. Tampilkan Hasil & Proses Cutting
        st.subheader("🔥 Hasil Deteksi AI")
        
        for i, moment in enumerate(viral_moments):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"""
                <div class='clip-box'>
                    <h4>🎥 Klip #{i+1}: {moment['title']}</h4>
                    <p>💡 <b>Alasan Viral:</b> {moment['reason']}</p>
                    <p>⏱️ <b>Timestamp:</b> {moment['start']}s - {moment['end']}s</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # Tombol Generate Per Klip (Biar server gak meledak render semua sekaligus)
                if st.button(f"✂️ GENERATE KLIP #{i+1}", key=f"btn_{i}"):
                    output_name = f"shorts_{i}_{int(time.time())}.mp4"
                    with st.spinner("🔄 Sedang Cropping ke 9:16..."):
                        success = process_clip(video_path, moment['start'], moment['end'], output_name)
                        if success:
                            st.success("✨ Selesai!")
                            st.video(output_name)
                            with open(output_name, "rb") as f:
                                st.download_button("⬇️ DOWNLOAD", f, file_name=f"Shorts_{i+1}.mp4")
                            # Hapus file output hemat storage
                            os.remove(output_name)

        # Cleanup video asli nanti manual atau auto restart session

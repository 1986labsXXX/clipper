import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip
from groq import Groq
import os
import time
import json
import re
import glob

# --- SETUP HALAMAN ---
st.set_page_config(page_title="AI Viral Clipper Pro", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h1 { color: #00C853; text-align: center; }
    .stButton>button { width: 100%; background-color: #00C853; color: white; font-weight: bold; border-radius: 8px; }
    .clip-box { background-color: #1F2937; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #374151; }
</style>
""", unsafe_allow_html=True)

st.title("🎬 AI VIRAL CLIPPER (VERSI YT-DLP)")
st.caption("Solusi Transkrip Bandel: Menggunakan yt-dlp untuk menyedot subtitle otomatis.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Konfigurasi")
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except:
        api_key = st.text_input("🔑 Masukkan API Key Groq:", type="password")
    
    st.info("ℹ️ Upload 'cookies.txt' (Wajib agar tidak diblokir).")
    uploaded_cookie = st.file_uploader("Upload Cookies", type=["txt"])

# --- FUNGSI 1: SEDOT TRANSKRIP PAKAI YT-DLP (PREMAN STYLE) ---
def get_transcript_ytdlp(url, cookie_path=None):
    # Hapus file subtitle lama kalau ada
    for f in glob.glob("temp_subs.*"):
        os.remove(f)

    ydl_opts = {
        'skip_download': True,      # Jangan download videonya dulu
        'writeautomaticsub': True,  # Paksa ambil Auto-Subs
        'writesubtitles': True,     # Ambil manual subs juga kalau ada
        'subtitleslangs': ['id', 'en', 'en-orig'], # Prioritas bahasa
        'outtmpl': 'temp_subs',     # Nama file sementara
        'quiet': True,
        'no_warnings': True,
    }
    
    if cookie_path: ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Cari file subtitle yang terdownload (bisa .vtt atau .srv3)
        subs_files = glob.glob("temp_subs.*.vtt")
        
        if not subs_files:
            return None # Gagal dapat file
            
        # Baca file VTT dan bersihkan jadi Teks Biasa
        vtt_path = subs_files[0]
        cleaned_text = ""
        seen_lines = set()
        
        with open(vtt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                # Hapus timestamp (contoh: 00:00:01.000 --> 00:00:04.000)
                if "-->" in line: continue
                # Hapus header VTT/Numbers
                if line == "WEBVTT" or line.isdigit() or not line: continue
                # Hapus tag styling (misal <c.colorE5E5E5>)
                line = re.sub(r'<[^>]+>', '', line)
                # Hindari duplikasi baris (Auto-sub suka ngulang kalimat)
                if line not in seen_lines:
                    cleaned_text += line + " "
                    seen_lines.add(line)
        
        return cleaned_text

    except Exception as e:
        print(f"Error yt-dlp subs: {e}")
        return None

# --- FUNGSI 2: ANALISA AI ---
def analyze_virality(transcript_text, api_key):
    client = Groq(api_key=api_key)
    # Potong teks biar gak kepanjangan (Max 20.000 char untuk hemat token)
    truncated_text = transcript_text[:20000]
    
    prompt = """
    Kamu adalah Video Editor Handal. Tugasmu mencari "Viral Moments" dari transkrip mentah ini.
    Cari 3-4 bagian paling menarik (Lucu, Kontroversial, Insightful).
    
    PENTING:
    Karena transkrip ini tidak punya timestamp akurat (mentah), kamu harus MEMPERKIRAKAN timestamp berdasarkan urutan teks.
    1 paragraf teks kira-kira 10-20 detik.
    
    Output WAJIB JSON murni:
    [
        {"start": 60, "end": 100, "title": "Topik 1", "reason": "Alasan"},
        {"start": 300, "end": 350, "title": "Topik 2", "reason": "Alasan"}
    ]
    
    TRANSKRIP MENTAH:
    """ + truncated_text
    
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.5
    )
    content = completion.choices[0].message.content
    content = re.sub(r'```json', '', content).replace('```', '').strip()
    return json.loads(content)

# --- FUNGSI 3: DOWNLOAD VIDEO ---
def download_video(url, cookie_path=None):
    if not os.path.exists("downloads"): os.makedirs("downloads")
    ydl_opts = {
        'format': 'best[ext=mp4]', 
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
    }
    if cookie_path: ydl_opts['cookiefile'] = cookie_path
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info['title']

# --- FUNGSI 4: CROP 9:16 ---
def process_clip(video_path, start, end, output_name):
    try:
        with VideoFileClip(video_path) as clip:
            # Validasi durasi biar gak error out of bounds
            if end > clip.duration: end = clip.duration
            if start >= end: start = end - 30 
            
            subclip = clip.subclip(start, end)
            w, h = subclip.size
            
            # Logika Center Crop 9:16
            target_ratio = 9/16
            new_w = h * target_ratio
            if new_w <= w:
                x_center = w / 2
                x1 = x_center - (new_w / 2)
                x2 = x_center + (new_w / 2)
                final_clip = subclip.crop(x1=x1, y1=0, x2=x2, y2=h).resize(newsize=(720, 1280))
            else:
                final_clip = subclip.resize(height=1280)
            
            final_clip.write_videofile(output_name, codec='libx264', audio_codec='aac', preset='ultrafast', logger=None)
            return True
    except Exception as e:
        st.error(f"Gagal Crop: {e}")
        return False

# --- UI UTAMA ---
url = st.text_input("🔗 Link YouTube:", placeholder="https://youtube.com/watch?v=...")

if st.button("🚀 GAS TRANSKRIP & ANALISA"):
    if not url or not api_key:
        st.error("⚠️ Masukkan URL & API Key.")
    else:
        # Setup Cookie
        cookie_path = None
        if uploaded_cookie:
            with open("temp_cookies.txt", "wb") as f: f.write(uploaded_cookie.getbuffer())
            cookie_path = "temp_cookies.txt"

        with st.status("🔍 Menjalankan Misi...", expanded=True) as status:
            # 1. AMBIL TRANSKRIP (METODE YT-DLP)
            status.write("📑 Menyedot Subtitle Otomatis (Metode yt-dlp)...")
            transcript_text = get_transcript_ytdlp(url, cookie_path)
            
            if not transcript_text or len(transcript_text) < 50:
                status.error("❌ Gagal total ambil subtitle. YouTube memblokir akses teksnya, atau video benar-benar bisu.")
                st.stop()
            
            status.write("✅ Subtitle tersedot! Mengirim ke Otak AI...")
            
            # 2. ANALISA AI
            try:
                viral_moments = analyze_virality(transcript_text, api_key)
                status.write(f"✅ AI menemukan {len(viral_moments)} klip potensial.")
            except Exception as e:
                status.error(f"❌ AI Pusing: {e}")
                st.stop()
            
            # 3. DOWNLOAD VIDEO
            status.write("⬇️ Mendownload Video Fisik...")
            try:
                video_path, title = download_video(url, cookie_path)
            except:
                status.error("❌ Gagal download video.")
                st.stop()
                
            status.update(label="✅ Selesai!", state="complete", expanded=False)

        # 4. TAMPILKAN HASIL
        st.subheader("🔥 Hasil Kurasi AI")
        st.caption("Catatan: Karena subtitle otomatis tidak punya timestamp akurat, silakan geser slider sedikit jika potongan kurang pas.")

        for i, moment in enumerate(viral_moments):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"""
                <div class='clip-box'>
                    <h4>🎥 Klip #{i+1}: {moment['title']}</h4>
                    <p>💡 {moment['reason']}</p>
                    <p>⏱️ Estimasi: {moment['start']}s - {moment['end']}s</p>
                </div>
                """, unsafe_allow_html=True)
                
                # SLIDER MANUAL ADJUSTMENT (Fitur Penting!)
                # Karena transkrip auto-sub kadang timestampnya ngaco, user bisa geser dikit
                m_start, m_end = st.slider(f"Fine-Tune Klip #{i+1}", 0, int(VideoFileClip(video_path).duration), (moment['start'], moment['end']), key=f"sld_{i}")
            
            with col2:
                if st.button(f"✂️ POTONG #{i+1}", key=f"btn_{i}"):
                    output_name = f"shorts_{i}_{int(time.time())}.mp4"
                    with st.spinner("Processing..."):
                        if process_clip(video_path, m_start, m_end, output_name):
                            st.video(output_name)
                            with open(output_name, "rb") as f:
                                st.download_button("⬇️ SIMPAN", f, file_name=f"Shorts_{i+1}.mp4")
                            os.remove(output_name)

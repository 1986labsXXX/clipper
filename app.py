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
st.set_page_config(page_title="AI Viral Clipper (Fix Download)", page_icon="💾", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h1 { color: #00E676; text-align: center; }
    .stButton>button { width: 100%; background-color: #00E676; color: black; font-weight: bold; border-radius: 8px; }
    .clip-box { background-color: #1F2937; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #374151; }
</style>
""", unsafe_allow_html=True)

st.title("💾 AI VIRAL CLIPPER (FIX DOWNLOAD)")
st.caption("Versi Final: Download Menggunakan RAM (Anti-File Hilang)")

# --- KONFIGURASI ---
api_key = "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" # API Key Bos

# --- INISIALISASI MEMORI ---
if 'viral_moments' not in st.session_state:
    st.session_state.viral_moments = []
if 'video_path' not in st.session_state:
    st.session_state.video_path = None
if 'video_title' not in st.session_state:
    st.session_state.video_title = ""

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    st.success("✅ API Ready")
    st.info("ℹ️ Upload 'cookies.txt' agar lancar.")
    uploaded_cookie = st.file_uploader("Upload Cookies", type=["txt"])

# --- FUNGSI 1: SEDOT TRANSKRIP ---
def get_transcript_ytdlp(url, cookie_path=None):
    for f in glob.glob("temp_subs.*"):
        try: os.remove(f)
        except: pass

    ydl_opts = {
        'skip_download': True,      
        'writeautomaticsub': True,  
        'writesubtitles': True,     
        'subtitleslangs': ['id', 'en', 'en-orig'], 
        'outtmpl': 'temp_subs',     
        'quiet': True,
        'no_warnings': True,
    }
    if cookie_path: ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        subs_files = glob.glob("temp_subs.*.vtt")
        if not subs_files: return None
            
        vtt_path = subs_files[0]
        cleaned_text = ""
        seen_lines = set()
        with open(vtt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if "-->" in line or line == "WEBVTT" or line.isdigit() or not line: continue
                line = re.sub(r'<[^>]+>', '', line)
                if line not in seen_lines:
                    cleaned_text += line + " "
                    seen_lines.add(line)
        return cleaned_text
    except Exception as e:
        print(f"Error Transkrip: {e}")
        return None

# --- FUNGSI 2: ANALISA AI ---
def analyze_virality(transcript_text, api_key):
    client = Groq(api_key=api_key)
    truncated_text = transcript_text[:25000]
    
    prompt = """
    Kamu adalah Video Editor. Cari 3 bagian viral.
    Output WAJIB JSON MURNI:
    [
        {"start": 60, "end": 100, "title": "Judul 1", "reason": "Alasan singkat"},
        {"start": 300, "end": 350, "title": "Judul 2", "reason": "Alasan singkat"}
    ]
    TRANSKRIP:
    """ + truncated_text
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.4 
        )
        content = completion.choices[0].message.content
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match: return json.loads(match.group(0))
        else: raise ValueError("JSON Error")
    except:
        return [{"start": 0, "end": 30, "title": "⚠️ Mode Manual", "reason": "AI Error"}]

# --- FUNGSI 3: DOWNLOAD VIDEO ---
def download_video(url, cookie_path=None):
    if not os.path.exists("downloads"): os.makedirs("downloads")
    ydl_opts = {
        'format': 'best[height<=720][ext=mp4]/best[height<=480][ext=mp4]', 
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    if cookie_path: ydl_opts['cookiefile'] = cookie_path
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info['title']

# --- FUNGSI 4: CROP 9:16 (MODIFIKASI DEBUG) ---
def process_clip(video_path, start, end, output_name):
    try:
        with VideoFileClip(video_path) as clip:
            if end > clip.duration: end = clip.duration
            if start >= end: start = end - 30 
            
            subclip = clip.subclip(start, end)
            w, h = subclip.size
            
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
            return True, None # Sukses
    except Exception as e:
        return False, str(e) # Gagal & kirim error

# --- UI UTAMA ---
url = st.text_input("🔗 Link YouTube:", placeholder="https://youtube.com/watch?v=...")

# TOMBOL 1: ANALISA
if st.button("🚀 GAS (ANALISA)"):
    if not url:
        st.error("⚠️ Link kosong!")
    else:
        cookie_path = "temp_cookies.txt" if uploaded_cookie else None
        if uploaded_cookie:
            with open(cookie_path, "wb") as f: f.write(uploaded_cookie.getbuffer())

        with st.status("⚡ Turbo Processing...", expanded=True) as status:
            status.write("📑 Sedot Subtitle...")
            transcript_text = get_transcript_ytdlp(url, cookie_path)
            
            if not transcript_text or len(transcript_text) < 50:
                status.error("❌ Gagal ambil subtitle.")
                st.stop()
            
            status.write("🧠 AI Berpikir...")
            st.session_state.viral_moments = analyze_virality(transcript_text, api_key)
            
            status.write("⬇️ Download Video Ringan...")
            try:
                v_path, v_title = download_video(url, cookie_path)
                st.session_state.video_path = v_path
                st.session_state.video_title = v_title
            except Exception as e:
                status.error(f"❌ Gagal download: {e}")
                st.stop()
                
            status.update(label="✅ SELESAI!", state="complete", expanded=False)

# TAMPILAN HASIL
if st.session_state.video_path and st.session_state.viral_moments:
    st.markdown("---")
    st.subheader(f"🎬 {st.session_state.video_title}")
    
    for i, moment in enumerate(st.session_state.viral_moments):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**#{i+1} {moment['title']}**\n\n*{moment['reason']}*")
            try: d_dur = int(VideoFileClip(st.session_state.video_path).duration)
            except: d_dur = 600
            m_start, m_end = st.slider(f"Durasi #{i+1}", 0, d_dur, (int(moment['start']), int(moment['end'])), key=f"s_{i}")
        
        with col2:
            # TOMBOL 2: RENDER & DOWNLOAD
            if st.button(f"🎬 RENDER #{i+1}", key=f"b_{i}"):
                out_file = f"short_{i}_{int(time.time())}.mp4"
                
                with st.spinner("⏳ Rendering... (Tunggu sampai tombol download muncul)"):
                    # Proses Clip
                    success, error_msg = process_clip(st.session_state.video_path, m_start, m_end, out_file)
                    
                    if success:
                        st.success("✅ Video Siap!")
                        
                        # --- TRIK RAHASIA: BACA KE RAM ---
                        # Kita baca videonya jadi 'Bytes' biar aman disimpan di tombol download
                        try:
                            with open(out_file, "rb") as f:
                                video_bytes = f.read()
                            
                            # Tampilkan Preview
                            st.video(video_bytes)
                            
                            # Tampilkan Tombol Download (Pakai data dari RAM)
                            st.download_button(
                                label="⬇️ DOWNLOAD MP4",
                                data=video_bytes,
                                file_name=f"Shorts_{i+1}.mp4",
                                mime="video/mp4"
                            )
                            
                            # Hapus file fisik (Aman karena data udah di RAM tombol)
                            os.remove(out_file)
                            
                        except Exception as e:
                            st.error(f"Gagal menyiapkan download: {e}")
                            
                    else:
                        st.error(f"❌ Render Gagal: {error_msg}")

    if st.button("🗑️ Reset Semua"):
        st.session_state.viral_moments = []
        st.session_state.video_path = None
        st.rerun()

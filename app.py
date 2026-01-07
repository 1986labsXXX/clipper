import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip
from groq import Groq
import os
import time
import json
import re
import glob
import webvtt
from datetime import timedelta

# --- 🛠️ FIX BUG MOVIEPY ---
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# --- SETUP HALAMAN ---
st.set_page_config(page_title="AI Clipper + Subs", page_icon="🔥", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    h1 { color: #FFEB3B; text-align: center; text-shadow: 0 0 10px #FBC02D; }
    .stButton>button { width: 100%; background-color: #FBC02D; color: black; font-weight: bold; border-radius: 8px; }
    .clip-box { background-color: #1E1E1E; padding: 20px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #333; }
    .highlight { color: #FFEB3B; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🔥 AI CLIPPER + SUBTITLE KUNING")
st.caption("Akurasi Tinggi (Timestamp Asli) & Auto-Subtitle")

# --- KONFIGURASI ---
api_key = "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" 

# --- SESSION STATE ---
if 'data' not in st.session_state:
    st.session_state.data = {}

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    st.success("✅ API Ready")
    uploaded_cookie = st.file_uploader("Upload Cookies (Wajib)", type=["txt"])

# --- FUNGSI 1: SEDOT SUBTITLE & FORMAT KE AI ---
def get_transcript_with_timestamps(url, cookie_path=None):
    # Bersihkan file lama
    for f in glob.glob("temp_subs.*"): 
        try: os.remove(f)
        except: pass

    # Download VTT (Subtitle)
    ydl_opts = {
        'skip_download': True,      
        'writeautomaticsub': True,
        'writesubtitles': True,     
        'subtitleslangs': ['id', 'en'], 
        'outtmpl': 'temp_subs',     
        'quiet': True,
    }
    if cookie_path: ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Cari file VTT
        vtt_files = glob.glob("temp_subs.*.vtt")
        if not vtt_files: return None, None
        
        vtt_path = vtt_files[0]
        
        # PARSING CERDAS: Gabungkan kalimat per 15 detik biar AI enak bacanya
        transcript_for_ai = ""
        captions = webvtt.read(vtt_path)
        
        chunk_start = 0
        current_chunk = []
        
        for caption in captions:
            start_seconds = caption.start_in_seconds
            text = caption.text.replace('\n', ' ').strip()
            
            # Kumpulkan teks setiap 15 detik
            if start_seconds - chunk_start < 15:
                current_chunk.append(text)
            else:
                # Tulis ke format AI: [00:00 - 00:15] Teks...
                time_label = f"[{int(chunk_start)}s - {int(start_seconds)}s]"
                full_text = " ".join(current_chunk)
                if full_text:
                    transcript_for_ai += f"{time_label} {full_text}\n"
                
                # Reset chunk
                chunk_start = start_seconds
                current_chunk = [text]
                
        return transcript_for_ai, vtt_path

    except Exception as e:
        print(f"Error VTT: {e}")
        return None, None

# --- FUNGSI 2: ANALISA AI (LEBIH AKURAT) ---
def analyze_virality(transcript_text, api_key):
    client = Groq(api_key=api_key)
    truncated_text = transcript_text[:28000] # Token limit
    
    prompt = """
    Kamu adalah Video Editor. Tugas: Pilih 3 bagian PALING MENARIK dari transkrip ini.
    
    PENTING:
    - Transkrip sudah ada timestampnya [start - end]. 
    - GUNAKAN TIMESTAMP ITU. Jangan ngarang waktu sendiri!
    - Pastikan durasi klip antara 30 - 60 detik.
    
    Output WAJIB JSON MURNI:
    [
        {"start": 10, "end": 50, "title": "Judul Menarik", "reason": "Alasan singkat"}
    ]
    
    TRANSKRIP:
    """ + truncated_text
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3 
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
        'format': 'best[height<=720][ext=mp4]', # 720p Cukup
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
    }
    if cookie_path: ydl_opts['cookiefile'] = cookie_path
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info['title']

# --- FUNGSI 4: GENERATOR TEXT IMAGE (PENGGANTI TEXTCLIP) ---
def generator(txt):
    # Settingan Subtitle Kuning
    return TextClip(txt, font='Arial-Bold', fontsize=50, color='yellow', stroke_color='black', stroke_width=2, method='caption', size=(680, None), align='center')

# --- FUNGSI 5: PROCESS VIDEO + SUBTITLES ---
def process_clip_with_subs(video_path, vtt_path, start, end, output_name):
    try:
        # 1. Load Video & Crop 9:16
        clip = VideoFileClip(video_path)
        if end > clip.duration: end = clip.duration
        
        subclip = clip.subclip(start, end)
        w, h = subclip.size
        
        # Center Crop
        target_ratio = 9/16
        new_w = h * target_ratio
        if new_w <= w:
            x_center = w / 2
            subclip = subclip.crop(x1=x_center - new_w/2, y1=0, width=new_w, height=h)
        subclip = subclip.resize(newsize=(720, 1280))
        
        # 2. Bikin Subtitle
        # Ambil caption yg sesuai range waktu
        captions = webvtt.read(vtt_path)
        subs_data = []
        
        for c in captions:
            # Cek apakah caption ada di dalam range potongan kita
            # Kita kasih buffer dikit biar gak kepotong
            if (c.start_in_seconds >= start) and (c.start_in_seconds < end):
                # Geser waktu subtitle biar mulai dari 0 relatif terhadap potongan
                local_start = max(0, c.start_in_seconds - start)
                local_end = min(end - start, c.end_in_seconds - start)
                
                if local_end > local_start:
                    subs_data.append(((local_start, local_end), c.text.replace('\n', ' ')))
        
        # Jika ada subtitle, burn ke video
        if subs_data:
            try:
                # Buat SubtitlesClip
                subtitles = SubtitlesClip(subs_data, generator)
                # Set posisi subtitle (sedikit di atas bawah)
                subtitles = subtitles.set_position(('center', 1000)) 
                
                final_clip = CompositeVideoClip([subclip, subtitles])
            except Exception as e:
                print(f"Gagal bikin subtitle (mungkin ImageMagick missing): {e}")
                final_clip = subclip # Fallback tanpa subs
        else:
            final_clip = subclip

        # 3. Render
        final_clip.write_videofile(output_name, codec='libx264', audio_codec='aac', preset='ultrafast', logger=None)
        return True, None

    except Exception as e:
        return False, str(e)

# --- UI UTAMA ---
url = st.text_input("🔗 Link YouTube:", placeholder="https://youtube.com/watch?v=...")

# TOMBOL 1: ANALISA
if st.button("🚀 SCAN + ANALISA"):
    if not url:
        st.error("⚠️ Link kosong!")
    else:
        # Setup Cookie
        cookie_path = "temp_cookies.txt" if uploaded_cookie else None
        if uploaded_cookie:
            with open(cookie_path, "wb") as f: f.write(uploaded_cookie.getbuffer())

        with st.status("🕵️ Sedang Bekerja...", expanded=True) as status:
            status.write("📑 Download Subtitle & Sync Waktu...")
            transcript_text, vtt_path = get_transcript_with_timestamps(url, cookie_path)
            
            if not transcript_text:
                status.error("❌ Gagal. Pastikan video ada CC (Auto-generated OK).")
                st.stop()
            
            # Simpan path VTT
            st.session_state.data['vtt_path'] = vtt_path
            
            status.write("🧠 AI Menganalisa Konten...")
            st.session_state.data['moments'] = analyze_virality(transcript_text, api_key)
            
            status.write("⬇️ Download Video Bahan...")
            try:
                v_path, v_title = download_video(url, cookie_path)
                st.session_state.data['video_path'] = v_path
                st.session_state.data['title'] = v_title
            except Exception as e:
                status.error(f"❌ Error Download: {e}")
                st.stop()
                
            status.update(label="✅ SIAP EDIT!", state="complete", expanded=False)

# TAMPILAN HASIL
if 'moments' in st.session_state.data:
    st.markdown("---")
    st.subheader(f"🎬 {st.session_state.data.get('title', 'Video')}")
    
    moments = st.session_state.data['moments']
    v_path = st.session_state.data['video_path']
    vtt_path = st.session_state.data.get('vtt_path')
    
    for i, moment in enumerate(moments):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"""
            <div class='clip-box'>
                <h4 class='highlight'>#{i+1} {moment['title']}</h4>
                <p>{moment['reason']}</p>
                <p>⏱️ <b>Akurasi AI:</b> {moment['start']}s - {moment['end']}s</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Slider Fine-Tune
            try: d_dur = int(VideoFileClip(v_path).duration)
            except: d_dur = 600
            
            # Key slider harus unik biar gak konflik
            m_start, m_end = st.slider(f"Geser Waktu #{i+1}", 0, d_dur, (int(moment['start']), int(moment['end'])), key=f"sl_{i}")
        
        with col2:
            if st.button(f"✨ RENDER SUBTITLE #{i+1}", key=f"bt_{i}"):
                out_file = f"final_{i}_{int(time.time())}.mp4"
                
                with st.spinner("🎨 Burning Subtitles (Agak lama dikit ya)..."):
                    success, err = process_clip_with_subs(v_path, vtt_path, m_start, m_end, out_file)
                    
                    if success:
                        st.success("✅ Jadi Bos!")
                        try:
                            with open(out_file, "rb") as f:
                                video_bytes = f.read()
                            st.video(video_bytes)
                            st.download_button("⬇️ DOWNLOAD + SUBS", video_bytes, file_name=f"Shorts_{i+1}_Subbed.mp4", mime="video/mp4")
                            os.remove(out_file)
                        except: pass
                    else:
                        st.error(f"Gagal Render: {err}")
                        st.warning("Tips: Pastikan file 'packages.txt' berisi 'imagemagick' sudah dibuat di GitHub.")

    if st.button("🗑️ Reset Project"):
        st.session_state.data = {}
        st.rerun()

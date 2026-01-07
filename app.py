import streamlit as st
import yt_dlp
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip
from groq import Groq
import os
import time
import json
import re
import glob
import webvtt
from datetime import timedelta
import PIL.Image
from PIL import ImageDraw, ImageFont # Kita pakai "Pensil" Python sendiri
import numpy as np

# --- 🛠️ FIX BUG MOVIEPY ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# --- SETUP HALAMAN ---
st.set_page_config(page_title="AI Clipper (Final Fix)", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    h1 { color: #00E676; text-align: center; text-shadow: 0 0 10px #00E676; }
    .stButton>button { width: 100%; background-color: #00E676; color: black; font-weight: bold; border-radius: 8px; }
    .clip-box { background-color: #1E1E1E; padding: 20px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #333; }
    .highlight { color: #00E676; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ AI CLIPPER (BYPASS SECURITY)")
st.caption("Solusi Final: Menggunakan Pillow (Python) untuk subtitle agar tidak diblokir server.")

# --- KONFIGURASI ---
api_key = "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" 

if 'data' not in st.session_state:
    st.session_state.data = {}

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    st.success("✅ API Ready")
    uploaded_cookie = st.file_uploader("Upload Cookies (Wajib)", type=["txt"])

# --- FUNGSI 1: SEDOT SUBTITLE ---
def get_transcript_with_timestamps(url, cookie_path=None):
    for f in glob.glob("temp_subs.*"): 
        try: os.remove(f)
        except: pass

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
        
        vtt_files = glob.glob("temp_subs.*.vtt")
        if not vtt_files: return None, None
        
        vtt_path = vtt_files[0]
        
        transcript_for_ai = ""
        captions = webvtt.read(vtt_path)
        chunk_start = 0
        current_chunk = []
        
        for caption in captions:
            start_seconds = caption.start_in_seconds
            text = caption.text.replace('\n', ' ').strip()
            if start_seconds - chunk_start < 15:
                current_chunk.append(text)
            else:
                time_label = f"[{int(chunk_start)}s - {int(start_seconds)}s]"
                full_text = " ".join(current_chunk)
                if full_text: transcript_for_ai += f"{time_label} {full_text}\n"
                chunk_start = start_seconds
                current_chunk = [text]
        return transcript_for_ai, vtt_path

    except Exception as e:
        print(f"Error VTT: {e}")
        return None, None

# --- FUNGSI 2: ANALISA AI ---
def analyze_virality(transcript_text, api_key):
    client = Groq(api_key=api_key)
    truncated_text = transcript_text[:30000]
    
    prompt = """
    Kamu adalah Video Editor.
    ATURAN WAJIB:
    1. GUNAKAN TIMESTAMP DARI TEKS.
    2. DURASI KLIP HARUS 60 - 90 DETIK. Jangan kurang!
    
    Output JSON MURNI:
    [
        {"start": 60, "end": 140, "title": "Judul", "reason": "Alasan"}
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
        return [{"start": 0, "end": 60, "title": "⚠️ Mode Manual", "reason": "AI Error"}]

# --- FUNGSI 3: DOWNLOAD VIDEO ---
def download_video(url, cookie_path=None):
    if not os.path.exists("downloads"): os.makedirs("downloads")
    ydl_opts = {
        'format': 'best[height<=720][ext=mp4]', 
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
    }
    if cookie_path: ydl_opts['cookiefile'] = cookie_path
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info['title']

# --- FUNGSI 4: GENERATOR SUBTITLE MANUAL (BYPASS IMAGEMAGICK) ---
def pil_text_generator(txt):
    # 1. Settingan Canvas
    width = 720  # Lebar video 720p
    height = 120 # Tinggi area subtitle
    font_size = 45
    
    # Buat gambar transparan
    img = PIL.Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 2. Cari Font Linux
    try:
        # Lokasi standar font di server Linux Debian/Ubuntu
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        # Fallback kalau gak nemu (pasti jelek tapi jalan)
        font = ImageFont.load_default()

    # 3. Hitung posisi tengah (Center Text)
    # Karena PIL agak 'manual', kita pakai bbox buat ngukur teks
    left, top, right, bottom = draw.textbbox((0, 0), txt, font=font)
    text_w = right - left
    text_h = bottom - top
    x_pos = (width - text_w) / 2
    y_pos = (height - text_h) / 2

    # 4. Gambar Stroke (Garis Tepi Hitam) - Trik Manual
    stroke_width = 3
    stroke_color = "black"
    # Gambar teks hitam digeser-geser dikit buat efek stroke
    for adj in range(-stroke_width, stroke_width+1):
        for adj2 in range(-stroke_width, stroke_width+1):
             draw.text((x_pos+adj, y_pos+adj2), txt, font=font, fill=stroke_color)

    # 5. Gambar Teks Utama (Kuning)
    draw.text((x_pos, y_pos), txt, font=font, fill="#FFEB3B") # Warna Kuning Mantap

    # 6. Convert jadi MoviePy ImageClip
    numpy_img = np.array(img)
    return ImageClip(numpy_img)

# --- FUNGSI 5: PROCESS VIDEO ---
def process_clip_with_subs(video_path, vtt_path, start, end, output_name):
    try:
        clip = VideoFileClip(video_path)
        if end > clip.duration: end = clip.duration
        
        subclip = clip.subclip(start, end)
        w, h = subclip.size
        
        # Center Crop 9:16
        target_ratio = 9/16
        new_w = h * target_ratio
        if new_w <= w:
            x_center = w / 2
            subclip = subclip.crop(x1=x_center - new_w/2, y1=0, width=new_w, height=h)
        subclip = subclip.resize(newsize=(720, 1280))
        
        # Bikin Subtitle
        captions = webvtt.read(vtt_path)
        subs_data = []
        
        for c in captions:
            if (c.start_in_seconds >= start) and (c.start_in_seconds < end):
                local_start = max(0, c.start_in_seconds - start)
                local_end = min(end - start, c.end_in_seconds - start)
                if local_end > local_start:
                    subs_data.append(((local_start, local_end), c.text.replace('\n', ' ')))
        
        # Burn Subtitle (PAKAI GENERATOR PIL BARU)
        if subs_data:
            try:
                # Panggil fungsi manual kita tadi
                subtitles = SubtitlesClip(subs_data, pil_text_generator)
                subtitles = subtitles.set_position(('center', 1050))
                final_clip = CompositeVideoClip([subclip, subtitles])
                msg = "Subtitle Aman (Mode Bypass)!"
            except Exception as e:
                msg = f"Tanpa Subtitle (Error: {e})"
                final_clip = subclip
        else:
            msg = "Tidak ada percakapan."
            final_clip = subclip

        final_clip.write_videofile(output_name, codec='libx264', audio_codec='aac', preset='ultrafast', logger=None)
        return True, msg

    except Exception as e:
        return False, str(e)

# --- UI UTAMA ---
url = st.text_input("🔗 Link YouTube:", placeholder="https://youtube.com/watch?v=...")

if st.button("🚀 SCAN VIDEO"):
    if not url:
        st.error("⚠️ Link kosong!")
    else:
        cookie_path = "temp_cookies.txt" if uploaded_cookie else None
        if uploaded_cookie:
            with open(cookie_path, "wb") as f: f.write(uploaded_cookie.getbuffer())

        with st.status("🕵️ Mencari Topik...", expanded=True) as status:
            status.write("📑 Download Subtitle...")
            transcript_text, vtt_path = get_transcript_with_timestamps(url, cookie_path)
            
            if not transcript_text:
                status.error("❌ Gagal. Video tidak punya CC.")
                st.stop()
            
            st.session_state.data['vtt_path'] = vtt_path
            
            status.write("🧠 AI Mencari Momen Viral (60s+)...")
            st.session_state.data['moments'] = analyze_virality(transcript_text, api_key)
            
            status.write("⬇️ Download Video...")
            try:
                v_path, v_title = download_video(url, cookie_path)
                st.session_state.data['video_path'] = v_path
                st.session_state.data['title'] = v_title
            except Exception as e:
                status.error(f"❌ Error Download: {e}")
                st.stop()
                
            status.update(label="✅ SIAP EDIT!", state="complete", expanded=False)

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
                <p>⏱️ <b>{moment['start']}s - {moment['end']}s</b> (Durasi: {moment['end'] - moment['start']}s)</p>
            </div>
            """, unsafe_allow_html=True)
            
            try: d_dur = int(VideoFileClip(v_path).duration)
            except: d_dur = 600
            m_start, m_end = st.slider(f"Geser Waktu #{i+1}", 0, d_dur, (int(moment['start']), int(moment['end'])), key=f"sl_{i}")
        
        with col2:
            if st.button(f"✨ RENDER #{i+1}", key=f"bt_{i}"):
                out_file = f"final_{i}_{int(time.time())}.mp4"
                
                with st.spinner("🎨 Burning Subtitles (Manual Mode)..."):
                    success, msg = process_clip_with_subs(v_path, vtt_path, m_start, m_end, out_file)
                    
                    if success:
                        st.success(f"✅ {msg}")
                        try:
                            with open(out_file, "rb") as f:
                                video_bytes = f.read()
                            st.video(video_bytes)
                            st.download_button("⬇️ DOWNLOAD", video_bytes, file_name=f"Shorts_{i+1}.mp4", mime="video/mp4")
                            os.remove(out_file)
                        except: pass
                    else:
                        st.error(f"Gagal: {msg}")

    if st.button("🗑️ Reset Project"):
        st.session_state.data = {}
        st.rerun()

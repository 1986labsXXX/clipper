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
from PIL import ImageDraw, ImageFont
import numpy as np

# --- 🛠️ FIX BUG MOVIEPY ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# --- SETUP HALAMAN ---
st.set_page_config(page_title="AI Clipper V4 (Mixtral Stabil)", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    h1 { color: #00E5FF; text-align: center; text-shadow: 0 0 10px #00E5FF; }
    .stButton>button { width: 100%; background-color: #00E5FF; color: black; font-weight: bold; border-radius: 8px; }
    .clip-box { background-color: #1E1E1E; padding: 20px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #333; }
    .highlight { color: #00E5FF; font-weight: bold; }
    .error-box { background-color: #B00020; color: white; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ AI CLIPPER V4 (STABIL)")
st.caption("Otak Baru (Mixtral) + Deteksi Error Lengkap")

# --- KONFIGURASI ---
api_key = "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" 

if 'data' not in st.session_state:
    st.session_state.data = {}
if 'debug_msg' not in st.session_state:
    st.session_state.debug_msg = ""

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
        
        # Chunk 30s
        for caption in captions:
            start_seconds = caption.start_in_seconds
            text = caption.text.replace('\n', ' ').strip()
            if start_seconds - chunk_start < 30: 
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

# --- FUNGSI 2: ANALISA AI (MIXTRAL + ROBUST PARSER) ---
def analyze_virality(transcript_text, api_key):
    client = Groq(api_key=api_key)
    # Potong teks max 25k char biar aman di Mixtral
    truncated_text = transcript_text[:25000] 
    
    prompt = """
    Kamu adalah Video Editor Profesional.
    Tugas: Temukan 4 (EMPAT) momen paling menarik dari transkrip video ini untuk dijadikan YouTube Shorts.
    
    INSTRUKSI TEKNIS:
    1. Output HARUS format JSON murni. Jangan ada teks pembuka/penutup.
    2. Gunakan timestamp yang ada di transkrip.
    3. Durasi tiap klip idealnya 60-90 detik.
    
    Contoh Output:
    [
        {"start": 60, "end": 120, "title": "Topik A", "reason": "Lucu"},
        {"start": 200, "end": 290, "title": "Topik B", "reason": "Seru"}
    ]

    TRANSKRIP:
    """ + truncated_text
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            # GANTI MODEL KE MIXTRAL (Lebih patuh JSON)
            model="mixtral-8x7b-32768",
            temperature=0.2 # Rendah biar konsisten
        )
        content = completion.choices[0].message.content
        
        # Debugging: Simpan raw content kalau error
        st.session_state.last_raw_ai = content
        
        # Regex Cleaner
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            clean_json = match.group(0)
            return json.loads(clean_json)
        else:
            raise ValueError(f"Format JSON tidak ditemukan. Output AI: {content[:100]}...")
            
    except Exception as e:
        # Kirim pesan error asli ke UI
        error_detail = str(e)
        return [{"start": 0, "end": 60, "title": "⚠️ ERROR AI", "reason": f"Detail: {error_detail}"}]

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

# --- FUNGSI 4: GENERATOR SUBTITLE (AUTO-WRAP) ---
def pil_text_generator_wrapped(txt):
    video_width = 720
    font_size = 42
    max_text_width = video_width * 0.90 
    stroke_width = 3
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
        
    lines = []
    words = txt.split(' ')
    current_line = words[0]
    for word in words[1:]:
        test_line = current_line + " " + word
        bbox = font.getbbox(test_line) 
        w = bbox[2] - bbox[0]
        if w <= max_text_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line) 
    
    line_bbox = font.getbbox("Ay")
    line_height = (line_bbox[3] - line_bbox[1]) * 1.2 
    total_height = int(len(lines) * line_height) + 20 
    
    img = PIL.Image.new('RGBA', (video_width, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    y_text = 10
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x_text = (video_width - text_w) / 2
        
        for adj_x in range(-stroke_width, stroke_width+1):
            for adj_y in range(-stroke_width, stroke_width+1):
                 draw.text((x_text+adj_x, y_text+adj_y), line, font=font, fill="black")
        
        draw.text((x_text, y_text), line, font=font, fill="#FFD700") # Emas
        y_text += line_height
        
    return ImageClip(np.array(img))

# --- FUNGSI 5: PROCESS VIDEO ---
def process_clip_with_subs(video_path, vtt_path, start, end, output_name):
    try:
        clip = VideoFileClip(video_path)
        if end > clip.duration: end = clip.duration
        
        subclip = clip.subclip(start, end)
        w, h = subclip.size
        
        target_ratio = 9/16
        new_w = h * target_ratio
        if new_w <= w:
            x_center = w / 2
            subclip = subclip.crop(x1=x_center - new_w/2, y1=0, width=new_w, height=h)
        subclip = subclip.resize(newsize=(720, 1280))
        
        captions = webvtt.read(vtt_path)
        subs_data = []
        for c in captions:
            if (c.start_in_seconds >= start) and (c.start_in_seconds < end):
                local_start = max(0, c.start_in_seconds - start)
                local_end = min(end - start, c.end_in_seconds - start)
                if local_end > local_start:
                    clean_text = re.sub(r'<[^>]+>', '', c.text.replace('\n', ' ')).strip()
                    subs_data.append(((local_start, local_end), clean_text))
        
        if subs_data:
            try:
                subtitles = SubtitlesClip(subs_data, pil_text_generator_wrapped)
                subtitles = subtitles.set_position(('center', 900)) 
                final_clip = CompositeVideoClip([subclip, subtitles])
                msg = "Subtitle Aman!"
            except Exception as e:
                msg = f"Error Subs: {e}"
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

if st.button("🚀 SCAN (MODE MIXTRAL)"):
    if not url:
        st.error("⚠️ Link kosong!")
    else:
        cookie_path = "temp_cookies.txt" if uploaded_cookie else None
        if uploaded_cookie:
            with open(cookie_path, "wb") as f: f.write(uploaded_cookie.getbuffer())

        with st.status("🕵️ Menjalankan Analisa...", expanded=True) as status:
            status.write("📑 Download Subtitle...")
            transcript_text, vtt_path = get_transcript_with_timestamps(url, cookie_path)
            
            if not transcript_text:
                status.error("❌ Gagal. Video tidak punya CC/Transkrip.")
                st.stop()
            
            st.session_state.data['vtt_path'] = vtt_path
            
            status.write("🧠 AI (Mixtral) Berpikir...")
            st.session_state.data['moments'] = analyze_virality(transcript_text, api_key)
            
            status.write("⬇️ Download Video...")
            try:
                v_path, v_title = download_video(url, cookie_path)
                st.session_state.data['video_path'] = v_path
                st.session_state.data['title'] = v_title
            except Exception as e:
                status.error(f"❌ Error Download: {e}")
                st.stop()
                
            status.update(label="✅ Selesai!", state="complete", expanded=False)

if 'moments' in st.session_state.data:
    st.markdown("---")
    st.subheader(f"🎬 {st.session_state.data.get('title', 'Video')}")
    
    moments = st.session_state.data['moments']
    v_path = st.session_state.data['video_path']
    vtt_path = st.session_state.data.get('vtt_path')
    
    # CEK ERROR DARI AI
    if len(moments) == 1 and "ERROR AI" in moments[0]['title']:
        st.markdown(f"""
        <div class='error-box'>
            <h3>⚠️ AI GAGAL</h3>
            <p>{moments[0]['reason']}</p>
            <p>Saran: Coba video lain yang durasinya lebih pendek, atau coba refresh halaman.</p>
        </div>
        """, unsafe_allow_html=True)

    for i, moment in enumerate(moments):
        col1, col2 = st.columns([3, 1])
        with col1:
            durasi = int(moment['end']) - int(moment['start'])
            st.markdown(f"""
            <div class='clip-box'>
                <h4 class='highlight'>#{i+1} {moment['title']}</h4>
                <p>{moment['reason']}</p>
                <p>⏱️ <b>{moment['start']}s - {moment['end']}s</b> ({durasi}s)</p>
            </div>
            """, unsafe_allow_html=True)
            
            try: d_dur = int(VideoFileClip(v_path).duration)
            except: d_dur = 600
            m_start, m_end = st.slider(f"Geser Waktu #{i+1}", 0, d_dur, (int(moment['start']), int(moment['end'])), key=f"sl_{i}")
        
        with col2:
            if st.button(f"✨ RENDER #{i+1}", key=f"bt_{i}"):
                out_file = f"final_{i}_{int(time.time())}.mp4"
                
                with st.spinner("🎨 Rendering..."):
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

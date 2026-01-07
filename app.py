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
import PIL.Image
from PIL import ImageDraw, ImageFont
import numpy as np

# --- 🛠️ FIX BUG MOVIEPY ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# --- SETUP HALAMAN ---
st.set_page_config(page_title="AI Clipper V9 (Fix Model)", page_icon="🚀", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    h1 { color: #00B0FF; text-align: center; text-shadow: 0 0 10px #00B0FF; }
    .stButton>button { width: 100%; background-color: #00B0FF; color: white; font-weight: bold; border-radius: 8px; }
    .clip-box { background-color: #1E1E1E; padding: 20px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #333; }
    .error-box { background-color: #CF6679; color: black; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    .highlight { color: #00B0FF; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🚀 AI CLIPPER V9 (Llama 3.1 Instant)")
st.caption("Fix Error: Menggunakan Model Terbaru 'Llama-3.1-8b-Instant'. Subtitle Pop-up Aktif.")

# --- KONFIGURASI ---
DEFAULT_API_KEY = "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" 

if 'data' not in st.session_state:
    st.session_state.data = {}

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Konfigurasi")
    st.subheader("🔑 API Key")
    custom_key = st.text_input("Paste Key Baru (Jika Limit Habis)", type="password")
    
    if custom_key:
        active_key = custom_key
        st.success("✅ Key Custom Aktif")
    else:
        active_key = DEFAULT_API_KEY
        st.info("ℹ️ Key Default Aktif")
        
    st.markdown("---")
    st.subheader("🍪 Cookies")
    uploaded_cookie = st.file_uploader("Upload 'cookies.txt'", type=["txt"])

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

# --- FUNGSI 2: ANALISA AI (MODEL BARU 3.1) ---
def analyze_virality(transcript_text, api_key):
    client = Groq(api_key=api_key)
    # Potong teks 15rb karakter (Hemat Kuota)
    truncated_text = transcript_text[:15000] 
    
    prompt = """
    Kamu adalah Video Editor.
    Analisa transkrip dan cari 4 bagian paling viral/menarik.
    
    ATURAN:
    1. Output JSON Object dengan key "clips".
    2. Format: {"start": angka, "end": angka, "title": "teks", "reason": "teks"}.
    3. Gunakan timestamp asli.
    4. Durasi: 60 - 90 detik.
    
    TRANSKRIP:
    """ + truncated_text
    
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            # MODEL BARU YANG AKTIF & CEPAT
            model="llama-3.1-8b-instant", 
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        data = json.loads(content)
        
        if "clips" in data: return data["clips"]
        elif isinstance(data, list): return data
        else:
            for key, val in data.items():
                if isinstance(val, list): return val
            return []
            
    except Exception as e:
        return [{"start": 0, "end": 60, "title": "⚠️ ERROR AI", "reason": str(e)}]

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

# --- FUNGSI 4: GENERATOR TEKS POP-UP (BESAR & TENGAH) ---
def pil_word_generator(txt):
    video_width = 720
    canvas_height = 200 
    font_size = 70 
    stroke_width = 6
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()

    img = PIL.Image.new('RGBA', (video_width, canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    bbox = draw.textbbox((0, 0), txt, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x_pos = (video_width - text_w) / 2
    y_pos = (canvas_height - text_h) / 2
    
    for adj_x in range(-stroke_width, stroke_width+1):
        for adj_y in range(-stroke_width, stroke_width+1):
             draw.text((x_pos+adj_x, y_pos+adj_y), txt, font=font, fill="black")
    
    draw.text((x_pos, y_pos), txt, font=font, fill="#FFEB3B") # Warna Kuning
    
    return ImageClip(np.array(img))

# --- FUNGSI 5: PROCESS VIDEO (WORD BY WORD) ---
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
        word_subs_data = []
        
        for c in captions:
            if (c.end_in_seconds > start) and (c.start_in_seconds < end):
                full_text = re.sub(r'<[^>]+>', '', c.text.replace('\n', ' ')).strip()
                words = full_text.split()
                
                if not words: continue
                
                caption_duration = c.end_in_seconds - c.start_in_seconds
                time_per_word = caption_duration / len(words)
                
                current_word_start = c.start_in_seconds
                
                for word in words:
                    word_start = max(0, current_word_start - start)
                    word_end = min(end - start, (current_word_start + time_per_word) - start)
                    
                    if word_end > word_start:
                        word_subs_data.append(((word_start, word_end), word.upper()))
                    
                    current_word_start += time_per_word

        if word_subs_data:
            try:
                subtitles = SubtitlesClip(word_subs_data, pil_word_generator)
                subtitles = subtitles.set_position(('center', 'center')) 
                final_clip = CompositeVideoClip([subclip, subtitles])
                msg = "Subtitle Pop-up Siap!"
            except Exception as e:
                msg = f"Error Subs: {e}"
                final_clip = subclip
        else:
            msg = "Tidak ada percakapan terdeteksi."
            final_clip = subclip

        final_clip.write_videofile(output_name, codec='libx264', audio_codec='aac', preset='ultrafast', logger=None)
        return True, msg

    except Exception as e:
        return False, str(e)

# --- UI UTAMA ---
url = st.text_input("🔗 Link YouTube:", placeholder="https://youtube.com/watch?v=...")

if st.button("🚀 SCAN (MODE LLAMA 3.1)"):
    if not url:
        st.error("⚠️ Link kosong!")
    else:
        cookie_path = "temp_cookies.txt" if uploaded_cookie else None
        if uploaded_cookie:
            with open(cookie_path, "wb") as f: f.write(uploaded_cookie.getbuffer())

        with st.status("🕵️ Memproses (Model Baru)...", expanded=True) as status:
            status.write("📑 Download Subtitle...")
            transcript_text, vtt_path = get_transcript_with_timestamps(url, cookie_path)
            
            if not transcript_text:
                status.error("❌ Gagal. Video tidak punya CC.")
                st.stop()
            
            st.session_state.data['vtt_path'] = vtt_path
            
            status.write(f"🧠 AI Menganalisa (Key: {active_key[:5]}***)...")
            st.session_state.data['moments'] = analyze_virality(transcript_text, active_key)
            
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
    
    if len(moments) == 1 and "ERROR" in moments[0]['title']:
         st.markdown(f"""
        <div class='error-box'>
            <h3>🚨 ERROR AI: {moments[0]['reason']}</h3>
            <p>Tips: Gunakan API Key baru jika kena limit, atau coba video lain.</p>
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
                
                with st.spinner("💥 Rendering Pop-up Text..."):
                    success, msg = process_clip_with_subs(v_path, vtt_path, m_start, m_end, out_file)
                    
                    if success:
                        st.success(f"✅ {msg}")
                        try:
                            with open(out_file, "rb") as f:
                                video_bytes = f.read()
                            st.video(video_bytes)
                            st.download_button("⬇️ DOWNLOAD", video_bytes, file_name=f"PopUp_{i+1}.mp4", mime="video/mp4")
                            os.remove(out_file)
                        except: pass
                    else:
                        st.error(f"Gagal: {msg}")

    if st.button("🗑️ Reset Project"):
        st.session_state.data = {}
        st.rerun()

print("[INFO] Flask app starting...")

from flask import Flask, render_template, request
import os
import time
import hmac
import hashlib
import base64
import requests
import yt_dlp

app = Flask(__name__)
UPLOAD_FOLDER = "temp_audio"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- ACRCloud credentials ---
ACR_HOST = "identify-ap-southeast-1.acrcloud.com"
ACR_ACCESS_KEY = "f9e3a3cd1d9bc13227bb1954be662c0b"
ACR_ACCESS_SECRET = "G4vvE2hPyn8AvbhpAUgZu85k7j4bK8bX6Mcn0uoI"

# --- Path to ffmpeg/ffprobe ---
FFMPEG_DIR = r"C:\Users\Chanchal\OneDrive\Desktop\ohio\bin"

# Ensure Windows can find ffmpeg and ffprobe
os.environ["PATH"] += os.pathsep + FFMPEG_DIR

def download_audio_from_youtube(youtube_url):
    print(f"[DEBUG] Downloading first 15s of audio from: {youtube_url}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{UPLOAD_FOLDER}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'download_sections': {'*': {'start_time': 0, 'end_time': 15}},  # only 15 seconds
        'ffmpeg_location': FFMPEG_DIR
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        audio_file = ydl.prepare_filename(info)
        audio_file = os.path.splitext(audio_file)[0] + ".wav"
    print(f"[DEBUG] Trimmed audio downloaded: {audio_file}")
    return audio_file

def recognize_song(file_path):
    print(f"[DEBUG] Sending audio to ACRCloud: {file_path}")
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))

    string_to_sign = "\n".join([http_method, http_uri, ACR_ACCESS_KEY, data_type, signature_version, timestamp])
    sign = base64.b64encode(
        hmac.new(
            ACR_ACCESS_SECRET.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha1
        ).digest()
    ).decode('utf-8')

    with open(file_path, 'rb') as f:
        files = {'sample': f}
        data = {
            'access_key': ACR_ACCESS_KEY,
            'data_type': data_type,
            'signature_version': signature_version,
            'signature': sign,
            'timestamp': timestamp
        }
        response = requests.post(f"https://{ACR_HOST}/v1/identify", files=files, data=data)
    print(f"[DEBUG] ACRCloud response status: {response.status_code}")
    return response.json()

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    if request.method == "POST":
        yt_link = request.form.get("youtube_link")
        print(f"[DEBUG] Received YouTube link: {yt_link}")
        if yt_link:
            try:
                audio_file = download_audio_from_youtube(yt_link)
                song_info = recognize_song(audio_file)
                os.remove(audio_file)
                print(f"[DEBUG] Song info received: {song_info}")

                if song_info.get("status", {}).get("msg") == "Success":
                    music_list = song_info.get("metadata", {}).get("music", [])
                    if music_list:
                        title = music_list[0].get("title", "Unknown")
                        artist = music_list[0].get("artists", [{}])[0].get("name", "Unknown Artist")
                        result = f"{title} by {artist}"
                    else:
                        result = "Song not recognized."
                else:
                    result = f"Error: {song_info.get('status', {}).get('msg', 'Unknown error')}"
            except Exception as e:
                result = f"Error: {str(e)}"
                print(f"[ERROR] {str(e)}")
    return render_template("index.html", result=result)

if __name__ == "__main__":
    print("[INFO] Starting Flask app...")
    app.run(debug=True)

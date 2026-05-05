import os
import subprocess
import tempfile
import urllib.request
import base64
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

def upload_to_host(file_path, filename):
    """Upload file to 0x0.st (free, no auth, up to 512MB)."""
    with open(file_path, 'rb') as f:
        r = requests.post('https://0x0.st', files={'file': (filename, f, 'video/mp4')}, timeout=120)
    r.raise_for_status()
    return r.text.strip()

@app.route('/combine', methods=['POST'])
def combine():
    try:
        data = request.json
        audio_b64  = data.get('audio_b64')
        video_url  = data.get('video_url', '')
        filename   = data.get('filename', 'output.mp4')
        width      = int(data.get('width', 1280))
        height     = int(data.get('height', 720))

        with tempfile.TemporaryDirectory() as tmp:
            audio_path  = tmp + '/audio.mp3'
            video_path  = tmp + '/video.mp4'
            output_path = tmp + '/' + filename

            # Write audio from base64
            with open(audio_path, 'wb') as f:
                f.write(base64.b64decode(audio_b64))

            # Get audio duration
            dur = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                 '-of', 'csv=p=0', audio_path],
                capture_output=True, text=True
            )
            audio_dur = float(dur.stdout.strip() or '60')

            if video_url:
                # Download background video and loop to match audio
                urllib.request.urlretrieve(video_url, video_path)
                subprocess.run([
                    'ffmpeg',
                    '-stream_loop', '-1', '-i', video_path,
                    '-i', audio_path,
                    '-map', '0:v', '-map', '1:a',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-t', str(audio_dur),
                    '-y', output_path
                ], check=True, capture_output=True)
            else:
                # Generate dark horror-style animated background (noise + dark)
                noise_filter = (
                    f"color=0x050508:size={width}x{height}:rate=24,"
                    f"noise=alls=8:allf=t+u"
                )
                subprocess.run([
                    'ffmpeg',
                    '-f', 'lavfi', '-i', noise_filter,
                    '-i', audio_path,
                    '-map', '0:v', '-map', '1:a',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-t', str(audio_dur),
                    '-y', output_path
                ], check=True, capture_output=True)

            # Upload to free host
            public_url = upload_to_host(output_path, filename)
            return jsonify({'url': public_url, 'duration': audio_dur})

    except subprocess.CalledProcessError as e:
        return jsonify({'error': 'ffmpeg failed', 'stderr': e.stderr.decode()}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

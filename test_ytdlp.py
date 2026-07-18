import yt_dlp
import os

ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': False,
    'no_warnings': False,
}

cookies_file = os.path.join(os.path.dirname(__file__), 'cookies.txt')
if os.path.exists(cookies_file):
    ydl_opts['cookiefile'] = cookies_file
    print(f"Cookies file found at: {cookies_file}")
else:
    print("Cookies file NOT found!")

print("Running extraction...")
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info('https://www.youtube.com/watch?v=nwsewSMWIas', download=False)
        print("Success! Title:", info.get('title'))
except Exception as e:
    import traceback
    traceback.print_exc()

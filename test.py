import subprocess
import os

p = r'E:\PROJECT\Vibe code\C-Project\yt-short-clipper-2.0.5-beta\ffmpeg\ffmpeg'
print('Exists .exe:', os.path.exists(p + '.exe'))
try:
    subprocess.Popen([p, '-version'])
except Exception as e:
    print('Error:', type(e), e)

"""V8.6 local rendered-film inspector; file/stream-based, no external providers.

All metrics are heuristics about timing/frames/audio levels. The module DOES NOT
claim to assess face identity, Polish phonemes, acting or aesthetics.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

MAX_SIZE = 200 * 1024 * 1024
MAX_DURATION = 900.0


def _run(argv, timeout=45):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('FFmpeg/FFprobe jest niedostępny lub przekroczono czas analizy') from exc
    if done.returncode:
        raise ValueError('Nieprawidłowy plik multimedialny lub błąd FFmpeg')
    return done.stdout, done.stderr


def probe(path):
    src=Path(path)
    if not src.is_file() or src.stat().st_size<1024 or src.stat().st_size>MAX_SIZE:
        raise ValueError('MP4 musi mieć od 1 KB do 200 MB')
    with src.open('rb') as f:
        head=f.read(32)
    if head[4:8]!=b'ftyp':raise ValueError('Wymagany rzeczywisty kontener MP4')
    out,_=_run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(src)])
    info=json.loads(out)
    video=next((s for s in info.get('streams',[]) if s.get('codec_type')=='video'),None)
    audio=next((s for s in info.get('streams',[]) if s.get('codec_type')=='audio'),None)
    if not video:raise ValueError('Film nie ma ścieżki obrazu')
    try:seconds=float(info['format']['duration']);w=int(video['width']);h=int(video['height'])
    except (KeyError,TypeError,ValueError) as exc:raise ValueError('Brak długości lub wymiarów MP4') from exc
    if not math.isfinite(seconds) or not .3<=seconds<=MAX_DURATION or not 80<=w<=7680 or not 80<=h<=4320:
        raise ValueError('Długość lub wymiary poza bezpiecznym zakresem')
    rate=str(video.get('avg_frame_rate') or video.get('r_frame_rate') or '0/1').split('/')
    try:fps=float(rate[0])/float(rate[1])
    except (ValueError,ZeroDivisionError,IndexError):fps=0.
    return {'duration':round(seconds,3),'width':w,'height':h,'fps':round(fps,3),
            'video_codec':video.get('codec_name'),'audio_codec':audio.get('codec_name') if audio else None,
            'color_primaries':video.get('color_primaries','unknown'),
            'color_transfer':video.get('color_transfer','unknown'),
            'audio_present':bool(audio), 'bytes':src.stat().st_size}


def sample_motion(path, seconds, sample_fps=2):
    """Normalized frame-to-frame luma differences, not optical flow or acting assessment."""
    width,height=96,54;size=width*height
    maxframes=min(int(seconds*sample_fps)+3,2000)
    cmd=['ffmpeg','-v','error','-nostdin','-i',str(path),'-an',
         '-vf',f'fps={sample_fps},scale={width}:{height}:flags=fast_bilinear,format=gray',
         '-frames:v',str(maxframes),'-f','rawvideo','-pix_fmt','gray','pipe:1']
    try:
        p=subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=65)
    except (OSError,subprocess.TimeoutExpired) as exc:raise ValueError('Nie można pobrać próbek ruchu') from exc
    if p.returncode:raise ValueError('FFmpeg nie odczytał klatek')
    frames=[p.stdout[i:i+size] for i in range(0,len(p.stdout)-size+1,size)]
    scores=[]
    for a,b in zip(frames,frames[1:]):
        scores.append(sum(abs(x-y) for x,y in zip(a,b))/(size*255))
    # Conservative estimates of stillness; cut detection with simple histogram-level diff.
    still=[];start=None
    for i,val in enumerate(scores):
        static=val<0.008
        if static and start is None:start=i/sample_fps
        if not static and start is not None:
            if (i/sample_fps-start)>=1.5:still.append({'from':round(start,2),'to':round(i/sample_fps,2)})
            start=None
    if start is not None and len(scores)/sample_fps-start>=1.5:
        still.append({'from':round(start,2),'to':round(len(scores)/sample_fps,2)})
    static_percent=round(100*sum(s<0.008 for s in scores)/max(len(scores),1),1)
    cuts=[round((i+1)/sample_fps,2) for i,v in enumerate(scores) if v>0.22]
    return {'sample_rate_fps':sample_fps,'frames':len(frames),'static_percent':static_percent,
            'low_motion_intervals':still[:60], 'possible_hard_cuts':cuts[:100],
            'confidence':'heuristic_only','method':'luma frame difference at 96x54; camera and motion not separated'}


def audio_silence(path,seconds):
    cmd=['ffmpeg','-nostdin','-hide_banner','-i',str(path),'-vn','-af','silencedetect=noise=-35dB:d=0.5',
         '-t',str(min(seconds,MAX_DURATION)),'-f','null','-']
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired):return []
    raw=p.stderr
    starts=[];results=[]
    for line in raw.splitlines():
        m=re.search(r'silence_start: (\d+(?:\.\d+)?)',line)
        if m:starts.append(float(m.group(1)))
        m=re.search(r'silence_end: (\d+(?:\.\d+)?)',line)
        if m and starts:
            v=starts.pop(0);results.append({'from':round(v,2),'to':round(float(m.group(1)),2)})
    for v in starts:results.append({'from':round(v,2),'to':round(seconds,2)})
    return results[:60]


def inspect(path,planned_duration=None):
    m=probe(path); duration=m['duration']; warnings=[]
    motion=sample_motion(path,duration)
    silences=audio_silence(path,duration) if m['audio_present'] else []
    if planned_duration is not None:
        try:
            diff=abs(duration-float(planned_duration))
            if diff>0.5:warnings.append({'type':'duration','severity':'warning','message':f'Gotowy MP4 różni się od planu o {diff:.2f} s'})
        except (TypeError,ValueError):pass
    if not m['audio_present']:warnings.append({'type':'audio','severity':'warning','message':'Brak ścieżki dźwiękowej'})
    elif any(e['to']>=duration-.15 and e['to']-e['from']>.8 for e in silences):
        warnings.append({'type':'ending_silence','severity':'warning','message':'Końcówka ma ponad 0,8 s ciszy: sprawdź finał muzyczny'})
    if m['color_primaries']!='bt709':
        warnings.append({'type':'color','severity':'info','message':'Nie potwierdzono metadanych koloru BT.709 (color_primaries='+str(m['color_primaries'])+'). Zweryfikuj eksport.'})
    if duration<=35:
        for r in motion['low_motion_intervals']:
            if r['to']-r['from']>2.1:
                warnings.append({'type':'still','severity':'info','interval':r,
                    'message':'Długie niemal nieruchome ujęcie; sprawdź czy ma cel dramaturgiczny'})
    if m['width']/m['height']>0.9:
        warnings.append({'type':'aspect','severity':'info','message':'Wideo nie wygląda na pionowe 9:16'})
    return {'version':'8.6.0','media':m,'motion':motion,'silence_intervals':silences,
            'warnings':warnings,'not_verified':['zgodność twarzy i ubioru z Golden Master',
             'naturalność polskiej mowy','synchronizacja fonemów i ust',
             'czytelność prawdziwej interakcji UI','jakość aktorska i komediowa'],
            'external_requests':0,'review_required':True}


def movie_file(root,project_id):
    if not re.fullmatch(r'[0-9a-f-]{36}',str(project_id)):
        raise ValueError('Nieprawidłowy ID projektu')
    return Path(root)/'data'/'v86_films'/project_id/'source.mp4'

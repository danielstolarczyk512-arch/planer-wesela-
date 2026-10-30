"""Local frame-change diagnostics. Not a substitute for watching the movie.

Uses only ffmpeg/ffprobe; pixel changes are never called cinematographic quality.
"""
import subprocess
from pathlib import Path

WIDTH=96
HEIGHT=160

def inspect_motion(path, fps=2, limit_seconds=45):
    f=Path(path)
    if not f.is_file():raise ValueError('Brak rzeczywistego pliku MP4')
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration',
        '-of','default=noprint_wrappers=1:nokey=1',str(f)],capture_output=True,text=True,timeout=15)
    if probe.returncode:raise ValueError('FFprobe nie potrafi odczytać pliku')
    try:duration=float(probe.stdout.strip())
    except ValueError:raise ValueError('Nieznana długość wideo') from None
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-i',str(f),'-t',str(min(duration,limit_seconds)),
        '-vf',f'fps={fps},scale={WIDTH}:{HEIGHT},format=gray','-f','rawvideo','-pix_fmt','gray','pipe:1']
    try:p=subprocess.run(cmd,capture_output=True,timeout=60)
    except (FileNotFoundError,subprocess.TimeoutExpired):raise ValueError('FFmpeg niedostępny lub analiza przekroczyła czas') from None
    if p.returncode:raise ValueError('Nie udało się odczytać klatek filmu')
    size=WIDTH*HEIGHT
    frames=[p.stdout[i:i+size] for i in range(0,len(p.stdout)-size+1,size)]
    if len(frames)<2:raise ValueError('Za mało klatek do pomiaru')
    changes=[];low_contrast=0
    for frame in frames:
        if max(frame)-min(frame)<15:low_contrast+=1
    for before,after in zip(frames,frames[1:]):
        changes.append(sum(abs(a-b) for a,b in zip(before,after))/size)
    ratio=sum(v<1.25 for v in changes)/len(changes)
    return {'source_seconds':round(duration,2),'analyzed_seconds':round(min(duration,limit_seconds),2),
      'frame_sample_hz':fps,'sampled_frames':len(frames),'mean_frame_change':round(sum(changes)/len(changes),3),
      'almost_identical_frame_pairs_fraction':round(ratio,3),
      'flat_colored_frame_fraction':round(low_contrast/len(frames),3),
      'issues':(['Mało zmian w obrazie — obejrzyj czy ujęcie nie jest mozolne lub statyczne'] if ratio>.6 else [])+
               (['Wiele klatek prawie jednolitych kolorystycznie — sprawdź UI i plansze'] if low_contrast/len(frames)>.6 else []),
      'notes':'To wyłącznie pomiar różnic pikseli. Nie rozpoznaje naturalnej gry aktorskiej, poprawnej kompozycji ani synchronizacji ust.',
      'human_review_required':True}

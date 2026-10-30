"""Optional local **heuristic** V6 frame inspection, no external service.
No face recognition or AI anatomy validation is claimed.
Requires Pillow only when available; otherwise gracefully skips.
"""
from __future__ import annotations

import io
import shutil
import subprocess


def _sample_frame(path,second):
    if not shutil.which('ffmpeg'):return None
    try:
        from PIL import Image
    except ImportError:return None
    cmd=['ffmpeg','-v','error','-ss',str(max(0,second)),'-i',str(path),'-frames:v','1',
         '-vf','scale=320:560','-f','image2pipe','-vcodec','png','pipe:1']
    try:
        proc=subprocess.run(cmd,capture_output=True,timeout=20)
        if proc.returncode or not proc.stdout:return None
        im=Image.open(io.BytesIO(proc.stdout));im.load();return im.convert('RGB')
    except (OSError,subprocess.TimeoutExpired,ValueError):return None


def _avgdiff(a,b):
    from PIL import ImageChops, ImageStat
    return sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/3


def audit(path,duration):
    """Detect only *very likely* repeated top/bottom and near-frozen sources.
    Never auto-reject; false positives possible in stylized animation.
    """
    images=[_sample_frame(path,s) for s in (min(0.5,duration/5),min(duration*0.5,10),max(0,duration-0.6))]
    images=[i for i in images if i is not None]
    if len(images)<2:return {'performed':False,'warnings':[],'note':'Brak ffmpeg/Pillow lub klatek'}
    findings=[]
    for frame in images:
        w,h=frame.size
        a=frame.crop((0,0,w,h//2)).resize((160,140))
        b=frame.crop((0,h//2,w,h)).resize((160,140))
        if _avgdiff(a,b)<4:
            findings.append('Kadr może zawierać powtórzone identyczne górne/dolne półobrazy — sprawdź ręcznie.')
            break
    if _avgdiff(images[0],images[-1])<1.8:
        findings.append('Klip ma bardzo mały ruch między początkiem a końcem; może przypominać statyczną planszę.')
    return {'performed':True,'warnings':findings,
            'note':'Heurystyka, bez AI rozpoznawania twarzy i bez pewnego wykrywania kolaży.'}

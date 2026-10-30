"""Local media inspector. Flags technical faults, never claims AI anatomy has been checked."""
import json
import shutil
import subprocess
from pathlib import Path


def probe(path):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError('Brak pliku nagrania')
    if not shutil.which('ffprobe'):raise RuntimeError('Brakuje bezpłatnego ffprobe')
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,format_name,size:stream=index,codec_type,codec_name,width,height,r_frame_rate',
        '-of','json',str(path)],capture_output=True,text=True,timeout=30)
    if p.returncode:raise ValueError('Uszkodzony lub nieobsługiwany plik wideo')
    data=json.loads(p.stdout);video=next((s for s in data.get('streams',[]) if s.get('codec_type')=='video'),None)
    if not video:raise ValueError('Brak strumienia wideo')
    duration=float(data.get('format',{}).get('duration') or 0)
    return {'seconds':duration,'width':video.get('width'),'height':video.get('height'),
            'codec':video.get('codec_name'),'audio_present':any(s.get('codec_type')=='audio' for s in data.get('streams',[])),
            'size_bytes':path.stat().st_size}


def inspect_shot(path,shot):
    info=probe(path);issues=[];warnings=[]
    needed=float(shot.get('in_point',0))+float(shot['duration'])
    if info['seconds']+0.08<needed:issues.append(f'Źródło jest za krótkie ({info["seconds"]:.2f}s vs {needed:.2f}s)')
    if info['width']<720 or info['height']<720:warnings.append('Źródło ma niską rozdzielczość; eksport 1080p nie doda szczegółów')
    if not info['audio_present']:warnings.append('Źródło nie ma audio; zostanie dodana cisza')
    if shot.get('mode')=='ui':warnings.append('Autentyczność UI wymaga ręcznego sprawdzenia źródła nagrania')
    if shot.get('mode')=='t2v':warnings.append('Anatomia, mimika i ciągłość wymagają oględzin człowieka')
    from qc.visual_v6 import audit as v6_audit
    visual=v6_audit(path,info['seconds'])
    warnings.extend(visual.get('warnings',[]))
    return {'metadata':info,'issues':issues,'warnings':warnings,'technical_pass':not issues,
            'visual_pass':None,'v6_heuristic':visual}


"""V8.5 editorial audio/subtitle timeline. Pure local operations; no API spending.

Dialogue WAVs are stored under data/v85_audio/<project-id>/<shot-id>.wav and
explicitly reviewed by a human. Original video sound is muted only when the
user opts in; dialogue then spans video cuts without destructive per-shot fades.
"""
from __future__ import annotations

import hashlib
import math
import re
import subprocess
import uuid
from pathlib import Path

SPEAKERS={'ONA', 'ON', 'WUJEK', 'LEKTOR', 'INNA'}
SID=re.compile(r'^S\d{2,6}$')
PID=re.compile(r'^[a-f0-9-]{36}$')

def digest(data):return hashlib.sha256(data).hexdigest()
def project_duration(p):return round(sum(float(s.get('duration') or 0) for s in p.get('shots',[])),3)
def safe_audio(root,project_id,shot_id):
    if not PID.fullmatch(project_id) or not SID.fullmatch(shot_id):raise ValueError('Niedozwolony identyfikator projektu lub ujęcia')
    return Path(root)/'data'/'v85_audio'/project_id/(shot_id+'.wav')

def probe_audio(file):
    r=subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries',
        'stream=codec_name,channels,sample_rate:format=duration','-of','json',str(file)],
        capture_output=True,text=True,timeout=30)
    if r.returncode:raise ValueError('Nie można odczytać nagrania audio')
    import json
    try:
        data=json.loads(r.stdout);stream=data['streams'][0]
        seconds=float(data['format']['duration'])
    except (KeyError,ValueError,IndexError) as exc:raise ValueError('Nieprawidłowy dźwięk') from exc
    if stream.get('codec_name')!='pcm_s16le':raise ValueError('Wymagany 16-bitowy PCM WAV')
    if not 0.10<=seconds<=60 or int(stream.get('channels',0)) not in (1,2):
        raise ValueError('Dźwięk: 0,1–60 s i mono/stereo')
    return round(seconds,3)

def add_audio(root,project,shot,contents,offset=0):
    if not isinstance(contents,bytes) or not 1024<=len(contents)<=25*1024*1024:
        raise ValueError('WAV musi mieć od 1 KB do 25 MB')
    if not -2<=float(offset)<=2 or not math.isfinite(float(offset)):
        raise ValueError('Przesunięcie audio poza zakresem -2 do +2 sekund')
    if not contents.startswith(b'RIFF') or contents[8:12]!=b'WAVE':raise ValueError('Wymagany prawdziwy WAV')
    dest=safe_audio(root,project['id'],shot['id']);dest.parent.mkdir(parents=True,exist_ok=True)
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(dir=dest.parent,suffix='.wav',delete=False) as f:
        f.write(contents);tmp=Path(f.name)
    try:
        seconds=probe_audio(tmp)
        if seconds>project_duration(project)+0.5:raise ValueError('Nagranie dłuższe od filmu')
        os.replace(tmp,dest)
    finally:tmp.unlink(missing_ok=True)
    # Voice changes make old lipsync and old MP4 invalid, not just the cue metadata.
    # Preserve the files as history, but never approve them for this new dialogue.
    shot['edit_version']=uuid.uuid4().hex
    shot['qc_approved']=False
    shot['v7_lips_approved']=False
    for stale in ('v82_frame_approval','v82_clip_approval','v7_voice','quote','workflow_id','media_url'):
        shot.pop(stale,None)
    info={'sha256':digest(contents),'seconds':seconds,'offset':round(float(offset),3),
          'approved':False,'edit_version':shot.get('edit_version'),
          'dialogue_hash':digest(str(shot.get('dialogue') or '').encode('utf8')),
          'speaker':shot.get('speaker','INNA'), 'source':'user_uploaded_local_wav',
          'path':dest.relative_to(root).as_posix()}
    shot['v85_audio']=info
    return info

def approve_audio(root,project,shot,sha,heard):
    info=shot.get('v85_audio') or {}
    if heard is not True:raise ValueError('Najpierw odsłuchaj pełną wypowiedź')
    f=safe_audio(root,project['id'],shot['id'])
    if not f.is_file() or digest(f.read_bytes())!=info.get('sha256') or sha!=info.get('sha256'):
        raise ValueError('Nagranie zostało podmienione')
    if info.get('edit_version')!=shot.get('edit_version') or info.get('dialogue_hash')!=digest(str(shot.get('dialogue') or '').encode('utf8')):
        raise ValueError('Kwestia zmieniła się po dodaniu nagrania')
    info['approved']=True
    return info

def cues(root,p,require_approved=False):
    cue_list=[];cursor=0.
    for shot in p.get('shots',[]):
        info=shot.get('v85_audio') or {}
        dur=float(shot.get('duration') or 0)
        if info:
            if info.get('edit_version')!=shot.get('edit_version') or info.get('dialogue_hash')!=digest(str(shot.get('dialogue') or '').encode('utf8')):
                raise ValueError('Dialog wymaga ponownego nagrania: '+shot['id'])
            if require_approved and not info.get('approved'):
                raise ValueError('Nieodsłuchany dubbing V8.5: '+shot['id'])
            f=safe_audio(root,p['id'],shot['id'])
            if not f.is_file() or digest(f.read_bytes())!=info.get('sha256'):
                raise ValueError('Nieprawidłowy plik dubbingu: '+shot['id'])
            begin=cursor+float(info.get('offset') or 0)
            if begin < -0.001:raise ValueError('Głos zaczyna się przed filmem')
            end=begin+float(info.get('seconds') or 0)
            if end>project_duration(p)+0.05:raise ValueError('Głos wykracza poza koniec filmu')
            cue_list.append({'shot_id':shot['id'],'file':str(f),'start':max(0,round(begin,3)),
                             'duration':info['seconds'],'speaker':info.get('speaker','INNA'),
                             'text':str(shot.get('dialogue') or '').strip(),
                             'approved':bool(info.get('approved'))})
        cursor+=dur
    return cue_list

def _stamp(value):
    ms=max(0,round(value*1000));h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def srt_from_cues(cue_list,total):
    """Generate non-overlapping subtitles tied to real dubbed voice, not shot ends."""
    items=[]
    for c in sorted(cue_list,key=lambda x:x['start']):
        t=str(c.get('text') or '').strip()
        if not t:continue
        start=max(0,float(c['start']));end=min(float(total),start+float(c['duration']))
        if items and start < items[-1]['end']:
            items[-1]['end']=max(items[-1]['start']+.1,start)
            if items[-1]['end']>start+0.01:raise ValueError('Kolidujące kwestie audio: najpierw popraw montaż')
        if end-start<0.15:continue
        words=t.split();lines=[];current=''
        for word in words:
            if len(current+' '+word)>35 and current:lines.append(current);current=word
            else:current=(current+' '+word).strip()
        if current:lines.append(current)
        if len(lines)>3:lines=[' '.join(words)]  # do not silently lose text
        items.append({'start':start,'end':end,'text':'\n'.join(lines)})
    return ''.join(f'{i}\n{_stamp(c["start"])} --> {_stamp(c["end"])}\n{c["text"]}\n\n'
                   for i,c in enumerate(items,1))

def review(root,p):
    result={'version':'8.5.0','mix_enabled':bool(p.get('v85_audio_mix')),
            'overwrite_original_audio':bool((p.get('v85_audio_mix') or {}).get('replace_clip_audio')),
            'total':project_duration(p),'notes':[],'cues':[]}
    try:
        result['cues']=cues(root,p)
        srt_from_cues(result['cues'],result['total'])
    except ValueError as e:result['notes'].append(str(e))
    if not result['cues']:result['notes'].append('Brak przygotowanych polskich nagrań: nie można ocenić dubbingu')
    if not result['overwrite_original_audio']:
        result['notes'].append('W trybie klasycznym dźwięk źródłowych MP4 pozostaje bez zmian')
    result['visual_and_phoneme_sync_verified']=False
    result['human_audiovisual_review_required']=True
    return result

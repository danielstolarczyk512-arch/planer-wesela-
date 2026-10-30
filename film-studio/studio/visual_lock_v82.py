"""V8.2 Master Visual Lock -- local, explicit human review and immutable SHA256 pins.
No paid work, model downloads, or outbound network requests from this module.

STYLE / IDENTITY / WARDROBE are intentionally distinct. Automatic image similarity
cannot prove identity for stylized humans; approval remains a human quality gate.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock

SLOTS = ("style", "woman", "man", "couple")
SOURCE = {
    "style": "assets/style/visual_reference.png",
    "woman": "assets/reference_v6/KOBIETA/MASTER/07_face_front.png",
    "man": "assets/reference_v6/MEZCZYZNA/MASTER/07_face_front.png",
    "couple": "assets/reference_v6/PARA/TOGETHER/01_table.png",
}
LOCK = RLock()
VERSION = "8.2.0"

def now():
    return datetime.now(UTC).isoformat(timespec="seconds")

def sha256(file):
    h=hashlib.sha256()
    with open(file,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def config_file(root):return Path(root)/"data"/"master_visual_v82.json"

def safe_file(root,rel):
    if not isinstance(rel,str) or not rel or rel.startswith('/') or '\\' in rel or '..' in Path(rel).parts:
        raise ValueError('Niedozwolona ścieżka do wzorca')
    base=Path(root).resolve()
    file=(base/rel).resolve()
    if not file.is_relative_to(base) or not file.is_file():raise ValueError('Brakuje pliku wzorca: '+rel)
    return file

def verify_image(file):
    # stdlib-only format and dimension check, not a visual/semantic evaluation
    f=Path(file)
    if not f.is_file() or not 128<=f.stat().st_size<=15*1024*1024:raise ValueError('Obraz musi mieć 128 B–15 MB')
    with f.open('rb') as stream:
        start=stream.read(32)
        if start[:8]==b'\x89PNG\r\n\x1a\n' and start[12:16]==b'IHDR':
            w,h=struct.unpack('>II',start[16:24]);kind='png'
        elif start[:3]==b'\xff\xd8\xff':
            stream.seek(2);w=h=0;kind='jpeg'
            for _ in range(10000):
                m=stream.read(1)
                if not m:break
                if m!=b'\xff':continue
                while m==b'\xff':m=stream.read(1)
                if not m:break
                code=m[0]
                if code in (0x00,0xd8,0xd9,0x01) or 0xd0<=code<=0xd7:continue
                sizebuf=stream.read(2)
                if len(sizebuf)<2:break
                n=int.from_bytes(sizebuf,'big')
                if n<2:break
                if code in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
                    data=stream.read(5)
                    if len(data)==5:h=int.from_bytes(data[1:3],'big');w=int.from_bytes(data[3:5],'big')
                    break
                stream.seek(n-2,1)
        else:raise ValueError('Wymagany prawdziwy plik PNG lub JPEG')
    if not 160<=w<=8192 or not 160<=h<=8192:raise ValueError('Wymiary obrazu: 160–8192 px')
    return {'format':kind,'width':w,'height':h,'bytes':f.stat().st_size,'sha256':sha256(f)}

def _read(root):
    file=config_file(root)
    try:data=json.loads(file.read_text('utf8'))
    except (OSError,ValueError):data={}
    if not isinstance(data,dict):data={}
    slots=data.get('slots') if isinstance(data.get('slots'),dict) else {}
    for k,rel in SOURCE.items():
        if k not in slots:
            # The style picture is designated as the previous approved source;
            # identity/couple portraits are unreviewed candidates, not promoted.
            slots[k]={'path':rel,'approved':k=='style', 'sha256':sha256(safe_file(root,rel)) if k=='style' else '', 'review_note':'Zatwierdzony przez użytkownika 2026-10-29 nowy Golden Master V8.5' if k=='style' else 'Kandydat — wymaga oceny ręcznej'}
    data['slots']=slots
    return data

def _save(root,data):
    f=config_file(root);f.parent.mkdir(parents=True,exist_ok=True)
    tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');os.replace(tmp,f)

def summary(root):
    with LOCK:data=_read(root)
    out={}
    for slot in SLOTS:
        record=data['slots'][slot].copy()
        try:
            file=safe_file(root,record['path']);info=verify_image(file)
            pinned=record.get('sha256')
            changed=bool(pinned and pinned!=info['sha256'])
            record.update(info)
            record['ready']=bool(record.get('approved')) and not changed
            record['changed']=changed
            record['warning']='Źródło ma niską rozdzielczość — nie jest wysokiej jakości referencją' if min(info['width'],info['height'])<512 else ''
        except ValueError as exc:
            record.update(ready=False,changed=True,warning=str(exc),sha256='',width=0,height=0)
        out[slot]=record
    return {'version':VERSION,'slots':out,'ready':all(x['ready'] for x in out.values()),
            'note':'Porównanie estetyczne wymaga ręcznej oceny. Brak modeli AI i generacji w tle.'}

def approve(root,slot,observed_sha,viewed,note):
    if slot not in SLOTS:raise ValueError('Nieznany typ wzorca')
    if viewed is not True:raise ValueError('Najpierw obejrzyj wzorzec')
    if not isinstance(note,str) or len(note)>700:raise ValueError('Notatka za długa')
    with LOCK:
        data=_read(root);record=data['slots'][slot]
        info=verify_image(safe_file(root,record['path']))
        if observed_sha!=info['sha256']:raise ValueError('Obraz się zmienił. Odśwież podgląd przed zatwierdzeniem')
        record.update(approved=True,sha256=info['sha256'],reviewed_at=now(),review_note=note.strip())
        _save(root,data)
    return summary(root)['slots'][slot]

def replace(root,slot,contents,content_type):
    if slot not in SLOTS:raise ValueError('Nieznany typ wzorca')
    if content_type not in ('image/png','image/jpeg'):raise ValueError('Dozwolone PNG/JPEG')
    if not 128<=len(contents)<=12*1024*1024:raise ValueError('Obraz: 128 B–12 MB')
    with LOCK:
        base=Path(root)/'data'/'master_assets_v82';base.mkdir(parents=True,exist_ok=True)
        ext='.png' if content_type=='image/png' else '.jpg'
        import tempfile
        with tempfile.NamedTemporaryFile(dir=base,suffix=ext,delete=False) as temp:
            temp.write(contents);temp_path=Path(temp.name)
        try:
            info=verify_image(temp_path)
            if info['format'] != ('png' if ext=='.png' else 'jpeg'):raise ValueError('Zawartość nie pasuje do MIME')
            destination=base/(slot+'_'+info['sha256'][:20]+ext)
            if not destination.exists():shutil.copy2(temp_path,destination)
            data=_read(root)
            data['slots'][slot]={'path':destination.relative_to(root).as_posix(), 'approved':False,
               'sha256':info['sha256'],'review_note':'Nowy obraz — wymaga ręcznej akceptacji'}
            _save(root,data)
        finally:temp_path.unlink(missing_ok=True)
    return summary(root)['slots'][slot]

def snapshot(root):
    state=summary(root)
    missing=[x for x,v in state['slots'].items() if not v['ready']]
    if missing:raise ValueError('Najpierw zatwierdź wzorce: '+', '.join(missing))
    return {slot:{'sha256':row['sha256'],'path':row['path']} for slot,row in state['slots'].items()}

def pin_project(project,root):
    frozen=snapshot(root)
    project['v82_visual_lock']=True
    project['v82_visual_snapshot']=frozen
    project['v82_visual_version']=VERSION
    project['style_lock']=True
    project['visual_style_version']='8.2-master'
    for shot in project.get('shots',[]):
        shot['edit_version']=__import__('uuid').uuid4().hex
        shot['qc_approved']=False
        shot['v7_lips_approved']=False
        for field in ('v82_frame_approval','v82_clip_approval','v82_synced_sha256','v82_synced_at','quote','image_quote','image_url','workflow_id','media_url'):
            shot.pop(field,None)
    return project

def unpin_project(project):
    project['v82_visual_lock']=False
    project.pop('v82_visual_snapshot',None)
    return project

def check_masters(project,root):
    if not project.get('v82_visual_lock'):return []
    pinned=project.get('v82_visual_snapshot') or {}
    try:current=snapshot(root)
    except ValueError as e:return [str(e)]
    problems=[]
    for slot in SLOTS:
        if pinned.get(slot)!=current.get(slot):problems.append('Zmienił się wzorzec '+slot+'; ponownie przypnij Master Visual Lock')
    return problems

def frame_path(root,project,shot):
    file_name=shot.get('firstframe_local')
    if not isinstance(file_name,str) or not re.fullmatch(r'S\d{2}\.(png|jpg|jpeg)',file_name):
        raise ValueError('Brak lokalnej klatki początkowej PNG/JPG')
    base=Path(root)/'data'/'keyframes'/project['id']
    file=(base/file_name).resolve()
    if not file.is_relative_to(base.resolve()) or not file.is_file():raise ValueError('Klatka początkowa nie istnieje')
    return file

def approve_frame(project,shot,root,viewed,style_ok,identity_ok,notes='',observed_sha=None):
    issues=check_masters(project,root)
    if not project.get('v82_visual_lock'):raise ValueError('Najpierw włącz Master Visual Lock dla projektu')
    if issues:raise ValueError('; '.join(issues))
    if any(x is not True for x in (viewed,style_ok,identity_ok)):
        raise ValueError('Potwierdź obejrzenie, zgodność stylu i tożsamości')
    if len(str(notes))>800:raise ValueError('Notatka przekracza 800 znaków')
    file=frame_path(root,project,shot)
    image=verify_image(file)
    if observed_sha is not None and observed_sha!=image['sha256']:
        raise ValueError('Klatka zmieniła się od ostatniego podglądu')
    if min(image['width'],image['height'])<512:raise ValueError('Klatka startowa jest zbyt mała (minimum 512 px)')
    approval={'sha256':image['sha256'],'edit_version':shot.get('edit_version'),
              'master_snapshot':project['v82_visual_snapshot'],'approved_at':now(),'notes':notes}
    shot['v82_frame_approval']=approval
    shot['qc_approved']=False
    return approval

def check_frame(project,shot,root):
    issues=check_masters(project,root)
    if not project.get('v82_visual_lock'):return []
    if shot.get('mode')!='t2v':return issues
    try:
        file=frame_path(root,project,shot);sha=sha256(file)
        approval=shot.get('v82_frame_approval') or {}
        if approval.get('sha256')!=sha or approval.get('edit_version')!=shot.get('edit_version') or approval.get('master_snapshot')!=project.get('v82_visual_snapshot'):
            issues.append('Brak aktualnej ręcznie zatwierdzonej klatki '+shot['id'])
    except ValueError as e:issues.append(str(e))
    return issues

def check_video(project,shot,root):
    issues=check_frame(project,shot,root)
    if project.get('v82_visual_lock') and shot.get('mode')=='t2v':
        if shot.get('video_model')!='minimax-h3-fasth3-i2v-turbo':issues.append('V8.2: wymagany tryb Image-to-Video H3')
        if not str(shot.get('image_url') or '').startswith('https://'):issues.append('V8.2: najpierw synchronizuj zatwierdzoną klatkę')
        if shot.get('v82_synced_sha256')!=(shot.get('v82_frame_approval') or {}).get('sha256'):
            issues.append('V8.2: adres klatki Sogni nie pasuje do zatwierdzonego obrazu')
        try:
            dt=datetime.fromisoformat(shot.get('v82_synced_at',''))
            if datetime.now(UTC)-dt > timedelta(hours=40):issues.append('V8.2: odśwież czasowy adres klatki Sogni')
        except (ValueError,TypeError):issues.append('V8.2: brak czasu synchronizacji klatki')
    return issues

def project_report(project,root):
    return {'enabled':bool(project.get('v82_visual_lock')),
      'master_issues':check_masters(project,root),'shots':[
        {'id':s['id'],'mode':s['mode'],'frame_issues':check_frame(project,s,root),
        'video_issues':check_video(project,s,root),
        'frame_approved':bool(s.get('v82_frame_approval'))}
       for s in project.get('shots',[])]}

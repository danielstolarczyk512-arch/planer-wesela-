"""V6 curated reference library: local-only until explicitly approved and sent to Sogni.

Checkpoint is NOT a completed approved library: preserve the author's review status.
Image bytes are packaged read-only under assets/reference_v6. User decisions live in data/.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / 'assets' / 'reference_v6'
INDEX = ASSETS / 'index.json'
DATA = BASE / 'data' / 'references_v6'
REVIEWS = DATA / 'review_decisions.json'
LOCK = RLock()
DECISIONS = {'pending_final_review', 'pending_correction', 'approved', 'rejected'}
ROLES = {'ONA': 'KOBIETA', 'ON': 'MEZCZYZNA', 'WUJEK': 'WUJEK'}


def utcnow():
    return datetime.now(UTC).isoformat(timespec='seconds')


def _catalog():
    if not INDEX.is_file(): return {'version': 'v6', 'checkpoint': True, 'items': []}
    return json.loads(INDEX.read_text(encoding='utf-8'))


def _decisions():
    if not REVIEWS.is_file(): return {}
    data=json.loads(REVIEWS.read_text(encoding='utf-8'))
    return data if isinstance(data, dict) else {}


def _write(data):
    DATA.mkdir(parents=True,exist_ok=True)
    tmp=REVIEWS.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,REVIEWS)


def entries():
    with LOCK:
        overrides=_decisions()
        out=[]
        for item in _catalog().get('items',[]):
            x=item.copy(); x.update(overrides.get(x['id'],{}))
            # Do not trust old approved status when the underlying file changes.
            file=ASSETS / x['path']
            if not file.is_file() or file.stat().st_size != x['bytes']:
                x['review']='missing_or_changed'
            out.append(x)
        return out


def summary():
    all_items=entries()
    statuses={s:sum(x['review']==s for x in all_items) for s in (*sorted(DECISIONS),'missing_or_changed')}
    return {'version':'6.0','library_status':'checkpoint_requires_review','count':len(all_items),
            'categories':{c:sum(x['category']==c for x in all_items) for c in ('KOBIETA','MEZCZYZNA','PARA','WUJEK')},
            'statuses':statuses,'images':all_items}


def find(identifier):
    if not isinstance(identifier,str) or len(identifier)>120 or not re.fullmatch(r'[A-Za-z0-9_\-/]+',identifier):
        raise ValueError('Nieprawidłowy identyfikator referencji')
    for x in entries():
        if x['id']==identifier:return x
    raise ValueError('Nieznana referencja')


def file_for(identifier):
    row=find(identifier)
    p=(ASSETS / row['path']).resolve()
    if not p.is_relative_to(ASSETS.resolve()) or not p.is_file():
        raise ValueError('Referencja niedostępna')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
        raise ValueError('Referencja zmieniona: błąd SHA-256')
    return p


def review(identifier,decision,note=''):
    if decision not in DECISIONS:raise ValueError('Nieprawidłowa decyzja jakościowa')
    if len(str(note))>800:raise ValueError('Notatka za długa')
    with LOCK:
        row=find(identifier)
        if row['review']=='missing_or_changed':raise ValueError('Brak prawidłowego pliku do oceny')
        actual=hashlib.sha256((ASSETS/row['path']).read_bytes()).hexdigest()
        if actual != row['sha256']:raise ValueError('Referencja zmieniona: błąd SHA-256')
        updates=_decisions()
        prev=updates.get(identifier,{})
        new={'review':decision,'reviewed_at':utcnow(),'review_note':str(note).strip(),
             'remote_url':'','remote_synced_at':''}
        if decision==prev.get('review')=='approved':
            new['remote_url']=prev.get('remote_url','')
            new['remote_synced_at']=prev.get('remote_synced_at','')
        updates[identifier]=new
        _write(updates)
    return find(identifier)


def set_remote(identifier,remote_url):
    url=urlparse(remote_url)
    if url.scheme!='https' or not url.netloc or len(remote_url)>2500:
        raise ValueError('Adres referencji z Sogni musi być poprawnym HTTPS')
    with LOCK:
        row=find(identifier)
        if row['review']!='approved':raise ValueError('Najpierw zatwierdź referencję')
        file_for(identifier)  # Verify actual bytes before publishing a remote link
        overrides=_decisions();d=overrides.get(identifier,{})
        d.update(review='approved',remote_url=remote_url,remote_synced_at=utcnow())
        overrides[identifier]=d;_write(overrides)
    return find(identifier)


def live_url(row,ttl_hours=40):
    url=row.get('remote_url','')
    if not url.startswith('https://') or row.get('review')!='approved':return ''
    try:
        synced=datetime.fromisoformat(row.get('remote_synced_at',''))
        if datetime.now(UTC)-synced >= timedelta(hours=ttl_hours):return ''
    except (ValueError,TypeError):return ''
    return url


def _quality_score(item,shot,role):
    """Deterministic ranking only; not an AI similarity metric."""
    text=(' '.join(str(shot.get(k,'')) for k in ('prompt','function','description'))).lower()
    mode=(str(shot.get('camera',''))+' '+text).lower()
    parts=item['path'].lower()
    score=0
    if '/master/07_face_front' in parts:score+=70
    if '/master/01_front' in parts:score+=60
    if '/views/09_waist_up' in parts:score+=45
    if ('profil' in mode or 'profile' in mode or 'side view' in mode):
        if '/views/03_left_profile' in parts or '/views/04_right_profile' in parts:score+=85
    if ('tył' in mode or 'rear' in mode or 'back view' in mode) and '/views/02_back' in parts:score+=95
    if ('full body' in mode or 'cała sylwetka' in mode) and '/master/01_front' in parts:score+=50
    if ('smile' in mode or 'uśmiech' in mode) and '/expressions/11_soft_smile' in parts:score+=60
    if ('laugh' in mode or 'śmiech' in mode) and '/expressions/12_laugh' in parts:score+=60
    if ('sad' in mode or 'smutek' in mode) and '/expressions/14_sad' in parts:score+=60
    if ('phone' in mode or 'telefon' in mode) and '/poses/24_phone' in parts:score+=75
    if ('walking' in mode or 'spacer' in mode) and '/poses/22_walking' in parts:score+=75
    if role=='WUJEK':
        if 'portrait.png' in parts:score+=95
        if 'threequarter' in mode and 'threequarter' in parts:score+=120
        if ('profile' in mode or 'profil' in mode) and 'profile' in parts:score+=110
        if ('śmiech' in mode or 'laugh' in mode) and 'expression_2' in parts:score+=100
        if ('telefon' in mode or 'phone' in mode) and 'phone' in parts:score+=105
        if ('taniec' in mode or 'dance' in mode) and 'dance' in parts:score+=110
    if role=='PARA' and '/together/' in parts:score+=20
    if role=='PARA' and ('kuchnia' in mode or 'kitchen' in mode) and ('03_kitchen' in parts or '01_table' in parts):score+=65
    if role=='PARA' and ('laptop' in mode or 'plan' in mode) and ('02_laptop' in parts or '07_wedding_planning' in parts):score+=75
    return score


def suggest_for_shot(shot,max_images=3):
    """Rank approved references, never silently promote unchecked checkpoint images."""
    characters=set(shot.get('characters') or [])
    wanted=[ROLES[r] for r in ('ONA','ON','WUJEK') if r in characters]
    eligible=[x for x in entries() if x['review']=='approved']
    selected=[]
    if len(wanted)==2 and set(wanted)=={'KOBIETA','MEZCZYZNA'}:
        couple=[x for x in eligible if x['category']=='PARA']
        if couple:selected.append(max(couple,key=lambda x:(_quality_score(x,shot,'PARA'),x['id'])))
    for cat in wanted:
        images=[x for x in eligible if x['category']==cat]
        if images:selected.append(max(images,key=lambda x:(_quality_score(x,shot,cat),x['id'])))
    return selected[:max_images]


def resolve_for_shot(shot):
    manual=shot.get('v6_reference_ids') or []
    if not isinstance(manual,list) or len(manual)>3:raise ValueError('Dozwolone są maksymalnie 3 referencje')
    chosen=[find(key) for key in manual] if manual else suggest_for_shot(shot)
    categories={ROLES[r] for r in (shot.get('characters') or []) if r in ROLES}
    for row in chosen:
        if row['review']!='approved':raise ValueError('Referencja nie jest zatwierdzona: '+row['id'])
        file_for(row['id'])  # Never use approval for tampered image bytes
        if row['category'] not in categories and not (row['category']=='PARA' and len(categories)==2):
            raise ValueError('Referencja nie pasuje do obsady ujęcia: '+row['id'])
    return chosen


def prepare_prompt(project,shot):
    refs=resolve_for_shot(shot)
    # State the assignment explicitly, but never promise exact identity from text alone.
    desc=' '.join(f'<Picture {i+1}>: approved {r["category"]} identity / {r["path"].split("/")[-1]}; ' for i,r in enumerate(refs))
    if not desc:return 'CHARACTER CONSISTENCY: Use locked visual bible and approved cast references; never invent a different face.'
    return 'IDENTITY REFERENCE POLICY: '+desc+'Primary portraits take precedence over pose and environment references. Use role-specific identity only: ON has short hair and rounded jaw; ONA has brown updo and freckles; WUJEK Bogdan has a LONG narrow face, thin moustache, greying temples and plum suit. NEVER transfer ON facial structure to WUJEK. Keep Golden Storybook 3D, no live action.'


def upload_urls(shot):
    refs=resolve_for_shot(shot)
    return [u for x in refs if (u:=live_url(x))]


def review_safety(shot):
    selected=resolve_for_shot(shot)
    if shot.get('mode') not in ('t2v','i2v','ia2v'):return {'ready':True,'missing':[],'selected':[x['id'] for x in selected]}
    characters=set(shot.get('characters') or [])
    missing=[]
    for role in ('ONA','ON','WUJEK'):
        if role in characters and not any(x['category']==ROLES[role] for x in selected):missing.append('Brak zatwierdzonej referencji '+role)
    return {'ready':not missing,'missing':missing,'selected':[x['id'] for x in selected]}

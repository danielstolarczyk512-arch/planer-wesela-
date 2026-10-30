"""Apply the user's 29-Oct approved new STYLE to migrated V8.4 data only.
Preserves identity reference decisions and project archives; old project pins fail
until the user explicitly re-pins all masters (no silent migration of old clips).
"""
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
source=ROOT/'assets/style/visual_reference.png'
sha=hashlib.sha256(source.read_bytes()).hexdigest()
config=ROOT/'data/master_visual_v82.json'
if config.exists():
    try:d=json.loads(config.read_text(encoding='utf8'))
    except (ValueError,OSError):d={}
    if not isinstance(d,dict):d={}
    slots=d.setdefault('slots',{})
    slots['style']={'path':'assets/style/visual_reference.png','approved':True,'sha256':sha,
        'review_note':'Nowy styl wybrany przez użytkownika 2026-10-29; projekty wymagają ponownego przypięcia'}
    tmp=config.with_suffix('.tmp')
    tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
    os.replace(tmp,config)
    print('V8.5: styl zmieniony. Ponownie przypnij Master Visual Lock we wszystkich projektach.')
else:
    print('V8.5: brak poprzednich zatwierdzeń. Nowy styl jest domyślnie wybrany.')
print('STYLE SHA256:',sha)

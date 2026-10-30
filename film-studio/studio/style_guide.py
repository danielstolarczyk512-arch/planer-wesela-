"""Local style anchor, optionally uploaded to Sogni via an explicit user request."""
import hashlib
import json
from pathlib import Path

from .personas import STYLE_ID, STYLE_NAME, now


def default_image(root):
    return Path(root)/'assets'/'style'/'visual_reference.png'

def _master_sha(root):
    f=default_image(root)
    return hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else ''

def state(root):
    file=Path(root)/'data'/'style_guide.json'
    try:raw=json.loads(file.read_text(encoding='utf8'))
    except (OSError,ValueError):raw={}
    current=_master_sha(root)
    matching=bool(raw.get('master_sha256') and raw.get('master_sha256')==current)
    return {'style_id':STYLE_ID,'style_name':STYLE_NAME,'master_sha256':current,'remote_master_matches':matching,
            'remote_reference_url':raw.get('remote_reference_url','') if matching else '',
            'synced_at':raw.get('synced_at',''),
            'expires_hint_hours':48,'has_local_image':default_image(root).is_file(),'remote_outdated':bool(raw.get('remote_reference_url') and not matching)}

def write_remote(root,url):
    file=Path(root)/'data'/'style_guide.json'
    file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(json.dumps({'remote_reference_url':url,'synced_at':now(),'master_sha256':_master_sha(root)},ensure_ascii=False),encoding='utf8')

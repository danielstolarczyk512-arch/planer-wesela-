#!/usr/bin/env python3
"""Import previously downloaded V6 checkpoint to LIGHT version without untrusted paths."""
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'assets'/'reference_v6'
INDEX=TARGET/'index.json'

def install(archive):
    if not INDEX.is_file():raise RuntimeError('Missing V6 index.json')
    entries=json.loads(INDEX.read_text(encoding='utf8'))['items']
    with ZipFile(archive) as z:
        names=set(z.namelist())
        for x in entries:
            name='NASZ_DZIEN_CHARACTERS_V6/'+x['path']
            if name not in names:raise RuntimeError('Missing image in checkpoint: '+name)
            content=z.read(name)
            if hashlib.sha256(content).hexdigest()!=x['sha256'] or len(content)!=x['bytes']:
                raise RuntimeError('SHA256 mismatch: '+name)
            dest=(TARGET/x['path']).resolve()
            if not dest.is_relative_to(TARGET.resolve()):raise RuntimeError('Unsafe path')
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(content)
    return len(entries)

if __name__=='__main__':
    if len(sys.argv)!=2:
        print('Użycie: python tools/install_checkpoint.py NASZ_DZIEN_CHARACTER_REFERENCE_LIBRARY_V6_CHECKPOINT.zip');sys.exit(2)
    print('Zainstalowano',install(Path(sys.argv[1])),'referencji PNG — wymagają ręcznej akceptacji w aplikacji.')

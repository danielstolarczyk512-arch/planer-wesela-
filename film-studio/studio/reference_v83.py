"""Master-guided image-edit requests with explicit upload consent.
No network on reading/building plans; URLs expire and must be reuploaded.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from . import character_bible_v83
from . import visual_lock_v82 as visual

VERSION='8.3.0'
IMAGE_MODEL='krea-identity-edit'  # verified selector; actual Unlimited eligibility checked by provider on start


def slots_for_shot(shot):
    roles=set(shot.get('characters') or [])
    if roles == {'ONA'}:return ['woman','style']
    if roles == {'ON'}:return ['man','style']
    if roles == {'ONA','ON'}:return ['couple','woman','man','style']
    return ['style']


def plan(project,shot,root):
    if not project.get('v82_visual_lock'):
        raise ValueError('Najpierw włącz Master Visual Lock V8.2')
    issues=visual.check_masters(project,root)
    if issues:raise ValueError('; '.join(issues))
    frozen=project.get('v83_character_snapshot')
    if project.get('v83_reference_mode') and frozen!=character_bible_v83.binding(project)['roles']:
        raise ValueError('Zmieniła się Character Bible: ponownie zatwierdź obsadę i przypnij wzorce')
    if shot.get('mode')!='t2v':raise ValueError('Referencyjny obraz generujemy tylko dla ujęcia animowanego')
    snapshot=project.get('v82_visual_snapshot') or {}
    slots=slots_for_shot(shot)
    return {'model':IMAGE_MODEL,'slots':slots,'source_slot':slots[0],
            'files':[{'slot':s,'path':snapshot[s]['path'],'sha256':snapshot[s]['sha256']} for s in slots],
            'edit_version':shot.get('edit_version'),'note':'Zatwierdzone referencje muszą być wysłane jawnie. Następnie sprawdź obraz wyjściowy ręcznie.'}


def mark_uploaded(project,shot,root,uploads):
    expected=plan(project,shot,root)
    if not isinstance(uploads,list) or len(uploads)!=len(expected['files']):
        raise ValueError('Niekompletne przesłanie wzorców')
    for file,row in zip(expected['files'],uploads):
        if file['slot']!=row.get('slot') or not str(row.get('url','')).startswith('https://'):
            raise ValueError('Nieprawidłowa kolejność lub URL wzorca')
    shot['v83_reference_binding']={
        'source_slot':expected['source_slot'],'slots':expected['slots'],
        'master_snapshot':project['v82_visual_snapshot'],
        'edit_version':shot.get('edit_version'),
        'synced_at':datetime.now(UTC).isoformat(timespec='seconds'),
        'urls':[row['url'] for row in uploads]}
    shot.pop('image_quote',None)
    return shot['v83_reference_binding']


def remote_refs(project,shot,root):
    expected=plan(project,shot,root)
    binding=shot.get('v83_reference_binding') or {}
    if (binding.get('edit_version')!=shot.get('edit_version') or
        binding.get('master_snapshot')!=project.get('v82_visual_snapshot') or
        binding.get('slots')!=expected['slots']):
        raise ValueError('Referencje nie odpowiadają obecnej klatce/wersji projektu. Ponownie prześlij wzorce.')
    try:
        dt=datetime.fromisoformat(binding.get('synced_at',''))
        if dt.tzinfo is None or datetime.now(UTC)-dt>timedelta(hours=40):raise ValueError('Wygasła ważność referencji Sogni')
    except (TypeError,ValueError) as exc:
        raise ValueError('Referencje Sogni wymagają ponownego przesłania') from exc
    urls=binding.get('urls') or []
    if len(urls)!=len(expected['slots']) or any(not isinstance(u,str) or not u.startswith('https://') for u in urls):
        raise ValueError('Brakuje wymaganych obrazowych referencji')
    return urls


def prepare_image_request(project,shot,root,prepared=None):
    urls=remote_refs(project,shot,root)
    from .personas import prepare_for_sogni
    prepared=prepared or prepare_for_sogni(project,shot)
    prepared['v83_image_model']=IMAGE_MODEL
    prepared['v83_reference_urls']=urls
    prepared['v83_master_sha256']={k:v['sha256'] for k,v in project['v82_visual_snapshot'].items()}
    return prepared


def public_status(project,shot,root):
    try:
        info=plan(project,shot,root)
        try:remote_refs(project,shot,root);ready=True;problem=None
        except ValueError as e:ready=False;problem=str(e)
        return {'plan':info,'uploaded':ready,'problem':problem}
    except ValueError as e:return {'plan':None,'uploaded':False,'problem':str(e)}

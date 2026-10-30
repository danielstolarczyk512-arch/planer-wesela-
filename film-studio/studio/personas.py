"""V5 Character Library: local portraits and deterministic style/casting preparation.
No external dependencies and no billable operations on import or project creation.
"""
from __future__ import annotations

import copy
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

STYLE_ID='golden_storybook_3d'
STYLE_NAME='Golden Storybook 3D — wzorzec Nasz Dzień'
# Style is *not* photorealism. These motifs reflect the user's own reference collage.
STYLE_VISUAL=(
    'Consistent premium stylized 3D ANIMATED STORYBOOK FILM, NOT live action, '
    'NOT photorealistic portrait photography. Preserve the EXACT approved Golden Master character facial geometry and proportions; '
    'humanlike stylized eye size, soft dimensional facial planes, subtle painterly contours matching the supplied NEW V8.5 master couple image, '
    'soft painterly CGI surface shading, hand-crafted animation aesthetic, subtle warm blush and freckles, '
    'artistically designed hair clumps with fine luminous wisps, charming imperfect expressions. '
    'Golden-hour illumination matching the actual approved V8.5 master couple image, amber rim lights with retained skin midtones, warm honey-brown and burnt-orange shadows, '
    'glowing rim lighting, cozy window light and pendant lamps, cinematic atmospheric dust, '
    'soft volumetric rays, rich bokeh depth, living-in a warm detailed kitchen or wedding setting. '
    'Coherent silhouettes and stable model-sheet identity for all shots; no identity changes.'
)
STYLE_MOTION=(
    'Animate like a high-end original 3D short: restrained expressive facial acting, '
    'believable eyelines and small pauses, smooth head movement, controlled hand anatomy, '
    'gentle ease-in and ease-out, a single readable physical action per shot, '
    'film-like camera motion, no rubber limbs and no generic talking-to-camera poses.'
)
STYLE_AVOID=(
    'Avoid photo-real live action, glossy fashion portrait skin, hyperrealistic wrinkles, '
    'plastic doll skin, excessively large eyes, caricatured face, round glassy doll eyes, changed character anatomy, random extra fingers, '
    'overexposure, washed-out white highlights, neon palette, conflicting anime/flat-vector style, '
    'subtitles or fake text embedded in frames.'
)

STARTER={
 'ona':{'name':'Natalia — animowana bohaterka', 'role':'ONA',
  'look':'Original stylized brunette woman, brown expressive eyes, softly arched brows, warm light complexion with a few subtle beauty marks, messy brown updo with wisps, sunglasses on top of head, black halter top with small white polka dots, ivory wide-leg trousers, white shoes, dark smartwatch. Keep exact approved master face geometry, do not turn into a doll or a photorealistic glamour portrait.',
  'personality':'pogodna, błyskotliwa, subtelny humor', 'avoid':'same bun, sunglasses, dark polka-dot halter, light trousers, brown eyes and model-sheet facial shape'},
 'on':{'name':'Daniel — animowany bohater', 'role':'ON',
  'look':'Original stylized adult man, short neatly textured medium-brown hair, broad softly rounded jaw, regular natural brows, pleasant gentle half-smile, light complexion; charcoal black plain T-shirt, beige shorts and white sneakers as the default approved outfit. Render with the same stylized, subtly sculpted eye proportions, painted CGI skin and soft contour language as the female model sheet, not a realistic photograph.',
  'personality':'spokojny, dowcipny, życzliwy', 'avoid':'keep cropped short brown haircut, broad face, short simple hairstyle and fixed wardrobe; no voluminous hair, no angular long face, no heavy stubble, no live-action skin'}
}


# Exact approved *design* from the separately supplied character-reference bundle.
BOGUS_PERSONA={'name': 'Bogdan „Boguś” — król weselnego parkietu', 'role': 'WUJEK', 'look': "Bogdan (Boguś), the SAME fictional Polish wedding uncle from the supplied identity portrait. Approximately 52 years old, tall slim long-limbed build, long narrow face and chin, prominent long nose, thick dark eyebrows, brown eyes, dark narrow moustache, swept-up and swept-back brown hair with grey temples. Warm light complexion. Fixed plum matching suit, pale pink open-collar shirt, fine gold chain, patterned plum-and-gold pocket square in his LEFT breast pocket, dark belt with gold-tone buckle, black loafers. Preserve the exact portrait facial geometry. Original stylized cinematic 3D animation, soft painterly CGI shading matching the approved project style. Portrait is identity authority; body views govern proportions and clothing. Never transfer the younger male lead's rounded jaw or short haircut to Bogdan.", 'personality': 'Serdeczny, towarzyski, nadmiernie pewny siebie. Pomaga bez proszenia, uważa się za eksperta od wesel. Humor sytuacyjny i mikroreakcje. Powiedzonko: „Ja tylko jedną rzecz podpowiem…”. Nigdy złośliwy; nie opierać komizmu na alkoholu.', 'avoid': 'No changing face, nose, jaw length, moustache, eye color, age, haircut, body build or wardrobe. No glasses, beard, bow tie, necktie, hat, extra jewellery, duplicate person, extra fingers, warped hands, facial blending with Daniel, photorealistic restyling or enlarged doll eyes. No automatic mirroring of pocket square or hair. No permanent toothy smile. No generated interface text.'}
BOGUS_ID='33333333-3333-4333-8333-333333333333'

ALLOWED_ASSETS={'sheet','portrait','front','threequarter','profile','back'} | {f'expression_{i}' for i in range(1,7)}

def now():return datetime.now(UTC).isoformat(timespec='seconds')

def new_persona(data):
    name=str(data.get('name','')).strip()
    if not (1<=len(name)<=100):raise ValueError('Nazwa postaci: 1–100 znaków')
    role=str(data.get('role','')).strip().upper()
    if role not in ('ONA','ON','CIOCIA','WUJEK','INNA'):role='INNA'
    return {'id':str(uuid.uuid4()),'name':name,'role':role,'look':str(data.get('look',''))[:3000],
            'personality':str(data.get('personality',''))[:1000], 'avoid':str(data.get('avoid',''))[:2000],
            'style_id':STYLE_ID,'created':now(),'updated':now(),'assets':{},'remote_reference_url':'',
            'remote_reference_kind':'','remote_synced_at':'','reference_status':'local_only'}

def seed_defaults(store,root):
    base=Path(root)/'assets'/'starter_personas'
    for k,spec in STARTER.items():
        id='11111111-1111-4111-8111-111111111111' if k=='ona' else '22222222-2222-4222-8222-222222222222'
        if store.get_persona(id):continue
        obj=new_persona(spec);obj['id']=id;obj['starter']=True
        dst=Path(root)/'data'/'personas'/id;dst.mkdir(parents=True,exist_ok=True)
        for asset in ALLOWED_ASSETS:
            file=base/(k+('_arkusz' if asset=='sheet' else '_'+asset)+'.png')
            if file.is_file():
                shutil.copy2(file,dst/(asset+'.png'));obj['assets'][asset]=asset+'.png'
        store.save_persona(obj)

def seed_wujek(store, root):
    """Idempotently install ORIGINAL Boguś images, never approve remote use."""
    if store.get_persona(BOGUS_ID):return store.get_persona(BOGUS_ID)
    item=new_persona(BOGUS_PERSONA);item['id']=BOGUS_ID;item['starter']=True
    target=Path(root)/'data'/'personas'/BOGUS_ID;target.mkdir(parents=True,exist_ok=True)
    source=Path(root)/'assets'/'starter_personas'
    for asset in sorted(ALLOWED_ASSETS):
        f=source/('wujek_'+asset+'.png')
        if f.is_file():
            shutil.copy2(f,target/(asset+'.png'))
            item['assets'][asset]=asset+'.png'
    store.save_persona(item)
    return item

def check_asset_name(asset):
    if asset not in ALLOWED_ASSETS:raise ValueError('Nieobsługiwany typ referencji')

def selected_cast(store,casting):
    cast=[]
    for role,pid in (casting or {}).items():
        if role not in ('ONA','ON','CIOCIA','WUJEK'):raise ValueError('Nieznana rola obsady')
        if not pid:continue
        person=store.get_persona(pid)
        if not person:raise ValueError('Nie znaleziono postaci w bibliotece')
        if person.get('role')!=role:raise ValueError('Nieprawidłowe przypisanie roli: '+role)
        cast.append({'id':role,'name':person['name'],'look':person['look'],
                     'personality':person['personality'],'avoid':person['avoid'],
                     'persona_id':person['id'],'reference_url':person.get('remote_reference_url',''),
                     'style_id':person['style_id']})
    return cast

def invalidate_shots(project):
    project['shot_generation']=str(uuid.uuid4())
    for s in project.get('shots',[]):
        s['edit_version']=str(uuid.uuid4());s['qc_approved']=False
        for k in ('quote','image_quote','media_url','image_url','workflow_id','ui_provenance','qc_report','approval_date'):
            s.pop(k,None)

def bind_cast(project,store,casting):
    if not isinstance(casting,dict) or len(casting)>4:raise ValueError('Wybierz maksymalnie 4 postacie')
    cast=selected_cast(store,casting)
    project['casting']={k:v for k,v in casting.items() if v}
    project['cast']=cast+[copy.deepcopy(c) for c in project.get('cast',[]) if c.get('id') not in {v['id'] for v in cast} and c.get('id') in ('CIOCIA','WUJEK')]
    project['visual_style_id']=STYLE_ID
    project['visual_style_version']='1.0'
    project['style_lock']=True
    invalidate_shots(project)
    for shot in project.get('shots',[]):
        # Legacy V2/V3 demo shots did not define characters; default to lead actors.
        if shot.get('mode')=='t2v' and not shot.get('characters'):
            shot['characters']=[r for r in ('ONA','ON') if r in project['casting']]
        # Role assignment remains explicit; the storyboard knows exactly who appears.
        shot['personas']={r:project['casting'][r] for r in shot.get('characters',[]) if r in project['casting']}
        shot['style_id']=STYLE_ID
    project['updated']=now()
    return project

def cast_for_shot(project,shot):
    ids=set(shot.get('characters') or [])
    return [c for c in project.get('cast',[]) if c.get('id') in ids]

def clean_live_action(text):
    text=str(text or '')
    for phrase in ('Cinematic realistic live action','Observational cinematic live action',
                   'believable skin texture','naturally imperfect placement of tableware',
                   'realistic live action','realistic skin texture'):
        text=re.sub(re.escape(phrase),'stylized cinematic CGI animation',text,flags=re.I)
    return text

def render_prompt(project,shot):
    people=cast_for_shot(project,shot)
    identity=('; '.join(f'{x["name"]}: {x.get("look","")}. Stable identity: {x.get("avoid","")}' for x in people))
    # Only selected cast goes into prompt; this prevents swapping the actors.
    locked='MASTER VISUAL LOCK 8.2: verified frame is authoritative. Do not reinterpret any face shape, eyes, nose, jaw, hair or material style. STYLE and IDENTITY are separate; WARDROBE must follow approved continuity. ' if project.get('v82_visual_lock') else ''
    return (locked+'STYLE LOCK ['+STYLE_ID+']: '+STYLE_VISUAL+' MOTION: '+STYLE_MOTION+
            ' DESIGN REFERENCES: '+identity+'. SCENE: '+clean_live_action(shot.get('prompt',''))+
            ' QUALITY GUARD: '+STYLE_AVOID)[:10500]

def shot_provider_refs(project,shot,style_url=None):
    ids=set(shot.get('characters') or [])
    refs=[style_url] if isinstance(style_url,str) and style_url.startswith('https://') else []
    for c in project.get('cast',[]):
        if c.get('id') in ids and c.get('reference_url','').startswith('https://'):
            refs.append(c['reference_url'])
    for url in shot.get('reference_image_urls') or []:
        if url.startswith('https://') and url not in refs:refs.append(url)
    if len(refs)>4:
        raise ValueError('Zbyt wiele referencji Sogni dla ujęcia. Limit adaptera to 4 (STYLE + do trzech postaci); usuń dodatkowe linki ręczne.')
    return refs

def prepare_for_sogni(project,shot,style_url=None):
    prepared=copy.deepcopy(shot)
    prepared['prompt']=render_prompt(project,shot)
    prepared['cast_instruction']=''
    prepared['reference_image_urls']=shot_provider_refs(project,shot,style_url)
    # An approved first frame already carries identity and style. I2V does not
    # accept loose R2V references in the current adapter; don't mix the modes.
    if prepared.get('video_model')=='minimax-h3-fasth3-i2v-turbo' and prepared.get('image_url'):
        prepared['reference_image_urls']=[]
    if prepared['reference_image_urls'] and str(shot.get('video_model','')).endswith('t2v-turbo'):
        prepared['video_model']='minimax-h3-fasth3-r2v-turbo'
    return prepared

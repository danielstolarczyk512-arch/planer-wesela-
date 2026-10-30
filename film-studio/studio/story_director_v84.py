"""Local dramaturgy analysis and cost-free shot planning. Flags, not quality guarantees."""

def review_story(project):
    shots=project.get('shots') or []
    issues=[];suggestions=[]
    duration=float(project.get('duration') or 0)
    dialogue=[s for s in shots if str(s.get('dialogue') or '').strip()]
    ui=[s for s in shots if s.get('mode')=='ui']
    if not dialogue:issues.append('Brak dialogów — scenariusz przypomina niemy storyboard.')
    for shot in dialogue:
        words=len(str(shot.get('dialogue','')).split())
        if words/max(0.5,float(shot.get('duration') or .5))>2.8:
            issues.append(str(shot.get('id'))+': kwestia może być za długa na przydzielone ujęcie — zmierz zatwierdzone audio.')
    if ui and duration and min(s['start'] for s in ui)>duration*.25:issues.append('Prawdziwy interfejs produktu pojawia się po 25% filmu.')
    if not ui:issues.append('Brakuje nagrania rzeczywistego interfejsu aplikacji.')
    recent=[]
    for s in shots:
        camera=str(s.get('camera','')).lower()
        group=('close-up' if 'close-up' in camera else 'wide' if 'wide' in camera else 'ui' if s.get('mode')=='ui' else 'medium')
        recent.append(group)
        if len(recent)>=3 and len(set(recent[-3:]))==1 and group!='ui':
            issues.append('Trzy podobne plany pod rząd w okolicy '+str(s.get('id')))
    if not any('puent' in str(s.get('beat','')).lower() or 'karteczk' in str(s.get('beat','')).lower() for s in shots):
        suggestions.append('Dodaj powracający gag i jego zakończenie.')
    if any(s.get('dialogue') and not s.get('speaker') for s in shots):issues.append('Kwestia bez przypisanego mówcy.')
    suggestions+=['Zatwierdź wymowę i ekspresję każdej kwestii przed Sogni Audio-to-Video.',
                  'Nie wydłużaj materiału źródłowego do docelowego czasu; tnij na reakcjach i gestach.',
                  'Dla ujęć dialogowych wybieraj czytelną twarz zamiast długiego obrotu 360°.']
    return {'version':'8.4.0','offline':True,'calls_to_sogni':0,'shot_count':len(shots),
       'dialogue_count':len(dialogue),'first_real_ui_second':min((s['start'] for s in ui),default=None),
       'issues':issues,'suggestions':suggestions,'requires_human_review':True}

def render_plan(project,jobs=()):
    """Plan independent from provider. Never calls a billable API."""
    byshot={}
    for j in jobs:
        if j.get('status') in ('completed','queued','running','submitted','submitting','submission_uncertain'):
            byshot[(j.get('shot_id'),j.get('kind','video'))]=j
    rows=[];total=0;reuse=0
    for s in project.get('shots') or []:
        kind='video' if s.get('mode')=='t2v' else 'manual_ui' if s.get('mode')=='ui' else 'overlay'
        previous=byshot.get((s.get('id'),'video'))
        if kind=='video':
            sec=float(s.get('generation_seconds') or 0)
            if not previous:total+=sec
            else:reuse+=sec
        else:sec=0
        rows.append({'shot_id':s.get('id'),'kind':kind,'target_seconds':s.get('duration'),
           'source_generation_seconds':sec,'priority':'P0' if s.get('dialogue') or s.get('mode')=='ui' else 'P1',
           'existing_job':previous.get('id') if previous else None,
           'action':'reuse_or_check' if previous else 'review_and_render' if kind=='video' else 'record_real_ui' if kind=='manual_ui' else 'local_design'})
    rows.sort(key=lambda r:(r['priority'],r['shot_id']))
    return {'version':'8.4.0','offline':True,'target_duration_seconds':project.get('duration'),
       'new_video_source_seconds':round(total,2),'previously_submitted_source_seconds':round(reuse,2),
       'new_video_jobs':sum(r['kind']=='video' and not r['existing_job'] for r in rows),
       'cost_unknown':True,'does_not_reserve_subscription_capacity':True,'shots':rows}

def continuity_report(project):
    """Check metadata/approvals only, never pretend to recognize a face."""
    items=[]
    for s in project.get('shots',[]):
        if s.get('mode')!='t2v':continue
        warnings=[]
        if not s.get('scene_bible'):warnings.append('Brak Scene Bible')
        if not s.get('v82_frame_approval'):warnings.append('Brak ręcznie zatwierdzonej klatki')
        if not s.get('qc_approved'):warnings.append('Nieprzejrzany gotowy klip')
        if s.get('dialogue'):
            if not s.get('v7_lips_approved'):warnings.append('Niezaakceptowany ruch ust')
            if not s.get('v7_voice'):warnings.append('Brak zatwierdzonego nagrania audio-first')
        items.append({'shot_id':s.get('id'),'warnings':warnings,'style_identity_verified_automatically':False})
    return {'version':'8.4.0','items':items,'requires_human_review':True,
            'note':'Kontrola metadanych i decyzji człowieka; nie rozpoznaje twarzy ani fonemów.'}

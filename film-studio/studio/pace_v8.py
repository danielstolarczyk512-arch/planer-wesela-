"""V8 film rhythm, shot variety and product placement review (offline)."""
from __future__ import annotations


def audit(project):
    shots=project.get('shots') or []
    duration=float(project.get('duration') or sum(float(s.get('duration',0)) for s in shots))
    if duration<=0:raise ValueError('Brak poprawnego czasu projektu')
    issues=[];suggestions=[];timeline=[]
    first_product=None;static_time=0;dialogue_time=0
    prev='';same=0;start=0.0
    for shot in shots:
        t=float(shot.get('duration') or 0)
        if t<=0:continue
        label=str(shot.get('shot_role') or shot.get('camera') or shot.get('function') or 'nieopisane').lower().strip()
        mode=shot.get('mode')
        dialogue=bool(str(shot.get('dialogue') or '').strip() or shot.get('v7_voice'))
        if mode=='ui' and first_product is None:first_product=start
        if dialogue:dialogue_time+=t
        if t>6.0 and not dialogue and mode!='ui':
            issues.append({'level':'warning','shot':shot.get('id'),'message':'Długie ujęcie bez dialogu; rozważ zbliżenie, detal lub reakcję'})
        if t>8.0 and mode=='ui':
            issues.append({'level':'warning','shot':shot.get('id'),'message':'Długa prezentacja UI. Pokaż krótsze czynności i reakcje'})
        if label==prev:same+=1
        else:same=1
        if same>=3:issues.append({'level':'warning','shot':shot.get('id'),'message':'Trzeci podobny plan z rzędu; zmień wielkość kadru lub kąt'})
        if t>=5.5 and not dialogue:static_time+=t
        timeline.append({'shot_id':shot.get('id'),'start':round(start,2),'end':round(start+t,2),
                         'duration':t,'mode':mode,'has_dialogue':dialogue,'framing':label})
        prev=label;start+=t
    if first_product is None:
        issues.append({'level':'critical','message':'Brak autentycznej prezentacji produktu w storyboardzie'})
    elif first_product>duration*.45:
        issues.append({'level':'warning','message':f'Pierwsze UI dopiero w {first_product:.1f} s ({first_product/duration:.0%} filmu)'})
    if not shots:issues.append({'level':'critical','message':'Projekt nie ma ujęć'})
    suggestions=[
        'Rozbij długie dialogi na zbliżenie mówiącego, reakcję i plan wspólny — osobne rendery.',
        'Nie przyspieszaj głosów mechanicznie: skróć pauzy i tnij w punktach dramaturgicznych.',
        'Wstaw prawdziwe UI w ciągu pierwszej połowy reklamy oraz pokaż kliknięcie i rezultat.',
        'Stosuj J-cut i L-cut tylko po sprawdzeniu synchronizacji konkretnej sceny.',
        '360 stosuj do odsłaniania planu, nie w obracającym się zbliżeniu mówiącej twarzy.'
    ]
    return {'duration':duration,'shots':len(shots),'first_product_second':first_product,
            'first_product_fraction':round(first_product/duration,3) if first_product is not None else None,
            'dialogue_seconds':round(dialogue_time,2),'long_non_dialogue_seconds':round(static_time,2),
            'timeline':timeline,'issues':issues,'suggestions':suggestions,
            'automated_review_only':True,'film_watched_or_listened':False}


def suggest_cuts(project):
    """Non-destructive trim proposals; never cuts voice footage automatically."""
    plan=[]
    for s in project.get('shots') or []:
        t=float(s.get('duration') or 0)
        if t<=0:continue
        if s.get('v7_voice') or str(s.get('dialogue') or '').strip():
            plan.append({'shot_id':s.get('id'),'trim_seconds':0,'reason':'Dialog: nie tnij bez kontroli mowy'})
        elif t>5:
            plan.append({'shot_id':s.get('id'),'trim_seconds':round(min(t-3.5,t*.25),2),
                         'reason':'Proponowany skrót bez automatycznej zmiany projektu'})
    return {'proposals':plan,'applied':False,'requires_editorial_review':True}

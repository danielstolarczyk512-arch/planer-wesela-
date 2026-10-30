"""V8.5 conservative editorial diagnostics (never claims to see acting or identity)."""
from __future__ import annotations

from studio import timeline_v85


def review(root, project):
    shots=project.get('shots') or []
    total=timeline_v85.project_duration(project)
    problems=[];secs=0.0;last=None;repeat=0
    outro=0.0;product=None
    for shot in shots:
        dur=float(shot.get('duration') or 0)
        sid=shot.get('id');mode=shot.get('mode')
        framing=str(shot.get('shot_role') or shot.get('camera') or shot.get('function') or '').lower()
        if mode=='ui' and product is None:product=secs
        if any(x in framing for x in ('logo','outro','endcard','plansza końcowa')):outro+=dur
        if 'close' in framing or 'portret' in framing or 'zbliżenie' in framing or 'reaction' in framing:
            if dur>=3.6 and total<=30:problems.append({'shot':sid,'severity':'warning','message':f'Portret/reakcja trwa {dur:.1f} s w krótkiej reklamie. Rozważ kontrplan.'})
        if framing==last:repeat+=1
        else:repeat=1
        if repeat>=3:problems.append({'shot':sid,'severity':'warning','message':'Trzy podobnie opisane kadry z rzędu'})
        if mode=='ui' and dur>=5 and total<=30:problems.append({'shot':sid,'severity':'warning','message':'UI w krótkiej reklamie powinno pokazać jedną czytelną czynność i rezultat'})
        secs+=dur;last=framing
    if total<=30 and outro>2.1:problems.append({'shot':None,'severity':'warning','message':f'Plansza końcowa zajmuje {outro:.1f} s — sprawdź CTA'})
    if product is None:problems.append({'shot':None,'severity':'critical','message':'Brak realnego pokazu aplikacji'})
    elif total<=30 and product>total*.55:problems.append({'shot':None,'severity':'warning','message':'Aplikacja pojawia się za późno'})
    audio=timeline_v85.review(root,project)
    return {'version':'8.5.0','duration':total,'shot_count':len(shots),'first_ui':product,
       'outro_seconds':round(outro,2),'issues':problems,'audio':audio,
       'subtitles_rely_on_approved_audio':True,
       'manual_review_required':['zgodność twarzy i stylu','ruch ust względem fonemów',
                                  'emocje aktorskie','komediowe tempo','czytelność prawdziwego UI'],
       'no_generations_triggered':True}

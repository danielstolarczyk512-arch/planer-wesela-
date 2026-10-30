"""Editorial lint on shot timeline; explanatory findings, not fictitious aesthetic scoring."""
def audit(project):
    shots=project.get('shots') or []; problems=[];notes=[]
    if project.get('storyboard_stale'):problems.append('Scenariusz i storyboard są w innych wersjach')
    if len(shots)<8:notes.append('Mniej niż 8 ujęć: sprawdź, czy reklama nie jest zbyt statyczna')
    if not shots:return {'blocking':['Brak storyboardu'],'recommendations':notes,'ready':False}
    elapsed=0.0;ui=False;payoff=False;cta=False
    for i,s in enumerate(shots):
        start=float(s.get('start',elapsed));duration=float(s.get('duration',0))
        if duration<=0:problems.append(f'{s.get("id")}: czas musi być dodatni')
        if abs(start-elapsed)>.15:problems.append(f'{s.get("id")}: luka lub nakładanie na osi czasu')
        if duration>4.5 and s.get('mode')=='t2v':notes.append(f'{s.get("id")}: długie ujęcie AI ({duration:g}s), rozważ przebitkę')
        if s.get('mode')=='ui':ui=True
        if s.get('shot_role')=='payoff':payoff=True
        if s.get('mode')=='overlay':cta=True
        elapsed=start+duration
    if not ui:problems.append('Brakuje prawdziwego UI')
    if not payoff:notes.append('Brak czytelnej wizualnej puenty')
    if not cta:notes.append('Brak planszy CTA')
    if abs(elapsed-float(project.get('duration',elapsed)))>.2:problems.append('Oś czasu nie zgadza się z długością reklamy')
    return {'blocking':problems,'recommendations':notes,'ready':not problems}

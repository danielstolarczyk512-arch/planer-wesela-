"""Downloadable production handoff bundle; no generated media is faked."""
import csv
import io
import json
import zipfile

from .engine import validate_story


def package(project,jobs):
    out=io.BytesIO()
    prefix='film_'+project['id'][:8]+'/'
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
        def add(name,content):z.writestr(prefix+name,content)
        add('projekt.json',json.dumps({'project':project,'jobs':jobs},ensure_ascii=False,indent=2))
        add('scenariusz.txt',project.get('script','Brak scenariusza'))
        add('kontrola_jakosci.txt','\n'.join(validate_story(project)) or 'Brak znanych problemów strukturalnych. Wciąż wymagana kontrola wizualna i produktowa.')
        buf=io.StringIO();w=csv.writer(buf)
        w.writerow(['id','start_s','montaz_s','generacja_s','typ','funkcja','obraz','kamera','dialog','model','url_klipu'])
        for s in project.get('shots',[]):w.writerow([s.get(k,'') for k in ['id','start','duration','generation_seconds','mode','function','beat','camera','dialogue','video_model','media_url']])
        add('ujecia.csv',buf.getvalue().encode('utf-8-sig'))
        edl=[]
        for s in project.get('shots',[]):
            edl.append({'id':s['id'],'start':s['start'],'duration':s['duration'],'source':s.get('media_url'), 'mode':s['mode']})
            add('prompty/'+s['id']+'.txt',s.get('prompt',''))
        add('edl.json',json.dumps({'format':project['format'],'fps':24,'clips':edl},ensure_ascii=False,indent=2))
        add('CZYTAJ.txt','To jest paczka produkcyjna. Pliki ujęć są referencjami / URL; nie są domniemanymi ukończonymi filmami. Do montażu końcowego wymagane są prawdziwe klipy i nagranie interfejsu aplikacji.\n')
    out.seek(0);return out.getvalue()

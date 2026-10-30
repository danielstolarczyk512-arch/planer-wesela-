"""Offline visual contact sheets comparing real clip frames to approved style.

This is a viewing aid, not automatic identity proof. Requires FFmpeg and Pillow.
"""
import io
import subprocess
import tempfile
from pathlib import Path


def contact_sheet(master,clip):
    from PIL import Image, ImageDraw, ImageOps
    master=Path(master);clip=Path(clip)
    if not master.is_file() or not clip.is_file():raise FileNotFoundError('Brak wzorca lub wideo')
    cmd=['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(clip)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    if r.returncode:raise ValueError('Nie można zbadać czasu klipu')
    t=float(r.stdout.strip());times=[max(0,t*p) for p in (.12,.5,.86)]
    width,height=340,430
    canvas=Image.new('RGB',(4*width,500),'#1c1c1e');d=ImageDraw.Draw(canvas)
    with Image.open(master) as m:
        thumb=ImageOps.contain(m.convert('RGB'),(width-20,height));canvas.paste(thumb,((width-thumb.width)//2,35))
    d.text((20,10),'MASTER - styl',fill='white')
    with tempfile.TemporaryDirectory() as folder:
        for i,pos in enumerate(times,1):
            outfile=Path(folder)/f'f{i}.png'
            p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',f'{pos:.3f}',
                '-i',str(clip),'-frames:v','1','-vf','scale=600:-2',str(outfile)],capture_output=True,timeout=60)
            if p.returncode or not outfile.is_file():raise ValueError('Nie można pobrać klatek do porównania')
            with Image.open(outfile) as im:
                thumb=ImageOps.contain(im.convert('RGB'),(width-20,height));x=i*width+(width-thumb.width)//2
                canvas.paste(thumb,(x,35))
            d.text((i*width+20,10),f'{int(pos*100)/100:.2f}s',fill='white')
    d.text((20,472),'PORÓWNANIE DO OCENY CZŁOWIEKA — nie jest automatycznym rozpoznawaniem postaci.',fill='#dedede')
    buf=io.BytesIO();canvas.save(buf,format='PNG');return buf.getvalue()

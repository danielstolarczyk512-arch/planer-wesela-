"""Montaż wielościeżkowy OPERACJA STÓŁ 7 V2: 480 klatek @24 fps, osobne ścieżki (dialog M, dialog K, muzyka, SFX, otoczenie), napisy SRT."""
import json
import shutil
from pathlib import Path

from PIL import Image

from . import film5_build as B
from .film5_build import FPS, H, W, run

REC = Path('D:/film-studio/recordings_stol7/stol7v3.mp4')   # ostre nagranie 780x1388 (DSF 2)
ICON = Path('D:/aplikacjaweselna/frontend/public/icons/icon-512.png')
OLD_HOOK = Path('D:/film-studio/V5/Nasz_Dzien_Film_Studio_V5/data/film5/stol7/clips/o01.mp4')
TAKES = Path('D:/film-studio/OPERACJA_STOL_7_V2/POLISH_VOICES/takes')
# (id, rodzaj, klatki, źródło, t0 w źródle [s], dodatkowo)
PLAN = [
    ('s01', 'hook', 29, OLD_HOOK, 0.0),
    ('s02', 'ia2v', 72, 'v02', 0.0),
    ('s03', 'rec', 24, REC, 0.6),
    ('s04', 'ia2v', 54, 'v04', 0.0),
    ('s05', 'rec', 80, REC, 4.2),
    ('s06', 'clip', 20, 'v06m', 0.4),
    ('s07', 'clip', 20, 'v06', 0.8),
    ('s08', 'ia2v', 77, 'v07', 0.0),
    ('s09', 'clip', 31, 'v08', 0.5),
    ('s10', 'rec', 12, REC, 14.6),
    ('s11', 'end', 61, None, 0.0),
]
DIALOG = {'s02': ('on', 'M1_C', 'Stół siódmy. Mamy problem.'), 's04': ('ona', 'K1_C', 'Spokojnie. Mam plan.'), 's08': ('on', 'M2_B', 'A... stół ósmy?')}
SFX = [('hit', 0.04), ('buzz', 3.95), ('tap', 7.75), ('tap', 8.35), ('click', 8.4), ('chime', 9.0), ('chime', 10.85), ('chime', 17.0), ('chime', 17.75), ('chime', 18.6)]


def build(pr, out_dir):
    out_dir = Path(out_dir); wd = out_dir / 'work'; wd.mkdir(parents=True, exist_ok=True)
    starts = {}; f = 0; vids = []
    for sid, kind, n, src, t0 in PLAN:
        starts[sid] = f; f += n; d = n / FPS; v = wd / f'{sid}.mp4'
        if kind in ('hook', 'ia2v', 'clip'):
            clip = src if kind == 'hook' else pr.p('clips', src + '.mp4')
            run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t0:.3f}', '-i', clip, '-frames:v', n, '-vf', f'scale=-2:{H}:flags=lanczos,crop={W}:{H},fps={FPS},format=yuv420p', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', v])
            if kind == 'hook':   # napis nałożony w montażu (ostry), nie z modelu obrazu
                tp = wd / 'title.png'; B.title_png('OPERACJA: STÓŁ 7', tp); raw = wd / 's01_raw.mp4'; v.replace(raw)
                fc = "[1:v]format=rgba,fade=t=in:st=0.2:d=0.2:alpha=1[t];[0:v][t]overlay=0:0:shortest=1,format=yuv420p[o]"
                run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-loop', '1', '-framerate', FPS, '-t', f'{d:.3f}', '-i', tp, '-filter_complex', fc, '-map', '[o]', '-frames:v', n, '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', v])
        elif kind == 'rec':
            run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{t0:.3f}', '-i', src, '-frames:v', n, '-vf', f'scale={W}:{H}:flags=lanczos,fps={FPS},format=yuv420p', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', v])
        else:
            png = wd / 'end.png'; B.end_png('Nasz Dzień|Mniej stresu. Więcej Was.', png)
            im = Image.open(png).convert('RGB'); ic = Image.open(ICON).convert('RGBA').resize((300, 300), Image.LANCZOS)
            im.paste(ic, ((W - 300) // 2, 490), ic); im.save(png)
            run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', FPS, '-t', f'{d:.3f}', '-i', png, '-vf', 'format=yuv420p', '-frames:v', n, '-c:v', 'libx264', '-crf', '16', v])
        if sid == 's03':   # podpis do prawdziwego ekranu: fakt widoczny w aplikacji (Posadzeni: 3, bez miejsca: 4)
            cp = wd / 'cap.png'; B.caption_png('Czworo gości bez miejsca przy stole', cp, y0=1500); raw = wd / 's03_raw.mp4'; v.replace(raw)
            run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-i', cp, '-filter_complex', '[0:v][1:v]overlay=0:0,format=yuv420p[o]', '-map', '[o]', '-frames:v', n, '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', v])
        vids.append(v)
    total = f / FPS
    lst = wd / 'list.txt'; lst.write_text(''.join(f"file '{v.as_posix()}'\n" for v in vids), encoding='utf8')
    clean_v = wd / 'v_clean.mp4'; run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', clean_v])
    # ścieżki dźwięku
    tracks = {}
    for who in ('on', 'ona'):
        ev = []
        for sid, (w, take, text) in DIALOG.items():
            if w != who: continue
            pad = pr.p('audio', {'s02': 'v02', 's04': 'v04', 's08': 'v07'}[sid] + '_pad.wav'); ev.append((str(pad), starts[sid] / FPS))
        tracks[who] = wd / f'dialog_{who}.wav'; B.mix_events(ev, total, tracks[who], wd)
    sfx = []
    for kind, t in SFX:
        wv = wd / f'sfx_{kind}.wav'
        if not wv.exists(): B.synth(kind, wv)
        sfx.append((str(wv), t))
    tracks['sfx'] = wd / 'sfx.wav'; B.mix_events(sfx, total, tracks['sfx'], wd, gain=0.8)
    tracks['amb'] = wd / 'ambient.wav'
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'anoisesrc=d={total:.3f}:c=brown:a=0.05:r=48000', '-af', 'lowpass=f=500,volume=0.5,aformat=channel_layouts=stereo', tracks['amb']])
    music = pr.p('audio', 'spy20.audio')
    subs = []
    lines = {'s02': ('Stół siódmy. Mamy problem.', 0.2, 2.35), 's04': ('Spokojnie. Mam plan.', 0.2, 1.55), 's08': ('A… stół ósmy?', 0.2, 1.45)}
    for sid, (t, a, b) in lines.items():
        s0 = starts[sid] / FPS; subs.append((s0 + a, s0 + b, t))
    srt = out_dir / 'napisy.srt'
    def ts(x): h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60; return f'{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}'
    srt.write_text(''.join(f'{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n' for i, (a, b, t) in enumerate(subs, 1)), encoding='utf-8')
    # napisy wypalane (osobna wersja)
    sub_v = wd / 'v_sub.mp4'; cmd = ['ffmpeg', '-y', '-v', 'error', '-i', clean_v]; fc = []; last = '[0:v]'
    for i, (a, b, t) in enumerate(subs, 1):
        png = wd / f'sub{i}.png'; B.subtitle_png(t, png); cmd += ['-loop', '1', '-framerate', FPS, '-i', png]
        fc.append(f"[{i}:v]format=rgba[s{i}];{last}[s{i}]overlay=0:0:enable='between(t,{a:.2f},{b:.2f})':shortest=1[v{i}]"); last = f'[v{i}]'
    cmd += ['-filter_complex', ';'.join(fc), '-map', last, '-frames:v', f, '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', sub_v]; run(cmd)
    # miks: dialog M + K + SFX + otoczenie + muzyka z ducking → −16 LUFS, TP −1
    mix = wd / 'mix.wav'
    fc = ['[1:a]volume=0.5[amb]', '[2:a]volume=1.5[dm]', '[3:a]volume=1.5[dk]', '[dm][dk]amix=inputs=2:normalize=0:dropout_transition=0,asplit=2[dlg][dsc]', '[4:a]volume=0.85[sfx]',
          f'[5:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.55,atrim=0:{total:.3f},afade=t=out:st={total - 0.35:.2f}:d=0.35[m0]', '[m0][dsc]sidechaincompress=threshold=0.03:ratio=8:attack=30:release=400[mus]',
          '[amb][dlg][sfx][mus]amix=inputs=4:normalize=0:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=7,alimiter=limit=0.84:level=disabled,apad=whole_dur=%.3f,atrim=0:%.3f[a]' % (total, total)]
    run(['ffmpeg', '-y', '-v', 'error', '-i', clean_v, '-i', tracks['amb'], '-i', tracks['on'], '-i', tracks['ona'], '-i', tracks['sfx'], '-i', music, '-filter_complex', ';'.join(fc), '-map', '[a]', '-ar', '48000', '-ac', '2', mix])
    outs = {}
    for name, v in (('CLEAN', clean_v), ('SUBTITLES', sub_v)):
        o = out_dir / f'NASZ_DZIEN_OPERACJA_STOL_7_V2_{name}.mp4'
        run(['ffmpeg', '-y', '-v', 'error', '-i', v, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-r', FPS,
             '-vf', 'scale=in_range=pc:out_range=tv:out_color_matrix=bt709', '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709:range=tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-t', f'{total:.3f}', '-movflags', '+faststart', o])
        outs[name] = o
    shutil.copy(outs['SUBTITLES'], out_dir / 'NASZ_DZIEN_OPERACJA_STOL_7_V2_FINAL.mp4')
    tl = {'frames': f, 'fps': FPS, 'seconds': total, 'segments': [{'id': sid, 'kind': k, 'start_s': round(starts[sid] / FPS, 3), 'frames': n, 'source': str(s)} for sid, k, n, s, t0 in PLAN],
          'sfx': SFX, 'dialog': {k: list(v) for k, v in DIALOG.items()}, 'subtitles': subs}
    (out_dir / 'PROJECT_TIMELINE.json').write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding='utf-8')
    return outs, tl

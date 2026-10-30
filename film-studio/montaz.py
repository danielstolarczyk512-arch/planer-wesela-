#!/usr/bin/env python3
"""V4: shot-by-shot EDL with source in/out, 1080p output, voice-safe mix and LUFS.

All clips must exist. Never substitutes simulated footage for real Sogni or product UI.
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from qc.video import inspect_shot
from studio import product_demo_v8, timeline_v85

RESOLUTIONS={'9:16':(1080,1920),'16:9':(1920,1080),'1:1':(1080,1080)}

def probe_format(value,quality):
    if value not in RESOLUTIONS:raise ValueError('Nieobsługiwany format filmu')
    if quality not in ('draft','final'):raise ValueError('Nieznana jakość montażu')
    w,h=RESOLUTIONS[value]
    if quality=='draft':w,h=round(w/3/2)*2,round(h/3/2)*2
    return w,h

def run(*cmd):
    p=subprocess.run(list(cmd),capture_output=True,text=True,timeout=600)
    if p.returncode:raise RuntimeError('FFmpeg: '+(p.stderr[-1800:] or 'nieznany błąd'))

def make_edl(project):
    if project.get('storyboard_stale'):raise ValueError('Nieaktualny storyboard: najpierw synchronizacja')
    shots=project.get('shots') or []
    if not shots:raise ValueError('Brak ujęć')
    edl=[];cursor=0.0
    for shot in shots:
        sid=shot.get('id','')
        if not (sid.startswith('S') and sid[1:].isdigit() and len(sid)<=8):raise ValueError('Zły shot_id')
        dur=float(shot.get('duration',0));source_in=float(shot.get('in_point',0))
        if dur<=0 or source_in<0:raise ValueError('Niedozwolony czas na osi montażowej')
        if abs(float(shot.get('start',cursor))-cursor)>.25:
            raise ValueError('W osi montażowej istnieje luka lub nakładanie '+sid)
        edl.append({'shot_id':sid,'start':round(cursor,3),'in':source_in,'out':round(source_in+dur,3),
                    'shot_role':shot.get('shot_role') or shot.get('function',''),
                    'dialogue_id':shot.get('dialogue_id'), 'continuity_id':shot.get('continuity_id'),
                    'assets':[sid+'.mp4'], 'approved':bool(shot.get('qc_approved'))})
        cursor+=dur
    return edl

def _multitrack_v85(joined, output, project, root, music, total):
    """Audio mixed once over the full film; speech survives individual video cuts."""
    cue_list=timeline_v85.cues(root,project,require_approved=True)
    cfg=project.get('v85_audio_mix') or {}
    if not cue_list and cfg.get('replace_clip_audio'):
        raise ValueError('V8.5: nie wyciszaj oryginału bez zatwierdzonych dialogów')
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(joined)]
    filters=['[0:a]aresample=48000,volume='+('0' if cfg.get('replace_clip_audio') else '1')+'[b]']
    streams=['[b]']
    for i,c in enumerate(cue_list,1):
        cmd+=['-i',str(c['file'])]
        delay=max(0,round(c['start']*1000))
        filters.append(f'[{i}:a]aresample=48000,atrim=duration={c["duration"]:.3f},'
                       f'volume=1,adelay={delay}:all=1[v{i}]')
        streams.append(f'[v{i}]')
    if music:
        if not Path(music).is_file():raise FileNotFoundError('Brak legalnej ścieżki muzycznej')
        idx=1+len(cue_list)
        cmd+=['-stream_loop','-1','-i',str(music)]
        filters.append(f'[{idx}:a]aresample=48000,atrim=duration={total:.3f},volume=0.12[bg]')
        streams.append('[bg]')
    filters.append(''.join(streams)+f'amix=inputs={len(streams)}:duration=first:normalize=0,'
                   'loudnorm=I=-16:TP=-1:LRA=7:linear=false,alimiter=limit=0.89[aout]')
    cmd+=['-filter_complex',';'.join(filters),'-map','0:v:0','-map','[aout]','-c:v','copy',
          '-c:a','aac','-b:a','192k','-ar','48000','-ac','2',
          '-t',f'{total:.3f}','-movflags','+faststart',str(output)]
    run(*cmd)
    if cfg.get('subtitles',True):
        srt=timeline_v85.srt_from_cues(cue_list,total)
        if srt:
            Path(output).with_suffix('.srt').write_text(srt,encoding='utf-8')
    return len(cue_list)

def render(project_file,clips_folder,output,music=None,quality='final'):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('Zainstaluj bezpłatny FFmpeg i FFprobe do montażu MP4')
    project=project_file if isinstance(project_file,dict) else json.loads(Path(project_file).read_text(encoding='utf8'))
    if 'project' in project:project=project['project']
    edl=make_edl(project)
    if project.get('v7_enabled'):
        for shot in project.get('shots',[]):
            if shot.get('mode')=='t2v' and (str(shot.get('dialogue') or '').strip() or shot.get('v7_voice')):
                if not (shot.get('v7_voice') or (shot.get('v85_audio') or {}).get('approved')) or not shot.get('v7_lips_approved'):
                    raise ValueError('V7: brak zatwierdzonej polskiej mowy i synchronizacji ust dla '+shot['id'])
    if project.get('v8_enabled'):
        for shot in project.get('shots',[]):
            if shot.get('v8_voice_variants') and not shot.get('v8_voice_approved_id'):
                raise ValueError('V8: niezatwierdzony polski głos '+shot['id'])
            if shot.get('v8_product_frame') and not shot.get('qc_approved'):
                raise ValueError('V8: ekran UI po zmianie kadrowania wymaga ponownej akceptacji '+shot['id'])
    width,height=probe_format(project.get('format','9:16'),quality)
    clips_folder=Path(clips_folder).resolve()
    if project.get('v4_quality_mode'):
        for shot in project.get('shots',[]):
            if not shot.get('qc_approved'):
                raise ValueError('V4: wymagane obejrzenie i zatwierdzenie ujęcia '+shot['id'])
            if shot['mode']=='ui' and not shot.get('ui_provenance',{}).get('user_confirmed_real_ui'):
                raise ValueError('V4: brak potwierdzonego nagrania autentycznego interfejsu')
    clips=[];warnings=[]
    for row,shot in zip(edl,project['shots']):
        src=clips_folder/(row['shot_id']+'.mp4')
        if not src.is_file():raise FileNotFoundError('Brakuje klipu: '+row['shot_id'])
        report=inspect_shot(src,shot)
        if report['issues']:raise ValueError(row['shot_id']+': '+'; '.join(report['issues']))
        warnings += [row['shot_id']+': '+w for w in report['warnings']]
        clips.append((src, row['in'], row['out']-row['in']))
    total=sum(x[2] for x in clips)
    if abs(total-float(project.get('duration',total)))>.2:raise ValueError('Nie zgadza się czas trwania filmu')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.srt').unlink(missing_ok=True)  # stale subtitles must not survive a new render
    with tempfile.TemporaryDirectory(prefix='nasz-dzien-v4-') as td:
        folder=Path(td);segments=[]
        for i,(src,source_in,duration) in enumerate(clips):
            dest=folder/f'shot_{i:03}.mp4'
            filt=(f'scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,'
                  f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,'
                  'fps=24,format=yuv420p,setsar=1')
            if project.get('v8_enabled') and project['shots'][i].get('mode')=='ui' and project['shots'][i].get('v8_product_frame'):
                plan=project['shots'][i]['v8_product_frame']
                if plan.get('source')!='verified_real_screen_capture':raise ValueError('V8: brak zatwierdzenia nagrania UI')
                filt=product_demo_v8.ffmpeg_filter(plan['zoom'],plan['focus']['x'],plan['focus']['y'],width,height)+',fps=24,format=yuv420p'
            sound=subprocess.run(['ffprobe','-v','error','-select_streams','a:0',
                       '-show_entries','stream=codec_type','-of','csv=p=0',str(src)],capture_output=True,text=True)
            has_audio=sound.returncode==0 and 'audio' in sound.stdout
            cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(source_in),'-i',str(src)]
            if not has_audio:cmd+=['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000']
            afade_out=max(0,duration-0.08)
            af=f'aresample=48000,apad,atrim=duration={duration:.3f},afade=t=in:st=0:d=0.06,afade=t=out:st={afade_out:.3f}:d=0.08'
            cmd+=['-t',str(duration),'-vf',filt,'-map','0:v:0','-map','0:a:0' if has_audio else '1:a:0',
                  '-af',af,'-c:v','libx264','-preset','medium' if quality=='final' else 'veryfast',
                  '-crf','19' if quality=='final' else '27','-pix_fmt','yuv420p',
                  '-c:a','aac','-b:a','160k','-ar','48000','-ac','2','-movflags','+faststart',str(dest)]
            run(*cmd);segments.append(dest)
        concat=folder/'clips.txt'
        concat.write_text(''.join("file '"+str(p).replace("'","'\\''")+"'\n" for p in segments),encoding='utf8')
        joined=folder/'joined.mp4'
        run('ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(joined))
        common=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(joined)]
        if project.get('v85_audio_mix',{}).get('enabled'):
            n_v85_cues=_multitrack_v85(joined,output,project,clips_folder.parents[2],music,total)
        elif music:
            if not Path(music).is_file():raise FileNotFoundError('Brak pliku legalnie pozyskanej muzyki')
            # Sidechain: dialogue/scene audio ducks background while speech is audible.
            ff=(f'[0:a]aresample=48000,asplit=2[voice][key];'
                f'[1:a]aresample=48000,volume=0.19,atrim=duration={total:.3f}[bg];'
                f'[bg][key]sidechaincompress=threshold=0.025:ratio=8:attack=20:release=380[duck];'
                f'[voice][duck]amix=inputs=2:duration=first:normalize=0,'
                f'loudnorm=I=-16:TP=-1:LRA=7:linear=false,alimiter=limit=0.89[aout]')
            run(*(common+['-stream_loop','-1','-i',str(music),'-filter_complex',ff,'-map','0:v:0',
                          '-map','[aout]','-c:v','copy','-c:a','aac','-b:a','192k',
                          '-t',str(total),'-movflags','+faststart',str(output)]))
        else:
            run(*(common+['-map','0:v:0','-map','0:a:0','-af',
                          'loudnorm=I=-16:TP=-1:LRA=7:linear=false,alimiter=limit=0.89',
                          '-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)]))
    return {'output':str(output),'seconds_requested':total,'shots':len(edl),
            'resolution':[width,height],'music_included':bool(music),'quality':quality,
            'edl':edl,'technical_warnings':warnings,
            'v85_audio_cues':n_v85_cues if project.get('v85_audio_mix',{}).get('enabled') else 0,
            'v85_subtitles':str(Path(output).with_suffix('.srt')) if Path(output).with_suffix('.srt').is_file() else None,
            'note':'1080p output is a container resolution, not guaranteed additional detail'}

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--project',required=True);ap.add_argument('--clips',required=True)
    ap.add_argument('--out',default='nasz_dzien_reklama_v4.mp4')
    ap.add_argument('--music');ap.add_argument('--quality',choices=['draft','final'],default='final')
    args=ap.parse_args()
    print(json.dumps(render(args.project,args.clips,args.out,args.music,args.quality),ensure_ascii=False,indent=2))

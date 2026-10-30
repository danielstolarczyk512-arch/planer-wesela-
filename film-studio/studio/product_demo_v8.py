"""Safe UI framing plans for real application recordings; never synthesizes fake UI."""
from __future__ import annotations


def plan(shot,scale=1.0,focus_x=0.5,focus_y=0.5,confirmed=False):
    if shot.get('mode')!='ui':raise ValueError('Ten moduł dotyczy wyłącznie prawdziwego interfejsu')
    if confirmed is not True or not (shot.get('ui_provenance') or {}).get('user_confirmed_real_ui'):
        raise ValueError('Najpierw zatwierdź autentyczność nagrania aplikacji')
    if not 1<=scale<=2.5 or not 0<=focus_x<=1 or not 0<=focus_y<=1:
        raise ValueError('Nieprawidłowa skala lub punkt fokusu')
    return {'mode':'real_screen_reframe','zoom':scale,'focus':{'x':focus_x,'y':focus_y},
      'source':'verified_real_screen_capture','faux_ui_allowed':False,
      'ffmpeg_filter':ffmpeg_filter(scale,focus_x,focus_y)}

def ffmpeg_filter(scale,focus_x,focus_y,width=1080,height=1920):
    """Produces crop after aspect-fill scaling for a vertical canvas; no fake side bars."""
    # Fit video into 1080x1920, zoom, crop; x/y always within bounds.
    w=round(width*scale/2)*2;h=round(height*scale/2)*2
    return (f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,'
      f'crop={width}:{height}:(in_w-{width})*{focus_x:.3f}:(in_h-{height})*{focus_y:.3f},setsar=1')

"""Optional, local visual-motion diagnostic for an *explicit user-selected* mouth ROI.
No face identification, no phoneme classifier and no automatic lip-sync guarantee.
"""
from __future__ import annotations

import math


def inspect_mouth(video, roi=(0.35,0.38,0.30,0.20),max_seconds=14):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {'available':False,'reason':'Do diagnostyki opcjonalnej zainstaluj opencv-python i numpy',
                'lip_sync_verified':False}
    x,y,w,h=map(float,roi)
    if not all(math.isfinite(q) for q in (x,y,w,h)) or not (0<=x<1 and 0<=y<1 and .03<=w<=1-x and .03<=h<=1-y):
        raise ValueError('Ustaw prostokąt ust jako ułamki X, Y, szerokość i wysokość (0–1)')
    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():raise ValueError('Nie można odczytać klipu')
    fps=cap.get(cv2.CAP_PROP_FPS) or 24
    total=cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    stride=max(1,int(round(fps/6)))
    duration=min(max_seconds,total/max(1,fps))
    scores=[];previous=None;idx=0
    try:
        while idx<min(total,int(duration*fps)):
            ok,frame=cap.read()
            if not ok:break
            if idx%stride:idx+=1;continue
            img=cv2.cvtColor(cv2.resize(frame,(320,320)),cv2.COLOR_BGR2GRAY)
            a,b,c,d=int(x*320),int(y*320),int((x+w)*320),int((y+h)*320)
            crop=img[b:d,a:c]
            if previous is not None and crop.shape==previous.shape:
                # Higher ROI pixel change can indicate motion, but also lighting or camera movement.
                scores.append(round(float(np.abs(crop.astype('float32')-previous.astype('float32')).mean()),3))
            previous=crop;idx+=1
    finally:cap.release()
    motion=round(sum(scores)/max(1,len(scores)),3)
    return {'available':True,'frames_compared':len(scores),'mean_absolute_pixel_change':motion,
            'mouth_roi':[x,y,w,h], 'lip_sync_verified':False,
            'interpretation':'Ruch pikseli w zaznaczonym obszarze, NIE synchronizacja fonemów. Niska wartość sugeruje statyczne usta; wysoka może wynikać z ruchu kamery.',
            'review_required':'Obejrzyj z dźwiękiem oraz sprawdź zgodność słów, ust i twarzy.'}

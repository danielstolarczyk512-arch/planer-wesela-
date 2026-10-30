"""Sogni REST adapter. V3 HARD RULE: ONLY subscription-covered work; never use token billing."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API='https://api.sogni.ai'
MODEL='qwen3.6-35b-a3b-gguf-iq4xs'
VIDEO_MODELS={'ltx25', 'minimax-h3-fasth3-t2v-turbo', 'minimax-h3-t2v', 'minimax-h3-t2v-balanced','minimax-h3-fasth3-r2v-turbo', 'minimax-h3-fasth3-i2v-turbo'}
# SECURITY: deny-by-default. No frontier vendor models (Seedance, Wan 3, etc.).
IMAGE_MODEL='krea-2-turbo'
IMAGE_EDIT_MODEL='krea-identity-edit'
LLM_MODELS={MODEL}
BILLING_MODE='subscription'

def subscription_guard(body, model=None):
    if body.get('billing_mode') != BILLING_MODE:
        raise ProviderError('Zablokowano operację poza planem Unlimited.',403)
    if body.get('token_type') == 'sogni':
        raise ProviderError('Token SOGNI nie jest dozwolony w trybie bez dodatkowych opłat.',403)
    if model is not None and model not in VIDEO_MODELS | LLM_MODELS | {IMAGE_MODEL, IMAGE_EDIT_MODEL}:
        raise ProviderError('Model nie jest na liście dopuszczonych w planie Unlimited.',403)
    return body


class ProviderError(Exception):
    def __init__(self,message,status=502,details=None):
        super().__init__(message)
        self.status=status
        self.details=details or {}

def key():
    return os.environ.get('SOGNI_API_KEY','').strip()

def request(method,path,data=None,extra_headers=None,timeout=35):
    secret=key()
    if not secret:raise ProviderError('Brak SOGNI_API_KEY w środowisku serwera.',503)
    if not path.startswith('/') or '..' in path or '://' in path:raise ProviderError('Nieprawidłowa ścieżka API',400)
    headers={'Authorization':'Bearer '+secret,'User-Agent':'NaszDzienFilmStudio/4.0 (+local)', 'Accept':'application/json'}
    if data is not None:headers['Content-Type']='application/json'
    headers.update(extra_headers or {})
    req=urllib.request.Request(API+path, data=json.dumps(data).encode('utf8') if data is not None else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            body=resp.read(4_000_000).decode('utf8')
            return resp.status,json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raw=e.read(100_000).decode('utf8',errors='replace')
        try:
            err=json.loads(raw)
            message=(err.get('error') or {}).get('message') if isinstance(err.get('error'),dict) else None
            message=message or err.get('message') or f'API zwróciło HTTP {e.code}'
            details=err.get('details',{})
        except Exception:
            message=f'API zwróciło HTTP {e.code}'
            details={}
        raise ProviderError(str(message).replace(secret,'[REDACTED]'),e.code,details) from None
    except (OSError,TimeoutError):
        raise ProviderError('Brak połączenia z Sogni. Sprawdź sieć, DNS i konfigurację serwera.',503) from None

def subscription_status():
    _,res=request('GET','/v1/subscriptions/status',timeout=15)
    info=res.get('data',{}).get('subscription') or {}
    return {'active':info.get('active') is True,
            'status':str(info.get('status','unknown'))[:50],
            'tier':str(info.get('tier') or info.get('planId') or 'unknown')[:60]}

def assert_active_subscription():
    info=subscription_status()
    if not info['active']:
        raise ProviderError('Brak aktywnego Sogni Unlimited. Nie wykonano operacji; Spark nie zostaną użyte.',403)
    return info

def account_check():
    _,res=request('GET','/v2/account/me',timeout=12)
    sub=subscription_status()
    return {'connected':True, 'email_verified':res.get('data',{}).get('emailVerified'),
            'account_access':'verified','subscription':sub,'billing_mode':'subscription'}

def chat(system,user,max_tokens=2400,model=MODEL):
    if len(user)>25000:raise ProviderError('Zbyt długi tekst wejściowy',400)
    if model not in LLM_MODELS:raise ProviderError('Ten model tekstowy nie jest zatwierdzony dla planu Unlimited.',403)
    body={'billing_mode':'subscription','token_type':'auto','model':model,'messages':[{'role':'system','content':system},{'role':'user','content':user}], 'sogni_tools':False,'sogni_tool_execution':False,'temperature':0.65,'max_tokens':max_tokens,'stream':False, 'chat_template_kwargs':{'enable_thinking':False}}
    subscription_guard(body,model)
    assert_active_subscription()
    _,reply=request('POST','/v1/chat/completions',body,timeout=120)
    choices=reply.get('choices') or []
    if not choices:raise ProviderError('Sogni nie zwróciło odpowiedzi tekstowej.')
    result=choices[0].get('message',{}).get('content','')
    if not isinstance(result,str) or not result.strip():raise ProviderError('Sogni zwróciło pusty tekst. Sprawdź model i limit tokenów.')
    return result,reply.get('usage',{})

def workflow_body(shot,confirm_cost=False,max_units=None,format='9:16'):
    model=shot.get('video_model') or 'minimax-h3-fasth3-t2v-turbo'
    if model not in VIDEO_MODELS:raise ProviderError('Niedozwolony lub nieobsługiwany model wideo',400)
    if shot.get('mode') != 't2v':raise ProviderError('Ujęcia UI/overlay nie są generowane przez Sogni.',400)
    if len(shot.get('prompt','')) < 30:raise ProviderError('Prompt jest zbyt krótki.',400)
    duration=float(shot.get('generation_seconds',5.2))
    if not 5.17<=duration<=15.08 and model.startswith('minimax'):raise ProviderError('H3 wymaga 5.17–15.08 sekundy.',400)
    args={'prompt':shot['prompt']+' '+shot.get('cast_instruction','')[:1400],'videoModel':model,'duration':duration,'aspectRatio':format}
    tool_name='generate_video'
    body={'input':{'title':f'Nasz Dzien | {shot["id"]}', 'steps':[{'id':'clip','toolName':tool_name,'arguments':args}]}, 'app_source':'nasz-dzien-film-studio-v4', 'token_type':'auto', 'billing_mode':'subscription','confirm_cost':bool(confirm_cost)}
    if model=='minimax-h3-fasth3-i2v-turbo':
        url=shot.get('image_url')
        if not isinstance(url,str) or not url.startswith('https://'):
            raise ProviderError('Najpierw wygeneruj i zatwierdź klatkę referencyjną (HTTPS).',400)
        body['input']['steps'][0]['toolName']='animate_photo'
        args['sourceImageIndex']=-1
        body['media_references']=[{'kind':'image','url':url}]
    refs=shot.get('reference_image_urls') or []
    if model.endswith('r2v-turbo') and not refs:
        raise ProviderError('Tryb R2V wymaga zapisanych referencji HTTPS postaci.',400)
    if refs:
        if not model.endswith('r2v-turbo'):raise ProviderError('Dodatkowe referencje wymagają modelu R2V.',400)
        if len(refs)>4:raise ProviderError('W tym interfejsie maks. 4 referencje.',400)
        if not all(isinstance(u,str) and u.startswith('https://') and len(u)<2000 for u in refs):raise ProviderError('Referencje muszą być adresami HTTPS.',400)
        body['media_references']=[{'kind':'image','url':u} for u in refs]
        args['referenceImageIndices']=[-i for i in range(1,len(refs)+1)]
    if max_units is not None:body['max_estimated_capacity_units']=float(max_units)
    subscription_guard(body,model)
    return body

def estimate(shot,format='9:16'):
    # Explicitly non-executing local preflight. Real capacity is UNKNOWN.
    body=workflow_body(shot,False,format=format)
    return {'estimated_capacity':None,'unit':'capacity units',
            'requires_confirmation':True,'billing_mode':'subscription',
            'source':'local_preflight','warning':'Brak bezpiecznej wyceny z API. Ta operacja nie kontaktuje się z Sogni; wybierz własny limit przed startem.'}

def start_render(shot,max_units,idem_key,format='9:16'):
    if not 0 < float(max_units) <= 100000:raise ProviderError('Podaj poprawny limit capacity units.',400)
    body=workflow_body(shot,True,max_units=max_units,format=format)
    assert_active_subscription()
    _,res=request('POST','/v1/creative-agent/workflows',body,extra_headers={'Idempotency-Key':idem_key},timeout=40)
    workflow=res.get('data',{}).get('workflow') or {}
    if not workflow.get('workflowId'):raise ProviderError('Serwer nie zwrócił identyfikatora zadania.')
    return workflow

def get_workflow(id):
    if not id.startswith('wf_') or len(id)>170:raise ProviderError('Nieprawidłowy identyfikator workflow',400)
    _,res=request('GET','/v1/creative-agent/workflows/'+urllib.parse.quote(id),timeout=30)
    return res.get('data',{}).get('workflow') or {}

def cancel(id):
    if not id.startswith('wf_') or len(id)>170:raise ProviderError('Nieprawidłowy identyfikator workflow',400)
    _,res=request('POST','/v1/creative-agent/workflows/'+urllib.parse.quote(id)+'/cancel',{},timeout=30)
    return res.get('data',{}).get('workflow') or {}


def image_body(shot,confirm_cost=False,max_units=None):
    if shot.get('mode')!='t2v':raise ProviderError('Dla tego ujęcia nie można generować klatki AI.',400)
    prompt=shot.get('prompt','').strip()
    if len(prompt)<30:raise ProviderError('Zbyt krótki prompt klatki.',400)
    refs=shot.get('v83_reference_urls')
    if refs is not None:
        if not isinstance(refs,list) or not 1<=len(refs)<=4 or any(not isinstance(u,str) or not u.startswith('https://') for u in refs):
            raise ProviderError('V8.3: wymagane 1–4 obrazowe referencje HTTPS',400)
        # The first reference is source geometry; remaining references carry style
        # and characters. Indices refer to the supplied image list (NOT prompt text).
        args={'prompt':'Edit this approved character reference into the requested scene; preserve facial geometry and style. '+prompt[:3000],
              'model':IMAGE_EDIT_MODEL,'sourceImageIndex':-1}
        if len(refs)>1:args['referenceImageIndices']=[-i for i in range(2,len(refs)+1)]
        tool='edit_image';model=IMAGE_EDIT_MODEL
    else:
        args={'prompt':'High-quality cinematic still frame, single coherent instant. '+prompt[:3000]+' '+shot.get('cast_instruction','')[:1400],
              'model':IMAGE_MODEL}
        tool='generate_image';model=IMAGE_MODEL
    body={'input':{'title':f'Nasz Dzien | keyframe {shot["id"]}',
         'steps':[{'id':'keyframe','toolName':tool,'arguments':args}]},
        'app_source':'nasz-dzien-film-studio-v83','token_type':'auto',
        'billing_mode':'subscription','confirm_cost':bool(confirm_cost)}
    if refs is not None:body['media_references']=[{'kind':'image','url':u} for u in refs]
    if max_units is not None:body['max_estimated_capacity_units']=float(max_units)
    subscription_guard(body,model)
    return body

def estimate_image(shot):
    image_body(shot,False)
    return {'estimated_capacity':None,'unit':'capacity units',
            'requires_confirmation':True,'billing_mode':'subscription',
            'source':'local_preflight','warning':'Brak wyceny bez uruchomienia workflow. Dopiero zatwierdzenie startuje generację.'}

def start_image(shot,max_units,idem_key):
    if not 0<float(max_units)<=100000:raise ProviderError('Błędny limit kosztu.',400)
    body=image_body(shot,True,max_units)
    assert_active_subscription()
    _,res=request('POST','/v1/creative-agent/workflows',body,extra_headers={'Idempotency-Key':idem_key},timeout=40)
    wf=res.get('data',{}).get('workflow') or {}
    if not wf.get('workflowId'):raise ProviderError('Brak identyfikatora workflow obrazu')
    return wf

# V5: upload local reference images through the documented two-step signed-image
# flow. Upload alone is NOT a video generation. Explicit opt-in from UI required.
def upload_reference_image(local_path, content_type='image/png'):
    import uuid
    from pathlib import Path
    file=Path(local_path)
    if not file.is_file() or file.stat().st_size>16*1024*1024:
        raise ProviderError('Brak pliku obrazu albo przekroczony limit 16 MB.',400)
    if content_type not in ('image/png','image/jpeg','image/webp'):
        raise ProviderError('Nieobsługiwany format referencji.',400)
    assert_active_subscription()
    job_id=str(uuid.uuid4())
    params=urllib.parse.urlencode({'type':'referenceImage','jobId':job_id,'contentType':content_type})
    _,meta=request('GET','/v1/image/uploadUrl?'+params,timeout=25)
    signed_url=(meta.get('data') or {}).get('uploadUrl')
    if not isinstance(signed_url,str) or not signed_url.startswith('https://'):
        raise ProviderError('Sogni nie zwróciło poprawnego podpisanego adresu przesyłania.',502)
    # A signed URL is opaque and may use a changing storage host. Never send the API key.
    signed_req=urllib.request.Request(signed_url,data=file.read_bytes(),method='PUT',
              headers={'Content-Type':content_type})
    try:
        with urllib.request.urlopen(signed_req,timeout=60) as r:
            if r.status not in (200,201,204):raise ProviderError('Przesyłanie referencji nie powiodło się.',502)
    except (urllib.error.URLError,TimeoutError,OSError):
        raise ProviderError('Błąd przesyłania obrazu na serwer Sogni.',503) from None
    _,answer=request('GET','/v1/image/downloadUrl?'+params,timeout=25)
    url=(answer.get('data') or {}).get('downloadUrl')
    if not isinstance(url,str) or not url.startswith('https://'):
        raise ProviderError('Sogni nie zwróciło adresu odczytu referencji.',502)
    return {'url':url,'synced_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            'expires_hint_hours':48,'job_id':job_id}

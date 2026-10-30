"""Provenance gate for real app footage. No automatic browser recording is claimed."""
from datetime import UTC, datetime
from urllib.parse import urlparse


def provenance(source_url,confirmed,description=''):
    parsed=urlparse(source_url)
    if not confirmed or parsed.scheme not in ('https','http') or not parsed.netloc:
        raise ValueError('Potwierdź autentyczne nagranie ekranu i podaj źródłowy adres aplikacji http(s).')
    if len(source_url)>500 or len(description)>1000:raise ValueError('Za długa informacja o nagraniu')
    return {'source_url':source_url,'description':description.strip(),'user_confirmed_real_ui':True,
            'captured_reviewed_at':datetime.now(UTC).isoformat(timespec='seconds')}

"""Reconciliation-first submission guard: no automatic retries of unknown state."""
ACTIVE={'submitting','submission_uncertain','queued','submitted','running','processing','pending','waiting','in_progress'}

def pending_for_shot(jobs,shot_id,kind):
    return [j for j in jobs if j.get('shot_id')==shot_id and j.get('kind','video')==kind
            and str(j.get('status','')).lower() in ACTIVE]

def require_safe_submission(jobs,shot_id,kind,quote_id):
    blocks=pending_for_shot(jobs,shot_id,kind)
    if blocks:
        j=blocks[0]
        raise ValueError('Istnieje aktywne/niepewne zlecenie '+str(j.get('id'))+
             ' dla '+shot_id+'. Sprawdź workflow_id lub wyjaśnij status; nie ponawiaj.')
    # Must be called under the server submission lock, not a race-prone read.
    return True

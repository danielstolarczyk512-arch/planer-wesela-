"""Single canonical cast for NEW projects; older project casts are not rewritten.
Visual identity is bound to approved image hashes from visual_lock_v82, never
inferred from text-only style prompts. Local-only, stdlib.
"""
from __future__ import annotations

import copy

from .personas import STARTER, STYLE_ID

VERSION='8.3.0'
DEFAULT_PERSONAS={'ONA':'11111111-1111-4111-8111-111111111111',
                  'ON':'22222222-2222-4222-8222-222222222222'}


def canonical_cast():
    return [dict(id=role, name=spec['name'], look=spec['look'], avoid=spec['avoid'],
                 personality=spec['personality'], persona_id=DEFAULT_PERSONAS[role],
                 style_id=STYLE_ID)
            for role,spec in [('ONA',STARTER['ona']),('ON',STARTER['on'])]]


def binding(project):
    """Returns immutable identity snapshot; review status stays explicit."""
    cast=project.get('cast') or canonical_cast()
    by_role={row.get('id'):row for row in cast if isinstance(row,dict)}
    # Detect contradictory legacy descriptions instead of silently overwriting.
    return {'version':VERSION,'style_id':STYLE_ID,
            'roles':{r:{'persona_id':by_role.get(r,{}).get('persona_id'),
                        'name':by_role.get(r,{}).get('name'),
                        'look':by_role.get(r,{}).get('look'),
                        'avoid':by_role.get(r,{}).get('avoid')}
                      for r in DEFAULT_PERSONAS},
            'approved_master_snapshot':copy.deepcopy(project.get('v82_visual_snapshot') or {}),
            'visual_lock_enabled':bool(project.get('v82_visual_lock'))}


def ensure_new_project(project):
    if not project.get('cast'):
        project['cast']=canonical_cast()
    project['character_bible_version']=VERSION
    return project

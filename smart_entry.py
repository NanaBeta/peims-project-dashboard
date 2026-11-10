"""Project-scoped suggestions and safe defaults for PEIMS Spreadsheet Studio.

Suggestions are convenience hints, not a shared directory. The demo never searches
other projects, stores suggestions on the server, or changes validation rules.
"""
from __future__ import annotations

from collections import Counter
import re

import pandas as pd

from sheet_engine import SHEET_KEYS, project_sheet

# Related fields can reuse values entered in another register *of the same project*.
CROSS_FIELD_SOURCES = {
    'owner': (('activities', 'owner'), ('actions', 'owner'),
              ('risks', 'owner'), ('documents', 'owner')),
    'assigned_to': (('rfis', 'assigned_to'), ('activities', 'owner'),
                    ('actions', 'owner'), ('documents', 'owner')),
    'raised_by': (('rfis', 'raised_by'), ('contractors', 'company')),
    'lead': (('contractors', 'lead'), ('activities', 'owner')),
    'discipline': (('rfis', 'discipline'), ('documents', 'discipline')),
    'supplier': (('procurement', 'supplier'), ('contractors', 'company')),
}

# Helpful generic options, not prescribed disciplines or business classifications.
PRESETS = {
    'discipline': ('Civil', 'Electrical', 'Mechanical', 'Plumbing',
                   'Structural', 'Instrumentation & Controls', 'Process',
                   'Environmental', 'Geotechnical', 'HSE'),
    'category': ('Schedule', 'Technical', 'Commercial', 'Cost', 'Safety',
                 'Environmental', 'Procurement', 'Resource', 'Quality'),
    'document_type': ('Drawing', 'Specification', 'Method statement',
                      'Schedule', 'Calculation', 'Report', 'Checklist'),
    'priority': ('Low', 'Medium', 'High', 'Critical'),
    'critical': ('No', 'Yes'),
}
STATUS_OPTIONS = {
    'actions': ('Open', 'In progress', 'Closed'),
    'risks': ('Open', 'Closed'),
    'procurement': ('Ordered', 'In transit', 'Delayed', 'Received', 'Cancelled'),
    'contractors': ('Active', 'At Risk', 'Complete', 'On Hold'),
    'rfis': ('Open', 'In Review', 'Answered', 'Closed'),
    'documents': ('Draft', 'For Review', 'Approved', 'Superseded'),
}
SUGGESTED_FIELDS = {
    'activities': ('owner',),
    'procurement': ('supplier', 'status', 'critical'),
    'risks': ('category', 'owner', 'status'),
    'actions': ('owner', 'priority', 'status', 'source'),
    'contractors': ('company', 'lead', 'status'),
    'rfis': ('discipline', 'raised_by', 'assigned_to', 'status', 'critical'),
    'documents': ('discipline', 'revision', 'status', 'owner', 'document_type'),
}


def suggestions(core: dict, workflows: dict, sheet: str, project_id: str,
                field: str, max_items: int = 80) -> list[str]:
    """Deduplicated recent-value suggestions, limited to *selected project*."""
    if field not in SUGGESTED_FIELDS.get(sheet, ()):  # do not suggest free narrative text
        return []
    sources = CROSS_FIELD_SOURCES.get(field, ((sheet, field),))
    if (sheet, field) not in sources:
        sources = ((sheet, field),) + sources
    counts: Counter[str] = Counter()
    canonical: dict[str, str] = {}
    for src_sheet, src_field in sources:
        frame = project_sheet(core, workflows, src_sheet, project_id)
        if src_field not in frame.columns:
            continue
        for v in frame[src_field].tolist():
            if pd.isna(v):
                continue
            v = str(v).strip()
            if not v or v.casefold() in ('nan', 'none', 'nat'):
                continue
            key = v.casefold()
            counts[key] += 1
            canonical.setdefault(key, v)
    for v in (STATUS_OPTIONS.get(sheet, ()) if field == 'status' else PRESETS.get(field, ())):
        key = v.casefold()
        canonical.setdefault(key, v)
        counts.setdefault(key, 0)
    return [canonical[k] for k in sorted(canonical, key=lambda k: (-counts[k], k))[:max_items]]


def new_record_id(core: dict, workflows: dict, sheet: str, project_id: str) -> str:
    """Generate a short, globally unique suggestion; final validator remains authority."""
    prefixes = {'activities':'ACT', 'procurement':'PO', 'risks':'RSK',
                'actions':'TASK', 'contractors':'CTR', 'rfis':'RFI', 'documents':'DOC'}
    if sheet not in prefixes:
        raise ValueError('This worksheet cannot create standalone records')
    key = SHEET_KEYS[sheet]
    current = (core if sheet in core else workflows)[sheet]
    used = set(current[key].astype(str))
    project_token = re.sub(r'[^A-Za-z0-9_-]', '-', project_id)[:20]
    prefix = f'{project_token}-{prefixes[sheet]}'
    for n in range(1, 10000):
        result = f'{prefix}-{n:03d}'
        if result not in used and len(result) <= 48:
            return result
    raise ValueError('No available ID; enter a unique record ID manually')

# Text inputs that a new record needs beyond low-level schema requirements.
REQUIRED_NEW_FIELDS = {
    'activities': ('activity', 'owner'),
    'procurement': ('item', 'supplier', 'status'),
    'risks': ('risk', 'category', 'owner', 'status'),
    'actions': ('action', 'owner', 'priority', 'status'),
    'contractors': ('company', 'scope', 'lead', 'status'),
    'rfis': ('subject', 'discipline', 'raised_by', 'assigned_to', 'status'),
    'documents': ('title', 'discipline', 'revision', 'owner', 'document_type', 'status'),
}


def validate_smart_inputs(sheet: str, row: dict) -> dict:
    """Prevent a blank chooser being saved as the literal string 'None'."""
    if sheet not in REQUIRED_NEW_FIELDS:
        raise ValueError('This worksheet does not support the quick-add form')
    clean = dict(row)
    for field in REQUIRED_NEW_FIELDS[sheet]:
        value = clean.get(field)
        if value is None or not str(value).strip() or str(value).strip().casefold() in ('none', 'nan'):
            raise ValueError(f'{field.replace("_", " ").title()} is required')
        clean[field] = str(value).strip()
    if sheet == 'risks':
        for key in ('probability', 'impact'):
            if clean.get(key) is None:
                raise ValueError(f'Select a {key} score from 1 to 5')
    return clean

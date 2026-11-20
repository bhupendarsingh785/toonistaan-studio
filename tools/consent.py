#!/usr/bin/env python3
"""Fail-closed consent ledger for ASTRA voice profiles.

This is an operator attestation, not identity/signature verification or legal advice.
"""
from __future__ import annotations
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2

def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def record_consent(profile_dir: str | Path, voice_name: str, consent_scope: str = 'speech_generation',
                   speaker_name: str = '', expires_at_utc: str | None = None) -> Path:
    if not consent_scope.strip(): raise ValueError('consent_scope khali nahi ho sakta')
    payload = {
        'schema_version': SCHEMA_VERSION, 'voice_profile': voice_name,
        'consent_status': 'active', 'attested_at_utc': datetime.now(timezone.utc).isoformat(),
        'speaker_name': speaker_name.strip(), 'attestation': 'Operator confirms the speaker is the operator or has explicitly authorized this voice use.',
        'scope': consent_scope.strip(), 'expires_at_utc': expires_at_utc,
        'revoked': False,
        'verification_note': 'Operator attestation only; not independent identity, signature, or legal verification.'
    }
    path = Path(profile_dir) / 'consent_record.json'; _atomic_json(path, payload); return path

def revoke_consent(profile_dir: str | Path, reason: str = 'speaker_request') -> Path:
    path = Path(profile_dir) / 'consent_record.json'
    if not path.is_file(): raise FileNotFoundError('consent_record.json nahi mila')
    try: payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: raise PermissionError('Consent record corrupt hai; profile blocked.') from exc
    payload.update(consent_status='revoked', revoked=True,
                   revoked_at_utc=datetime.now(timezone.utc).isoformat(), revocation_reason=reason)
    _atomic_json(path, payload); return path

def assert_consent_active(profile_dir: str | Path, required_scope: str = 'speech_generation') -> None:
    path = Path(profile_dir) / 'consent_record.json'
    if not path.is_file(): raise PermissionError('Consent record missing; fail-closed: voice profile blocked.')
    try: payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: raise PermissionError('Consent record unreadable/corrupt; voice profile blocked.') from exc
    if payload.get('schema_version') not in (1, SCHEMA_VERSION): raise PermissionError('Unknown consent schema; profile blocked.')
    if payload.get('revoked') or payload.get('consent_status') not in ('active', 'attested'):
        raise PermissionError('Is voice profile ki permission active nahi hai; generation blocked.')
    if required_scope and required_scope not in str(payload.get('scope', '')).split(','):
        raise PermissionError('Consent scope required generation ko allow nahi karta.')
    expiry = payload.get('expires_at_utc')
    if expiry:
        try:
            dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
            if dt.tzinfo is None: raise ValueError('timezone missing')
            if dt <= datetime.now(timezone.utc): raise PermissionError('Consent expire ho chuka hai; profile blocked.')
        except PermissionError: raise
        except Exception as exc: raise PermissionError('Consent expiry invalid; profile blocked.') from exc

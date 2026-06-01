# -*- coding: utf-8 -*-
import os
import json
import threading
import time
from datetime import datetime
from pathlib import Path


LOG_DIR = None


def _get_log_dir():
    global LOG_DIR
    if LOG_DIR is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        LOG_DIR = Path(base) / 'logs' / 'llm_conversations'
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def _cleanup_old_logs():
    log_dir = _get_log_dir()
    cutoff = time.time() - 24 * 3600
    for f in log_dir.glob('*.json'):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except Exception:
            pass


def log_conversation(operation, prompt, response, extra=None):
    try:
        log_dir = _get_log_dir()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"{ts}_{operation}.json"
        filepath = log_dir / filename

        entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'prompt': prompt,
            'prompt_length': len(prompt),
            'response': response,
            'response_length': len(response) if response else 0,
        }
        if extra:
            entry['extra'] = extra

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)

        _cleanup_old_logs()
    except Exception:
        pass

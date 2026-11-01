from __future__ import annotations

import hmac
import json
import math
import threading
import time

from ..data.database import connect, utc_now


class DeveloperMode:
    KEY = "developer_mode_attempts"

    def __init__(self, db_path):
        self.db_path = db_path
        self.enabled = False
        self.generation = 0
        self._lock = threading.RLock()

    def _record(self, db):
        row = db.execute("SELECT value FROM settings WHERE key=?", (self.KEY,)).fetchone()
        return json.loads(row['value']) if row else None

    def _write(self, db, record):
        db.execute("INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                   (self.KEY, json.dumps(record), utc_now()))

    def status(self):
        with self._lock, connect(self.db_path) as db:
            record = self._record(db)
            return dict(enabled=self.enabled,
                        retry_after=max(0, math.ceil((record or {}).get('blocked_until', 0) - time.time())))

    def _verify(self, password):
        # Commit failure counters before raising, so restarting cannot reset cooldown.
        with connect(self.db_path) as db:
            db.execute('BEGIN IMMEDIATE')
            record = self._record(db) or dict(failures=0, blocked_until=0)
            if record.get('blocked_until', 0) > time.time():
                raise ValueError("密碼錯誤次數過多，請稍後再試。")
            valid = False
            if isinstance(password, str) and len(password) <= 128:
                valid = hmac.compare_digest(password.encode('utf-8'), b'5830485')
            record['failures'] = 0 if valid else record.get('failures', 0) + 1
            record['blocked_until'] = time.time() + 60 if record['failures'] >= 5 else 0
            if record['failures'] >= 5:
                record['failures'] = 0
            self._write(db, record)
        if not valid:
            raise ValueError("密碼不正確。連續錯誤 5 次將暫停 60 秒。")

    def unlock(self, password):
        with self._lock:
            self._verify(password)
            self.enabled = True
            self.generation += 1
            return self.status()

    def lock(self):
        with self._lock:
            self.enabled = False
            self.generation += 1
            return self.status()

    def require(self, generation=None):
        with self._lock:
            if not self.enabled or (generation is not None and generation != self.generation):
                raise ValueError("此功能僅限開發人員，請先解鎖開發人員模式。")
            return self.generation

"""Local social evidence, OS credentials, and read-only platform adapters."""
from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone

from ..data.database import connect, utc_now
from .cloud_advisor import NoRedirect

PLATFORMS = {"facebook", "instagram", "threads"}


class SocialError(ValueError):
    def __init__(self, message, kind="error"):
        super().__init__(message)
        self.kind = kind


class SystemSecrets:
    def __init__(self, db_path):
        self.service = "AI Prompt Studio Social " + hashlib.sha256(str(db_path).encode()).hexdigest()[:16]

    def _call(self, action, key, value=None):
        import keyring
        from keyring.errors import KeyringError, PasswordDeleteError
        try:
            if action == "get":
                return keyring.get_password(self.service, key) or ""
            if action == "set":
                keyring.set_password(self.service, key, value)
            else:
                try:
                    keyring.delete_password(self.service, key)
                except PasswordDeleteError:
                    pass
        except KeyringError:
            raise ValueError("無法存取系統金鑰圈，請解鎖 Keychain／Windows 認證管理員後重試。") from None

    def get(self, key):
        return self._call("get", key)

    def set(self, key, value):
        self._call("set", key, value)

    def delete(self, key):
        self._call("delete", key)


def http_json(url, token="", params=None, payload=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise SocialError("平台回應過大，請稍後重試。")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise SocialError("平台回應格式不正確。")
        return result
    except urllib.error.HTTPError as exc:
        try:
            error = json.loads(exc.read(32768)).get("error", {})
            code = error.get("code") if isinstance(error, dict) else None
        except (ValueError, AttributeError):
            code = None
        if exc.code == 429 or code in {4, 17, 32, 613}:
            raise SocialError("平台限流，請稍後手動重試。", "rate_limited") from None
        if exc.code == 401 or code == 190:
            raise SocialError("授權已失效，請重新連接帳號。", "expired") from None
        if exc.code == 403 or code in {10, 200}:
            raise SocialError("缺少讀取權限，請檢查帳號管理權限並重新授權。", "permission") from None
        if exc.code == 400 and code == 100:
            raise SocialError("此項目或指標不適用目前 API／貼文類型。", "unsupported") from None
        raise SocialError(f"社群服務請求失敗（HTTP {exc.code}），請檢查授權服務設定。") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SocialError("社群服務連線失敗或逾時。") from None
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, SocialError):
            raise
        raise SocialError("平台回應格式不正確。") from None


class SocialData:
    def __init__(self, db_path, credentials=None, transport=None):
        self.db_path = db_path
        self.secrets = credentials or SystemSecrets(db_path)
        self.request = transport or http_json
        self._lock = threading.Lock()
        self._authorization = None
        self._candidates = None

    def config(self):
        with connect(self.db_path) as db:
            return dict(db.execute("SELECT name,value FROM social_config").fetchall())

    def settings(self):
        config = self.config()
        with connect(self.db_path) as db:
            accounts = [dict(row) for row in db.execute("SELECT * FROM social_accounts ORDER BY platform")]
        for account in accounts:
            if account["connected"] and account["expires_at"] and account["expires_at"] <= time.time():
                account["status"] = "expired"
        return {"service_url": config.get("service_url", ""), "accounts": accounts}

    def configure(self, service_url, connection_code):
        parsed = urllib.parse.urlsplit(str(service_url).strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("請輸入授權服務的 HTTPS 根網址。")
        service_url = str(service_url).strip().rstrip("/")
        old = self.config().get("service_url")
        if not connection_code and old != service_url:
            raise ValueError("新服務需填入部署時設定的連線碼。")
        if connection_code:
            if not isinstance(connection_code, str) or not 32 <= len(connection_code) <= 256:
                raise ValueError("連線碼應為部署時設定的 32–256 字元字串。")
            self.secrets.set("broker", connection_code)
        with connect(self.db_path) as db:
            db.execute("INSERT OR REPLACE INTO social_config VALUES('service_url',?)", (service_url,))
        self._authorization = self._candidates = None
        return self.settings()

    def begin(self, provider):
        if provider not in {"facebook", "threads"}:
            raise ValueError("不支援此登入平台。")
        if not self._lock.acquire(False):
            raise ValueError("社群作業進行中，請稍候。")
        try:
            config = self.config()
            url, code = config.get("service_url"), self.secrets.get("broker")
            if not url or not code:
                raise ValueError("請先設定授權服務網址與連線碼。")
            verifier = secrets.token_urlsafe(32)
            data = self.request(url + "/auth/start", code, payload={"provider": provider, "challenge": hashlib.sha256(verifier.encode()).hexdigest()})
            auth_url = data.get("authorization_url", "")
            target = urllib.parse.urlsplit(auth_url)
            if target.scheme != "https" or target.hostname not in {"www.facebook.com", "www.threads.net", "threads.net", "www.threads.com", "threads.com"}:
                raise ValueError("授權服務回傳的登入網址不正確。")
            self._authorization = (time.monotonic(), data["session_id"], verifier, url)
            self._candidates = None
            if not webbrowser.open(auth_url):
                raise ValueError("無法開啟系統瀏覽器，請確認預設瀏覽器設定。")
            return {"status": "pending"}
        finally:
            self._lock.release()

    def poll(self):
        if not self._lock.acquire(False):
            return {"status": "pending"}
        try:
            if self._candidates and time.monotonic() - self._candidates[0] < 600:
                return {"status": "ready", "accounts": self._candidate_list()}
            if not self._authorization or time.monotonic() - self._authorization[0] >= 600:
                self._authorization = self._candidates = None
                raise ValueError("登入已逾時，請重新連接。")
            _, session, verifier, url = self._authorization
            data = self.request(url + "/auth/claim", self.secrets.get("broker"), payload={"session_id": session, "verifier": verifier})
            if data.get("status") == "ready":
                accounts = data.get("accounts", [])
                if not isinstance(accounts, list) or any(a.get("platform") not in PLATFORMS or not a.get("access_token") or not re.fullmatch(r"[0-9]+", str(a.get("account_id", ""))) for a in accounts):
                    raise ValueError("授權服務回傳的帳號格式不正確。")
                if not accounts:
                    raise ValueError("沒有可用帳號，請確認粉專管理權限、IG 專業帳號連結及測試者設定。")
                version = data.get("graph_version", "")
                if any(a["platform"] != "threads" for a in accounts) and not re.fullmatch(r"v\d+\.\d+", version):
                    raise ValueError("授權服務尚未設定有效的 Graph API 版本。")
                with connect(self.db_path) as db:
                    if version:
                        db.execute("INSERT OR REPLACE INTO social_config VALUES('graph_version',?)", (version,))
                self._candidates = (time.monotonic(), accounts)
                self._authorization = None
                return {"status": "ready", "accounts": self._candidate_list()}
            if data.get("status") == "error":
                self._authorization = None
                raise ValueError("平台授權未完成，請檢查服務設定、帳號權限或重新登入。")
            return {"status": "pending"}
        finally:
            self._lock.release()

    def _candidate_list(self):
        return [{"key": str(i), "platform": a["platform"], "name": a["name"], "account_id": a["account_id"]} for i, a in enumerate(self._candidates[1])]

    def select_accounts(self, keys):
        with self._lock:
            if not self._candidates or time.monotonic() - self._candidates[0] >= 600:
                raise ValueError("帳號清單已過期，請重新登入。")
            if not isinstance(keys, list) or not keys:
                raise ValueError("請選擇帳號。")
            lookup = {str(i): a for i, a in enumerate(self._candidates[1])}
            if any(k not in lookup for k in keys):
                raise ValueError("帳號選擇不正確。")
            accounts = [lookup[k] for k in set(keys)]
            if len({a["platform"] for a in accounts}) != len(accounts):
                raise ValueError("每個平台只能選擇一個帳號。")
            previous = {a['platform']: a for a in self.settings()['accounts']}
            for a in accounts:
                self.secrets.set(a["platform"] + ":" + a["account_id"], a["access_token"])
            with connect(self.db_path) as db:
                for a in accounts:
                    db.execute("INSERT INTO social_accounts(platform,account_id,name,expires_at) VALUES(?,?,?,?) ON CONFLICT(platform) DO UPDATE SET account_id=excluded.account_id,name=excluded.name,expires_at=excluded.expires_at,connected=1,status='connected',synced_at=NULL",
                               (a["platform"], a["account_id"], a["name"], a.get("expires_at")))
            self._candidates = None
            for a in accounts:
                old = previous.get(a['platform'])
                if old and old['account_id'] != a['account_id']:
                    self.secrets.delete(a['platform'] + ':' + old['account_id'])
        return self.settings()

    def disconnect(self, platform):
        with self._lock, connect(self.db_path) as db:
            row = db.execute("SELECT * FROM social_accounts WHERE platform=?", (platform,)).fetchone()
            if row:
                self.secrets.delete(platform + ":" + row["account_id"])
                db.execute("UPDATE social_accounts SET connected=0,status='disconnected' WHERE platform=?", (platform,))
        return self.settings()

    def clear(self, platform):
        if platform not in PLATFORMS:
            raise ValueError("未知平台。")
        with self._lock, connect(self.db_path) as db:
            db.execute("DELETE FROM social_posts WHERE platform=?", (platform,))
            db.execute("DELETE FROM social_syncs WHERE platform=?", (platform,))
            # Runs can contain evidence from several platforms; clear all copies.
            db.execute("DELETE FROM marketing_runs")
            db.execute("UPDATE social_accounts SET synced_at=NULL WHERE platform=?", (platform,))
        return self.settings()

    def _graph(self, platform, path, token, params):
        if platform == "threads":
            base = "https://graph.threads.net"
        else:
            version = self.config().get("graph_version", "")
            if not re.fullmatch(r"v\d+\.\d+", version):
                raise ValueError("請重新連接帳號以設定 Graph API 版本。")
            base = "https://graph.facebook.com/" + version
        return self.request(base + "/" + path, token, params=params)

    def sync(self, platform):
        if platform not in PLATFORMS:
            raise ValueError("未知平台。")
        if not self._lock.acquire(False):
            raise ValueError("社群作業進行中，請稍候。")
        try:
            return self._sync(platform)
        except SocialError as exc:
            with connect(self.db_path) as db:
                db.execute("UPDATE social_accounts SET status=? WHERE platform=?", (exc.kind, platform))
            raise
        finally:
            self._lock.release()

    def _sync(self, platform):
        with connect(self.db_path) as db:
            row = db.execute("SELECT * FROM social_accounts WHERE platform=? AND connected=1", (platform,)).fetchone()
        if not row:
            raise ValueError("請先連接帳號。")
        token = self.secrets.get(platform + ":" + row["account_id"])
        if not token or (row["expires_at"] and row["expires_at"] <= time.time()):
            raise SocialError("授權已過期，請重新連接。", "expired")
        since = datetime.now(timezone.utc) - timedelta(days=30)
        edge, fields = {
            "facebook": ("posts", "id,message,created_time,permalink_url,attachments{media_type},reactions.limit(0).summary(true),comments.limit(0).summary(true),shares"),
            "instagram": ("media", "id,caption,timestamp,permalink,media_type,like_count,comments_count"),
            "threads": ("threads", "id,text,timestamp,permalink,media_type"),
        }[platform]
        params = {"fields": fields, "limit": 50}
        if platform != "instagram":
            params["since"] = int(since.timestamp())
        posts, seen, cursors = [], set(), set()
        limited = False
        for _ in range(20):
            page = self._graph(platform, row["account_id"] + "/" + edge, token, params)
            items = page.get("data", [])
            if not isinstance(items, list):
                raise SocialError("貼文清單格式不正確。")
            for item in items:
                published = str(item.get("timestamp", item.get("created_time", "")))
                try:
                    date = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if date.tzinfo is None:
                        raise ValueError()
                except ValueError:
                    continue
                if date < since:
                    continue
                item['_published_at'] = date.isoformat()
                post_id = str(item.get("id", ""))
                if not re.fullmatch(r"[0-9_]+", post_id) or post_id in seen:
                    continue
                seen.add(post_id)
                posts.append(item)
                if len(posts) == 100:
                    limited = True
                    break
            paging = page.get("paging", {})
            after = paging.get("cursors", {}).get("after")
            if limited or not paging.get("next") or not after or after in cursors:
                break
            cursors.add(after)
            params["after"] = after
        else:
            limited = True
        captured, warnings, normalized = utc_now(), [], []
        for item in posts:
            metrics, issues = {}, []
            if platform == "facebook":
                metrics = {"reactions": item.get("reactions", {}).get("summary", {}).get("total_count"), "comments": item.get("comments", {}).get("summary", {}).get("total_count"), "shares": item.get("shares", {}).get("count")}
                requested = ["post_media_view"]
            elif platform == "instagram":
                metrics = {"likes": item.get("like_count"), "comments": item.get("comments_count")}
                requested = ["views", "reach", "saved", "shares"]
            else:
                requested = ["views", "likes", "replies", "reposts", "quotes", "shares"]
            try:
                insights = self._graph(platform, str(item["id"]) + "/insights", token, {"metric": ",".join(requested)})
                self._read_metrics(insights, metrics)
            except SocialError as exc:
                if exc.kind in {"expired", "rate_limited"}:
                    raise
                issues.append(str(exc))
                if exc.kind == "unsupported" and len(requested) > 1:
                    for metric in requested:
                        try:
                            self._read_metrics(self._graph(platform, str(item["id"]) + "/insights", token, {"metric": metric}), metrics)
                        except SocialError as metric_error:
                            if metric_error.kind in {"expired", "rate_limited"}:
                                raise
                            issues.append(f"{metric}：{metric_error}")
            for name in requested:
                metrics.setdefault(name, None)
            metrics = {key: value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None for key, value in metrics.items()}
            warnings.extend(issues)
            attachment = (item.get("attachments", {}).get("data") or [{}])[0]
            normalized.append((item, metrics, issues, item.get("media_type") or attachment.get("media_type") or "TEXT"))
        result = {"count": len(normalized), "limited": limited, "captured_at": captured, "warnings": list(dict.fromkeys(warnings)), "period": "最近 30 天發布的貼文；指標為同步時的累積值"}
        with connect(self.db_path) as db:
            for item, metrics, issues, media_type in normalized:
                db.execute("INSERT INTO social_posts VALUES(?,?,?,?,?,?,?) ON CONFLICT(platform,post_id) DO UPDATE SET content=excluded.content,permalink=excluded.permalink,media_type=excluded.media_type", (platform, str(item["id"]), row["account_id"], str(item.get("message", item.get("caption", item.get("text", ""))))[:20000], str(item.get("permalink_url", item.get("permalink", ""))), item['_published_at'], media_type))
                source = {'content': str(item.get('message', item.get('caption', item.get('text', ''))))[:20000], 'permalink': str(item.get('permalink_url', item.get('permalink', ''))), 'published_at': item['_published_at'], 'media_type': media_type}
                db.execute("INSERT INTO social_snapshots(platform,post_id,captured_at,metrics,warnings,source) VALUES(?,?,?,?,?,?)", (platform, str(item["id"]), captured, json.dumps(metrics), json.dumps(issues, ensure_ascii=False), json.dumps(source, ensure_ascii=False)))
            db.execute("UPDATE social_accounts SET synced_at=?,status=? WHERE platform=?", (captured, "partial" if warnings else "connected", platform))
            db.execute("INSERT INTO social_syncs(platform,captured_at,result) VALUES(?,?,?)", (platform, captured, json.dumps(result, ensure_ascii=False)))
        return result

    @staticmethod
    def _read_metrics(payload, metrics):
        for item in payload.get("data", []):
            values = item.get("values", [])
            value = item.get("total_value", {}).get("value")
            if value is None and values:
                value = values[-1].get("value")
            if isinstance(item.get("name"), str):
                metrics[item["name"]] = value

    def posts(self, platform):
        with connect(self.db_path) as db:
            rows = db.execute("SELECT p.*,s.id AS snapshot_id,s.captured_at,s.metrics,s.warnings FROM social_posts p JOIN social_accounts a ON a.platform=p.platform AND a.account_id=p.account_id JOIN social_snapshots s ON s.id=(SELECT MAX(x.id) FROM social_snapshots x WHERE x.platform=p.platform AND x.post_id=p.post_id) WHERE p.platform=? AND datetime(p.published_at)>=datetime('now','-30 days') ORDER BY p.published_at DESC LIMIT 100", (platform,)).fetchall()
        return [{**dict(row), "metrics": json.loads(row["metrics"]), "warnings": json.loads(row["warnings"])} for row in rows]

    def evidence(self, snapshot_ids):
        if not isinstance(snapshot_ids, list) or not 1 <= len(snapshot_ids) <= 10 or any(type(i) is not int for i in snapshot_ids):
            raise ValueError("請選擇 1–10 則參考貼文。")
        with connect(self.db_path) as db:
            rows = db.execute("SELECT p.*,s.id AS snapshot_id,s.captured_at,s.metrics,s.warnings,s.source FROM social_snapshots s JOIN social_posts p ON p.platform=s.platform AND p.post_id=s.post_id WHERE s.id IN (" + ",".join("?" for _ in snapshot_ids) + ") ORDER BY s.id", snapshot_ids).fetchall()
        if len(rows) != len(set(snapshot_ids)):
            raise ValueError("數據已清除，請重新選取貼文。")
        result = [{**{key: row[key] for key in row.keys() if key != 'source'}, **json.loads(row['source']), "metrics": json.loads(row["metrics"]), "warnings": json.loads(row["warnings"])} for row in rows]
        if len(json.dumps(result, ensure_ascii=False)) > 30000:
            raise ValueError("選取的貼文內容超過 30,000 字元，請減少參考貼文。")
        return result

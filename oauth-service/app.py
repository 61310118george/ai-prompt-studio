"""Single-user OAuth broker. Run one worker behind HTTPS; no token database."""
from __future__ import annotations

import hashlib
import asyncio
from contextlib import asynccontextmanager, suppress
import os
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


class Start(BaseModel):
    provider: str = Field(pattern="^(facebook|threads)$")
    challenge: str = Field(pattern="^[a-f0-9]{64}$")


class Claim(BaseModel):
    session_id: str = Field(min_length=20, max_length=128)
    verifier: str = Field(min_length=32, max_length=128)


class Meta:
    def __init__(self, config):
        self.config = config

    def client(self, provider, **kwargs):
        prefix = "META" if provider == "facebook" else "THREADS"
        return OAuth2Client(self.config[prefix + "_APP_ID"], self.config[prefix + "_APP_SECRET"],
                            token_endpoint_auth_method="client_secret_post", timeout=20, follow_redirects=False, **kwargs)

    def redirect(self, provider):
        return self.config["PUBLIC_BASE_URL"] + "/auth/callback/" + provider

    def authorization_url(self, provider, state):
        scopes = "pages_show_list pages_read_engagement read_insights instagram_basic instagram_manage_insights" if provider == "facebook" else "threads_basic threads_manage_insights"
        host = f"https://www.facebook.com/{self.config['META_GRAPH_VERSION']}/dialog/oauth" if provider == "facebook" else "https://threads.net/oauth/authorize"
        with self.client(provider, scope=scopes, redirect_uri=self.redirect(provider)) as client:
            url, _ = client.create_authorization_url(host, state=state)
            return url

    @staticmethod
    def data(response):
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("Oversized response")
        result = response.json()
        if not isinstance(result, dict) or "error" in result:
            raise ValueError("Invalid platform response")
        return result

    def exchange(self, provider, code):
        base = f"https://graph.facebook.com/{self.config['META_GRAPH_VERSION']}" if provider == "facebook" else "https://graph.threads.net"
        with self.client(provider, redirect_uri=self.redirect(provider)) as client:
            short = client.fetch_token(base + "/oauth/access_token", code=code, grant_type="authorization_code")
            with httpx.Client(timeout=20, follow_redirects=False) as http:
                if provider == "facebook":
                    long_token = self.data(http.get(base + "/oauth/access_token", params={"grant_type": "fb_exchange_token", "client_id": self.config["META_APP_ID"], "client_secret": self.config["META_APP_SECRET"], "fb_exchange_token": short["access_token"]}))
                else:
                    long_token = self.data(http.get(base + "/access_token", headers={"Authorization": "Bearer " + short["access_token"]}, params={"grant_type": "th_exchange_token", "client_secret": self.config["THREADS_APP_SECRET"]}))
                token = long_token["access_token"]
                headers = {"Authorization": "Bearer " + token}
                profile = self.data(http.get(base + "/me", headers=headers, params={"fields": "id,name" if provider == "facebook" else "id,username"}))
                allowed = self.config["ALLOWED_FACEBOOK_IDS" if provider == "facebook" else "ALLOWED_THREADS_IDS"].split(",")
                if str(profile["id"]) not in {value.strip() for value in allowed}:
                    raise ValueError("Account is not on the owner allowlist")
                expiry = time.time() + float(long_token.get("expires_in", short.get("expires_in", 3600)))
                if provider == "threads":
                    return [{"platform": "threads", "account_id": str(profile["id"]), "name": profile["username"], "access_token": token, "expires_at": expiry}]
                accounts, params, cursors = [], {"fields": "id,name,access_token,instagram_business_account{id,username}", "limit": 50}, set()
                for _ in range(10):
                    pages = self.data(http.get(base + "/me/accounts", headers=headers, params=params))
                    for page in pages.get("data", []):
                        page_token = page.get("access_token")
                        if not page_token:
                            continue
                        accounts.append({"platform": "facebook", "account_id": str(page["id"]), "name": page["name"], "access_token": page_token, "expires_at": expiry})
                        ig = page.get("instagram_business_account")
                        if ig:
                            accounts.append({"platform": "instagram", "account_id": str(ig["id"]), "name": ig.get("username", page["name"]), "access_token": page_token, "expires_at": expiry})
                    paging = pages.get("paging", {})
                    after = paging.get("cursors", {}).get("after")
                    if not paging.get("next") or not after or after in cursors:
                        break
                    cursors.add(after)
                    params["after"] = after
                return accounts


def create_app(config=None, meta=None):
    config = dict(os.environ if config is None else config)
    required = ("PUBLIC_BASE_URL", "BROKER_KEY", "META_GRAPH_VERSION", "META_APP_ID", "META_APP_SECRET", "THREADS_APP_ID", "THREADS_APP_SECRET", "ALLOWED_FACEBOOK_IDS", "ALLOWED_THREADS_IDS")
    missing = [name for name in required if not config.get(name)]
    if missing:
        raise RuntimeError("Missing configuration: " + ", ".join(missing))
    config["PUBLIC_BASE_URL"] = config["PUBLIC_BASE_URL"].rstrip("/")
    url = urlsplit(config["PUBLIC_BASE_URL"])
    if url.scheme != "https" or not url.hostname or url.path or url.username or url.password or url.query or url.fragment:
        raise RuntimeError("PUBLIC_BASE_URL must be an HTTPS origin")
    if not 32 <= len(config["BROKER_KEY"]) <= 256 or not re.fullmatch(r"v\d+\.\d+", config["META_GRAPH_VERSION"]):
        raise RuntimeError("Invalid broker key or graph version")
    meta = meta or Meta(config)
    sessions, states = {}, {}
    lock = threading.Lock()

    def authenticate(header):
        if not secrets.compare_digest(header or "", "Bearer " + config["BROKER_KEY"]):
            raise HTTPException(401, "Invalid connection code")

    def purge():
        for key, value in list(sessions.items()):
            if time.monotonic() - value["created"] >= 600:
                states.pop(value["state"], None)
                del sessions[key]

    @asynccontextmanager
    async def lifespan(app):
        async def cleanup():
            while True:
                await asyncio.sleep(30)
                with lock:
                    purge()
        task = asyncio.create_task(cleanup())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            with lock:
                sessions.clear()
                states.clear()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def no_cache(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/start")
    def start(body: Start, authorization: str | None = Header(default=None)):
        authenticate(authorization)
        with lock:
            purge()
            if len(sessions) >= 32:
                raise HTTPException(429, "Too many pending authorizations")
            session, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            url = meta.authorization_url(body.provider, state)
            sessions[session] = {"created": time.monotonic(), "provider": body.provider, "challenge": body.challenge, "state": state, "status": "pending"}
            states[state] = session
        return {"session_id": session, "authorization_url": url}

    @app.get("/auth/callback/{provider}", response_class=HTMLResponse)
    def callback(provider: str, state: str = "", code: str = "", error: str = ""):
        with lock:
            purge()
            session = states.get(state)
            item = sessions.get(session)
            if not item or item["provider"] != provider or item["status"] != "pending":
                raise HTTPException(400, "Invalid or expired authorization")
            states.pop(state)
            item["status"] = "processing"
        try:
            if error or not code:
                raise ValueError("Authorization declined")
            accounts = meta.exchange(provider, code)
            if not accounts:
                raise ValueError("No managed accounts")
            result = {"status": "ready", "accounts": accounts, "graph_version": config["META_GRAPH_VERSION"]}
        except Exception:
            # Never echo an OAuth exception: it can contain tokens or callback codes.
            result = {"status": "error"}
        with lock:
            if session in sessions:
                item.update(result)
        message = "授權完成，請回到 AI Prompt Studio 選擇帳號。" if result["status"] == "ready" else "授權未完成，請檢查帳號權限、允許的帳號 ID 與服務設定後重試。"
        return HTMLResponse("<!doctype html><html lang='zh-Hant'><meta charset='utf-8'><title>AI Prompt Studio</title><body><h1>AI Prompt Studio</h1><p>" + message + "</p></body></html>")

    @app.post("/auth/claim")
    def claim(body: Claim, authorization: str | None = Header(default=None)):
        authenticate(authorization)
        with lock:
            purge()
            item = sessions.get(body.session_id)
            if not item or not secrets.compare_digest(item["challenge"], hashlib.sha256(body.verifier.encode()).hexdigest()):
                raise HTTPException(400, "Invalid or expired session")
            if item["status"] in {"pending", "processing"}:
                return {"status": "pending"}
            del sessions[body.session_id]
            states.pop(item["state"], None)
            return {key: item[key] for key in ("status", "accounts", "graph_version") if key in item}

    return app

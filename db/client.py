from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()


class PostgrestError(RuntimeError):
    """Raised when Supabase/PostgREST returns a non-success response."""


@dataclass
class QueryResult:
    data: list[dict] | dict | None
    count: int | None = None


class SupabaseRestClient:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "apikey": key,
                "Authorization": f"Bearer {key}",
            }
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict | list | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        response = self.session.request(
            method,
            f"{self.url}/rest/v1/{path.lstrip('/')}",
            params=params,
            json=json,
            headers=headers,
            timeout=30,
        )

        if response.ok:
            return response

        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        raise PostgrestError(str(payload))

    def select(
        self,
        relation: str,
        *,
        params: dict[str, str] | None = None,
        count: str | None = None,
    ) -> QueryResult:
        headers = {"Prefer": f"count={count}"} if count else None
        response = self.request("GET", relation, params=params, headers=headers)
        total = None
        if count:
            content_range = response.headers.get("content-range", "")
            if "/" in content_range:
                try:
                    total = int(content_range.rsplit("/", 1)[1])
                except ValueError:
                    total = None
        return QueryResult(data=response.json(), count=total)

    def insert(self, relation: str, payload: dict) -> QueryResult:
        response = self.request(
            "POST",
            relation,
            json=payload,
            headers={"Content-Type": "application/json", "Prefer": "return=representation"},
        )
        return QueryResult(data=response.json())

    def upsert(self, relation: str, payload: dict, *, on_conflict: str) -> QueryResult:
        response = self.request(
            "POST",
            relation,
            params={"on_conflict": on_conflict},
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
        )
        return QueryResult(data=response.json())

    def update(
        self,
        relation: str,
        *,
        filters: dict[str, str],
        payload: dict,
    ) -> QueryResult:
        response = self.request(
            "PATCH",
            relation,
            params=filters,
            json=payload,
            headers={"Content-Type": "application/json", "Prefer": "return=representation"},
        )
        return QueryResult(data=response.json())


_read_client: SupabaseRestClient | None = None
_write_client: SupabaseRestClient | None = None


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _get_supabase_url() -> str:
    url = _first_env("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL must be set")
    return url


def _looks_publishable(key: str) -> bool:
    return key.startswith("sb_publishable_")


def get_read_client() -> SupabaseRestClient:
    global _read_client
    if _read_client is None:
        key = _first_env(
            "SUPABASE_ANON_KEY",
            "SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SECRET_KEY",
        )
        if not key:
            raise RuntimeError(
                "A Supabase read key must be set. "
                "Use SUPABASE_ANON_KEY, SUPABASE_PUBLISHABLE_KEY, or SUPABASE_KEY."
            )
        _read_client = SupabaseRestClient(_get_supabase_url(), key)
    return _read_client


def get_write_client() -> SupabaseRestClient:
    global _write_client
    if _write_client is None:
        key = _first_env("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY")
        if not key:
            fallback = _first_env("SUPABASE_KEY")
            if fallback and not _looks_publishable(fallback):
                key = fallback
        if not key:
            raise RuntimeError(
                "A write-capable Supabase key must be set for the scraper. "
                "Use SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY."
            )
        _write_client = SupabaseRestClient(_get_supabase_url(), key)
    return _write_client


def get_client() -> SupabaseRestClient:
    return get_read_client()

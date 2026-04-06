from __future__ import annotations

from datetime import datetime, timezone

try:
    from supabase import Client, create_client
except Exception:
    Client = None
    create_client = None


class SupabaseControl:
    def __init__(self, url: str, key: str):
        self._client: Client | None = None
        self._cache: dict[str, dict] = {}
        if url and key and create_client is not None:
            self._client = create_client(url, key)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def fetch_strategy_control(self) -> dict[str, dict]:
        if self._client is None:
            return self._cache
        try:
            rows = self._client.table("strategy_control").select("*").execute().data or []
            self._cache = {str(row.get("strategy_name", "")).strip(): row for row in rows}
            return self._cache
        except Exception:
            return self._cache

    def update_heartbeat(self, strategy_name: str) -> None:
        if self._client is None:
            return
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._client.table("strategy_control").update({"last_updated": now}).eq(
                "strategy_name", strategy_name
            ).execute()
        except Exception:
            return

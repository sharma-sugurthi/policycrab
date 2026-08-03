import pytest

from app.services import user_data


class _Result:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class _Table:
    def __init__(self, name, result=None, error=None):
        self.name = name
        self.result = result or _Result()
        self.error = error
        self.calls = []

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def eq(self, *args, **kwargs):
        self.calls.append(("eq", args, kwargs))
        return self

    def limit(self, *args, **kwargs):
        self.calls.append(("limit", args, kwargs))
        return self

    def upsert(self, *args, **kwargs):
        self.calls.append(("upsert", args, kwargs))
        return self

    def delete(self):
        self.calls.append(("delete", (), {}))
        return self

    def execute(self):
        self.calls.append(("execute", (), {}))
        if self.error:
            raise self.error
        return self.result


class _Client:
    def __init__(self, table):
        self._table = table

    def table(self, name):
        assert name == "user_chats"
        return self._table


def test_get_user_chat_reads_persisted_supabase_row(monkeypatch):
    table = _Table(
        "user_chats",
        _Result(data=[{"id": "chat-1", "messages": [{"role": "user", "content": "hi"}]}]),
    )
    monkeypatch.setattr(user_data, "get_supabase_client", lambda: _Client(table))

    chat = user_data.get_user_chat("user-1", "chat-1")

    assert chat["id"] == "chat-1"
    assert ("eq", ("user_id", "user-1"), {}) in table.calls


def test_upsert_user_chat_writes_persisted_supabase_row(monkeypatch):
    table = _Table("user_chats", _Result(data=[{"id": "chat-1"}]))
    monkeypatch.setattr(user_data, "get_supabase_client", lambda: _Client(table))

    saved = user_data.upsert_user_chat(
        "user-1",
        [{"role": "user", "content": "hi"}],
        policy_profile={"plan_name": "Gold"},
        cost_breakdown={"patient_responsibility": 25},
    )

    assert saved == {"id": "chat-1"}
    upsert_calls = [call for call in table.calls if call[0] == "upsert"]
    assert upsert_calls
    payload = upsert_calls[0][1][0]
    assert payload["user_id"] == "user-1"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]
    assert upsert_calls[0][2] == {"on_conflict": "id"}


def test_chat_persistence_errors_are_not_silently_ephemeral(monkeypatch):
    table = _Table("user_chats", error=RuntimeError("database unavailable"))
    monkeypatch.setattr(user_data, "get_supabase_client", lambda: _Client(table))

    with pytest.raises(RuntimeError, match="database unavailable"):
        user_data.get_user_chat("user-1", "chat-1")

from types import SimpleNamespace

from app.services import user_data


class _InsertCapture:
    def __init__(self):
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return SimpleNamespace(data=[self.payload])


class _FakeClient:
    def __init__(self, capture):
        self.capture = capture

    def table(self, name):
        assert name == "user_policies"
        return self.capture


def test_create_user_policy_supplies_explicit_id(monkeypatch):
    capture = _InsertCapture()
    monkeypatch.setattr(user_data, "get_supabase_client", lambda: _FakeClient(capture))

    result = user_data.create_user_policy("user-123", {"plan_name": "Test Plan"})

    assert result["user_id"] == "user-123"
    assert result["policy_profile_json"]["plan_name"] == "Test Plan"
    assert isinstance(result["id"], str)
    assert len(result["id"]) > 10
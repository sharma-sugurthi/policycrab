from types import SimpleNamespace

from app.services import user_data


class _InsertCapture:
    def __init__(self):
        self.payload = None
        self._mode = None  # tracks whether we're in "select" or "insert" flow

    def select(self, *args, **kwargs):
        self._mode = "select"
        return self

    def eq(self, *args, **kwargs):
        return self

    def insert(self, payload):
        self._mode = "insert"
        self.payload = payload
        return self

    def execute(self):
        if self._mode == "select":
            return SimpleNamespace(data=[], count=0)
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

class _ClaimInsertCapture:
    def __init__(self):
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return SimpleNamespace(data=[self.payload])


class _ClaimClient:
    def __init__(self, capture):
        self.capture = capture

    def table(self, name):
        assert name == "user_claims"
        return self.capture


def test_create_user_claim_supplies_explicit_id(monkeypatch):
    capture = _ClaimInsertCapture()
    monkeypatch.setattr(user_data, "get_supabase_client", lambda: _ClaimClient(capture))

    result = user_data.create_user_claim(
        "user-123",
        "I had a denied MRI claim.",
        {"billed_amount": 3500},
        {"appeal_letter": "draft"},
        "denied",
    )

    assert result["user_id"] == "user-123"
    assert isinstance(result["id"], str)
    assert len(result["id"]) > 10

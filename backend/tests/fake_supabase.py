"""In-memory stand-in for the supabase-py client used across service tests."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4


class FakeQuery:
    def __init__(self, table, store):
        self.table, self.store = table, store
        self.filters, self.mode, self.payload, self.count_mode = [], "select", None, None
        self._limit = None

    def select(self, *cols, count=None):
        self.mode, self.count_mode = "select", count
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, list(vals)))
        return self

    def is_(self, col, val):
        self.filters.append(("is", col, val))
        return self

    def gte(self, col, val):
        self.filters.append(("gte", col, val))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, n, *a):
        self._limit = n
        return self

    def insert(self, payload):
        self.mode, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.mode, self.payload = "update", payload
        return self

    def delete(self):
        self.mode = "delete"
        return self

    def _match(self, row):
        for op, col, val in self.filters:
            rv = row.get(col)
            if op == "eq" and str(rv) != str(val):
                return False
            if op == "in" and str(rv) not in {str(v) for v in val}:
                return False
            if op == "is" and val == "null" and rv is not None:
                return False
            if op == "gte" and (rv is None or str(rv) < str(val)):
                return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.table, [])
        if self.mode == "select":
            out = [dict(r) for r in rows if self._match(r)]
            if self._limit:
                out = out[: self._limit]
            return SimpleNamespace(data=out, count=len(out) if self.count_mode else None)
        if self.mode == "insert":
            row = dict(self.payload)
            row.setdefault("id", str(uuid4()))
            row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            rows.append(row)
            return SimpleNamespace(data=[dict(row)])
        if self.mode == "update":
            out = []
            for r in rows:
                if self._match(r):
                    r.update(self.payload)
                    out.append(dict(r))
            return SimpleNamespace(data=out)
        out = [dict(r) for r in rows if self._match(r)]
        rows[:] = [r for r in rows if not self._match(r)]
        return SimpleNamespace(data=out)


class FakeClient:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return FakeQuery(name, self.store)


class ExplodingClient:
    """Every call raises — proves recording never propagates failures."""

    def table(self, name):
        raise RuntimeError("database unavailable")

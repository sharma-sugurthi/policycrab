from app.api.auth import get_current_user
from app.api.router import api_router


def _dependency_call_names(route):
    return {dependency.call for dependency in route.dependant.dependencies}


def test_knowledge_search_requires_authenticated_user():
    route = next(
        route
        for route in api_router.routes
        if getattr(route, "path", None) == "/api/knowledge/search"
    )

    assert get_current_user in _dependency_call_names(route)

import pytest

from solution_gen.locale_search import set_search_provider


@pytest.fixture(autouse=True)
def _silence_web_search():
    set_search_provider(lambda _query: [])
    yield
    set_search_provider(None)

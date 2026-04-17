from app.domain.windows_it_admin import WINDOWS_IT_ADMIN_SOURCES, WINDOWS_IT_ADMIN_TASKS


def test_windows_domain_sources_only():
    assert len(WINDOWS_IT_ADMIN_SOURCES) == 4
    assert len(WINDOWS_IT_ADMIN_TASKS) == 0
    assert all(item["source_type"] == "url" for item in WINDOWS_IT_ADMIN_SOURCES)

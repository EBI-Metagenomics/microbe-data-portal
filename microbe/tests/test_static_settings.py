from django.conf import settings


def test_runtime_sass_compilation_is_disabled_outside_debug_mode():
    assert settings.DEBUG is False
    assert settings.SASS_PROCESSOR_ENABLED is False

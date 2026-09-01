from yfphonecam.update_check import _version_key, should_check


def test_stable_release_is_newer_than_beta() -> None:
    assert _version_key("0.1.0") > _version_key("0.1.0-beta.9")


def test_beta_versions_are_ordered_numerically() -> None:
    assert _version_key("v0.1.0-beta.10") > _version_key("0.1.0-beta.2")


def test_semver_prerelease_precedence() -> None:
    assert _version_key("1.0.0-alpha") < _version_key("1.0.0-beta")
    assert _version_key("1.0.0-beta.11") < _version_key("1.0.0-rc.1")


def test_update_check_runs_at_most_daily() -> None:
    assert not should_check(100, now=100 + 86_399)
    assert should_check(100, now=100 + 86_400)

"""Tests for garmin_client: session resume and the re-login fallback."""
# _with_session is the unit under test here: calling the module-private helper directly
# is intentional, so the protected-access warning is switched off for this file only.
# pylint: disable=protected-access
from unittest.mock import MagicMock, call, patch
import pytest
from garth.exc import GarthException

import garmin_client

REJECTED = GarthException(msg="DI-OAuth2 exchange failed: HTTP Error 400: ")
TIMEOUT = GarthException(
    msg="DI-OAuth2 exchange failed: Failed to perform, curl: (28) Operation timed out"
)

@patch("garmin_client.login")
def test_with_session_returns_result_without_relogin(mock_login):
    """A working cached session is used as is: one resume, no password login."""
    assert garmin_client._with_session(lambda: "data") == "data"
    mock_login.assert_called_once_with()

@patch("garmin_client.login")
def test_with_session_logs_in_again_when_session_is_rejected(mock_login):
    """A rejected token exchange triggers one forced login and one retry."""
    fetch = MagicMock(side_effect=[REJECTED, "data"])
    assert garmin_client._with_session(fetch) == "data"
    assert mock_login.call_args_list == [call(), call(force=True)]
    assert fetch.call_count == 2

@patch("garmin_client.login")
def test_with_session_does_not_relogin_on_timeout(mock_login):
    """Network timeouts are not an auth problem: no extra login, error passes through."""
    fetch = MagicMock(side_effect=TIMEOUT)
    with pytest.raises(GarthException):
        garmin_client._with_session(fetch)
    mock_login.assert_called_once_with()
    assert fetch.call_count == 1

@patch("garmin_client.login")
def test_with_session_retries_only_once(mock_login):
    """If the fresh session is refused too, the error is raised instead of looping."""
    fetch = MagicMock(side_effect=[REJECTED, REJECTED])
    with pytest.raises(GarthException):
        garmin_client._with_session(fetch)
    assert mock_login.call_count == 2

@patch("garmin_client.garth")
def test_forced_login_skips_resume_and_saves_session(mock_garth, monkeypatch):
    """force=True goes straight to the password login and stores the new session."""
    monkeypatch.setattr(garmin_client.config, "GARMIN_USERNAME", "user@example.com")
    monkeypatch.setattr(garmin_client.config, "GARMIN_PASSWORD", "secret")
    garmin_client.login(force=True)
    mock_garth.resume.assert_not_called()
    mock_garth.login.assert_called_once()
    mock_garth.save.assert_called_once()

@patch("garmin_client.garth")
def test_login_resumes_cached_session(mock_garth):
    """Without force the cached session is resumed and no password login happens."""
    garmin_client.login()
    mock_garth.resume.assert_called_once()
    mock_garth.login.assert_not_called()


@patch("garmin_client.garth")
def test_login_resumes_cached_session_without_credentials(mock_garth, monkeypatch):
    """A cached session is enough to work: resume must not demand a password."""
    monkeypatch.setattr(garmin_client.config, "GARMIN_USERNAME", None)
    monkeypatch.setattr(garmin_client.config, "GARMIN_PASSWORD", None)

    garmin_client.login()

    mock_garth.resume.assert_called_once()
    mock_garth.login.assert_not_called()


@patch("garmin_client.garth")
def test_login_without_credentials_reports_the_missing_variables(mock_garth, monkeypatch):
    """No session and no credentials: a ValueError naming the variables, before any
    network login is attempted."""
    monkeypatch.setattr(garmin_client.config, "GARMIN_USERNAME", None)
    monkeypatch.setattr(garmin_client.config, "GARMIN_PASSWORD", None)
    mock_garth.resume.side_effect = GarthException(msg="No token files found in ~/.garth")

    with pytest.raises(ValueError, match="GARMIN_USERNAME"):
        garmin_client.login()

    mock_garth.login.assert_not_called()

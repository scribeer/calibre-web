"""Hermetic tests for admin registration invite creation."""

import hashlib
import logging
import re
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from flask_wtf.csrf import CSRFProtect, generate_csrf
from jinja2 import ChainableUndefined, DictLoader, Environment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import cps
from cps import constants, ub
from cps.cw_login import AnonymousUserMixin


ADMIN_TEMPLATE = Path(__file__).parent.parent / "cps" / "themes" / "standard" / "templates" / "admin.html"


class AdminInviteHttpTest(unittest.TestCase):
    """Exercise the production admin blueprint with isolated app state."""

    @classmethod
    def setUpClass(cls):
        # Importing admin initializes the optional GDrive module. Keep that
        # initialization in memory rather than pointing it at DEV data.
        cps.cli_param.gd_path = ":memory:"
        from cps import admin, usermanagement

        cls.admin_module = admin
        cls.usermanagement = usermanagement

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        ub.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.admin_user = ub.User(name="admin", email="admin@example.org", role=constants.ROLE_ADMIN)
        self.normal_user = ub.User(name="reader", email="reader@example.org", role=constants.ROLE_USER)
        self.db.add_all((self.admin_user, self.normal_user))
        self.db.commit()
        self.users = {
            "admin": self.admin_user,
            "reader": self.normal_user,
        }

        self.config = type("TestConfig", (), {
            "config_allow_reverse_proxy_header_login": False,
            "config_public_reg": False,
            "config_anonbrowse": True,
            "config_uploading": False,
            "config_theme": 3,
            "config_authors_max": 0,
            "db_configured": True,
            "schedule_start_time": 0,
            "schedule_duration": 0,
        })()

        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="invite-test", TESTING=True, WTF_CSRF_ENABLED=True)
        CSRFProtect(self.app)
        self.app.add_url_rule("/csrf", "csrf", lambda: generate_csrf())

        self.old_user_callback = cps.lm._user_callback
        self.old_request_callback = cps.lm._request_callback
        self.old_anonymous_user = cps.lm.anonymous_user
        self.old_session_protection = cps.lm.session_protection
        cps.lm.init_app(self.app)
        cps.lm.anonymous_user = AnonymousUserMixin
        cps.lm.session_protection = None
        cps.lm._user_callback = None
        cps.lm._request_callback = lambda req: self.users.get(req.headers.get("X-Test-User"))

        def render_admin(_template, **context):
            return context.get("generated_invite_url") or "admin page"

        def fake_url_for(endpoint, **kwargs):
            if endpoint == "web.register_invite":
                return "/register/" + kwargs.get("token", "fake-token")
            return "/" + endpoint

        self.patchers = [
            patch.object(ub, "session", self.db),
            patch.object(self.admin_module, "config", self.config),
            patch.object(self.usermanagement, "config", self.config),
            patch.object(self.admin_module.aubooks_permissions, "config", self.config),
            patch.object(self.admin_module, "render_title_template", side_effect=render_admin),
            patch.object(self.admin_module.updater_thread, "get_current_version_info", return_value=False),
            patch.object(self.admin_module, "_", side_effect=lambda value, **_kwargs: value),
            patch.object(self.admin_module, "format_time", return_value="00:00"),
            patch.object(self.admin_module, "format_timedelta", return_value="0"),
        ]
        for patcher in self.patchers:
            patcher.start()

        self.app.register_blueprint(self.admin_module.admi)
        self.client = self.app.test_client()

        # Mock url_for on the module (must happen after blueprint registration)
        self._url_for_patcher = patch.object(self.admin_module, "url_for", side_effect=fake_url_for)
        self._url_for_patcher.start()

    def tearDown(self):
        self._url_for_patcher.stop()
        for patcher in reversed(self.patchers):
            patcher.stop()
        cps.lm._user_callback = self.old_user_callback
        cps.lm._request_callback = self.old_request_callback
        cps.lm.anonymous_user = self.old_anonymous_user
        cps.lm.session_protection = self.old_session_protection
        self.db.close()
        self.engine.dispose()

    def csrf_token(self):
        return self.client.get("/csrf").get_data(as_text=True)

    def post_as(self, username=None, data=None):
        headers = {"X-Test-User": username} if username else {}
        form = {"csrf_token": self.csrf_token()}
        form.update(data or {})
        return self.client.post("/admin/registration-link", data=form, headers=headers)

    def test_anonymous_cannot_create_invite(self):
        response = self.post_as()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)

    def test_non_admin_cannot_create_invite(self):
        response = self.post_as("reader")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)

    def test_admin_creates_exactly_one_invite(self):
        response = self.post_as("admin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.query(ub.Invite).count(), 1)

    def test_post_requires_csrf(self):
        response = self.client.post(
            "/admin/registration-link", headers={"X-Test-User": "admin"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)

    def test_get_is_not_allowed(self):
        response = self.client.get(
            "/admin/registration-link", headers={"X-Test-User": "admin"}
        )
        self.assertEqual(response.status_code, 405)

    def test_creator_and_expiry_are_server_controlled(self):
        response = self.post_as("admin", {
            "created_by_user_id": str(self.normal_user.id),
            "expires_at": "2099-01-01T00:00:00",
            "role": str(constants.ROLE_ADMIN),
            "email": "attacker@example.org",
            "max_uses": "99",
        })
        self.assertEqual(response.status_code, 200)
        invite = self.db.query(ub.Invite).one()
        self.assertEqual(invite.created_by_user_id, self.admin_user.id)
        self.assertEqual(invite.expires_at - invite.created_at, timedelta(days=7))
        self.assertFalse(hasattr(invite, "role"))
        self.assertFalse(hasattr(invite, "email"))
        self.assertFalse(hasattr(invite, "max_uses"))

    def test_response_contains_raw_url_but_database_only_has_hash(self):
        response = self.post_as("admin")
        body = response.get_data(as_text=True)
        match = re.fullmatch(r"/register/([A-Za-z0-9_-]{43})", body)
        self.assertIsNotNone(match)
        raw_token = match.group(1)
        invite = self.db.query(ub.Invite).one()
        self.assertNotEqual(invite.token_hash, raw_token)
        self.assertEqual(invite.token_hash, hashlib.sha256(raw_token.encode("ascii")).hexdigest())

    def test_raw_token_is_not_logged(self):
        with self.assertLogs(level=logging.CRITICAL) as captured:
            logging.getLogger().critical("stage-2-log-capture")
            response = self.post_as("admin")
        raw_token = response.get_data(as_text=True).rsplit("/", 1)[-1]
        self.assertNotIn(raw_token, "\n".join(captured.output))

    def test_non_aubooks_theme_cannot_create_invite(self):
        self.config.config_theme = 0
        response = self.post_as("admin")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)

    def test_existing_admin_page_still_works(self):
        response = self.client.get("/admin/view", headers={"X-Test-User": "admin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "admin page")


class InviteListTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        ub.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_list_is_limited_and_never_contains_raw_tokens(self):
        raw_tokens = [ub.create_invite(self.db) for _ in range(25)]
        self.db.commit()
        rows = ub.get_invite_list(self.db, limit=20)
        self.assertEqual(len(rows), 20)
        rendered = repr(rows)
        for raw_token in raw_tokens:
            self.assertNotIn(raw_token, rendered)

    def test_list_reports_all_statuses(self):
        active_token = ub.create_invite(self.db)
        used_token = ub.create_invite(self.db)
        revoked_token = ub.create_invite(self.db)
        expired_token = ub.create_invite(self.db)
        self.db.flush()
        ub.consume_invite(self.db, ub.get_invite_by_token(self.db, used_token), user_id=1)
        ub.revoke_invite(self.db, ub.get_invite_by_token(self.db, revoked_token))
        expired = self.db.query(ub.Invite).filter(ub.Invite.token_hash == ub._hash_token(expired_token)).one()
        expired.expires_at = expired.created_at
        self.db.commit()
        statuses = {row["status"] for row in ub.get_invite_list(self.db)}
        self.assertEqual(statuses, {"Active", "Used", "Revoked", "Expired"})
        self.assertIsNotNone(ub.get_invite_by_token(self.db, active_token))


class AdminInviteTemplateTest(unittest.TestCase):
    @staticmethod
    def render(is_aubooks):
        source = ADMIN_TEMPLATE.read_text()
        start = source.index("{% if is_aubooks %}")
        end = source.index("{% if (config.config_login_type == 1) %}", start)
        env = Environment(
            loader=DictLoader({"invite.html": source[start:end]}),
            undefined=ChainableUndefined,
        )
        env.globals.update({
            "theme": lambda _name: "layout.html",
            "url_for": lambda endpoint, **_kwargs: "/" + endpoint,
            "csrf_token": lambda: "csrf",
            "_": lambda value, **_kwargs: value,
            "change_confirm_modal": lambda: "",
        })
        return env.get_template("invite.html").render(
            is_aubooks=is_aubooks,
            invites=[],
            generated_invite_url=None,
        )

    def test_aubooks_theme_exposes_invite_ui(self):
        html = self.render(True)
        self.assertIn("admin.create_registration_link", html)
        self.assertIn('name="csrf_token"', html)
        self.assertIn("admin.send_invite", html)
        self.assertIn("invite_email", html)

    def test_standard_theme_does_not_expose_invite_ui(self):
        html = self.render(False)
        self.assertNotIn("admin.create_registration_link", html)
        self.assertNotIn("admin.send_invite", html)
        self.assertNotIn("invite_email", html)

    def test_generated_link_is_readonly_and_explanatory(self):
        source = ADMIN_TEMPLATE.read_text()
        self.assertIn('value="{{generated_invite_url}}" readonly', source)


class AdminInviteEmailTest(unittest.TestCase):
    """Tests for the invite-by-email endpoint."""

    @classmethod
    def setUpClass(cls):
        cps.cli_param.gd_path = ":memory:"
        from cps import admin, usermanagement

        cls.admin_module = admin
        cls.usermanagement = usermanagement

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        ub.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.admin_user = ub.User(name="admin", email="admin@example.org", role=constants.ROLE_ADMIN)
        self.normal_user = ub.User(name="reader", email="reader@example.org", role=constants.ROLE_USER)
        self.db.add_all((self.admin_user, self.normal_user))
        self.db.commit()
        self.users = {"admin": self.admin_user, "reader": self.normal_user}

        self.mail_configured = True
        self.config = type("TestConfig", (), {
            "config_allow_reverse_proxy_header_login": False,
            "config_public_reg": False,
            "config_anonbrowse": True,
            "config_uploading": False,
            "config_theme": 3,
            "config_authors_max": 0,
            "db_configured": True,
            "schedule_start_time": 0,
            "schedule_duration": 0,
            "get_mail_server_configured": lambda self_: self.mail_configured,
            "get_mail_settings": lambda self_: {"mail_server": "test"},
        })()

        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="invite-email-test", TESTING=True, WTF_CSRF_ENABLED=True)
        CSRFProtect(self.app)
        self.app.add_url_rule("/csrf", "csrf", lambda: generate_csrf())

        self.old_user_callback = cps.lm._user_callback
        self.old_request_callback = cps.lm._request_callback
        self.old_anonymous_user = cps.lm.anonymous_user
        self.old_session_protection = cps.lm.session_protection
        cps.lm.init_app(self.app)
        cps.lm.anonymous_user = AnonymousUserMixin
        cps.lm.session_protection = None
        cps.lm._user_callback = None
        cps.lm._request_callback = lambda req: self.users.get(req.headers.get("X-Test-User"))

        def render_admin(_template, **context):
            return context.get("generated_invite_url") or "admin page"

        def fake_url_for(endpoint, **kwargs):
            if endpoint == "web.register_invite":
                return "/register/" + kwargs.get("token", "fake-token")
            return "/" + endpoint

        self.email_queued = []
        self.patchers = [
            patch.object(ub, "session", self.db),
            patch.object(self.admin_module, "config", self.config),
            patch.object(self.usermanagement, "config", self.config),
            patch.object(self.admin_module.aubooks_permissions, "config", self.config),
            patch.object(self.admin_module, "render_title_template", side_effect=render_admin),
            patch.object(self.admin_module.updater_thread, "get_current_version_info", return_value=False),
            patch.object(self.admin_module, "_", side_effect=lambda value, **_kwargs: value),
            patch.object(self.admin_module, "format_time", return_value="00:00"),
            patch.object(self.admin_module, "format_timedelta", return_value="0"),
            patch.object(self.admin_module, "send_invite_mail",
                         side_effect=lambda email, url: self.email_queued.append({"email": email, "url": url})),
        ]
        for patcher in self.patchers:
            patcher.start()

        self.app.register_blueprint(self.admin_module.admi)
        self.client = self.app.test_client()

        self._url_for_patcher = patch.object(self.admin_module, "url_for", side_effect=fake_url_for)
        self._url_for_patcher.start()

    def tearDown(self):
        self._url_for_patcher.stop()
        for patcher in reversed(self.patchers):
            patcher.stop()
        cps.lm._user_callback = self.old_user_callback
        cps.lm._request_callback = self.old_request_callback
        cps.lm.anonymous_user = self.old_anonymous_user
        cps.lm.session_protection = self.old_session_protection
        self.db.close()
        self.engine.dispose()

    def csrf_token(self):
        return self.client.get("/csrf").get_data(as_text=True)

    def post_invite(self, username=None, data=None):
        headers = {"X-Test-User": username} if username else {}
        form = {"csrf_token": self.csrf_token()}
        form.update(data or {})
        return self.client.post("/admin/send-invite", data=form, headers=headers)

    def test_anonymous_cannot_send_invite(self):
        response = self.post_invite()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)

    def test_non_admin_cannot_send_invite(self):
        response = self.post_invite("reader")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)

    def test_admin_creates_invite_and_queues_email(self):
        response = self.post_invite("admin", {"invite_email": "newuser@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.query(ub.Invite).count(), 1)
        self.assertEqual(len(self.email_queued), 1)
        self.assertEqual(self.email_queued[0]["email"], "newuser@example.com")
        self.assertIn("/register/", self.email_queued[0]["url"])

    def test_empty_email_rejected(self):
        response = self.post_invite("admin", {"invite_email": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)
        self.assertEqual(len(self.email_queued), 0)

    def test_invalid_email_rejected(self):
        response = self.post_invite("admin", {"invite_email": "not-an-email"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)
        self.assertEqual(len(self.email_queued), 0)

    def test_valid_email_creates_exactly_one_invite(self):
        response = self.post_invite("admin", {"invite_email": "user@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.query(ub.Invite).count(), 1)

    def test_creates_exactly_one_email_task(self):
        response = self.post_invite("admin", {"invite_email": "user@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.email_queued), 1)

    def test_recipient_matches_submitted_email(self):
        response = self.post_invite("admin", {"invite_email": "target@domain.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.email_queued[0]["email"], "target@domain.com")

    def test_raw_token_not_stored_in_db(self):
        response = self.post_invite("admin", {"invite_email": "user@example.com"})
        body = response.get_data(as_text=True)
        invite = self.db.query(ub.Invite).one()
        self.assertNotEqual(invite.token_hash, "")
        self.assertEqual(len(invite.token_hash), 64)

    def test_manual_create_link_still_works(self):
        response = self.client.post(
            "/admin/registration-link",
            data={"csrf_token": self.csrf_token()},
            headers={"X-Test-User": "admin"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.query(ub.Invite).count(), 1)
        self.assertEqual(len(self.email_queued), 0)

    def test_invite_is_one_time_and_7day(self):
        response = self.post_invite("admin", {"invite_email": "user@example.com"})
        self.assertEqual(response.status_code, 200)
        invite = self.db.query(ub.Invite).one()
        self.assertIsNone(invite.used_at)
        delta = invite.expires_at - invite.created_at
        self.assertEqual(delta.days, 7)

    def test_non_aubooks_theme_returns_404(self):
        self.config.config_theme = 0
        response = self.post_invite("admin", {"invite_email": "user@example.com"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)

    def test_smtp_not_configured_creates_invite_but_no_email(self):
        self.mail_configured = False
        response = self.post_invite("admin", {"invite_email": "user@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.query(ub.Invite).count(), 1)
        self.assertEqual(len(self.email_queued), 0)

    def test_post_requires_csrf(self):
        response = self.client.post(
            "/admin/send-invite",
            data={"invite_email": "user@example.com"},
            headers={"X-Test-User": "admin"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.query(ub.Invite).count(), 0)

    def test_get_is_not_allowed(self):
        response = self.client.get(
            "/admin/send-invite", headers={"X-Test-User": "admin"}
        )
        self.assertEqual(response.status_code, 405)

    def test_invite_url_appears_in_response(self):
        response = self.post_invite("admin", {"invite_email": "user@example.com"})
        body = response.get_data(as_text=True)
        self.assertIn("/register/", body)
        invite = self.db.query(ub.Invite).one()
        self.assertIsNotNone(invite.token_hash)


if __name__ == "__main__":
    unittest.main()

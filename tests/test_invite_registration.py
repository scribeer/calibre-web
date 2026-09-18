"""Hermetic HTTP tests for AU-Books invite-only registration."""

import hashlib
import re
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask, redirect, url_for
from flask_wtf.csrf import CSRFProtect, generate_csrf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

import cps
from cps import constants, ub
from cps.cw_login import AnonymousUserMixin


class InviteRegistrationHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cps.cli_param.gd_path = ":memory:"
        from cps import web

        cls.web_module = web

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        ub.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.admin_user = ub.User(
            name="admin",
            email="admin@example.org",
            password=generate_password_hash("admin-password"),
            role=constants.ROLE_ADMIN,
        )
        self.db.add_all((
            self.admin_user,
            ub.Registration(domain="%.%", allow=1),
        ))
        self.db.commit()
        self.users = {"admin": self.admin_user}

        self.mail_configured = MagicMock(return_value=False)
        self.config = type("TestConfig", (), {
            "config_theme": 3,
            "config_public_reg": True,
            "config_register_email": False,
            "config_default_role": constants.ROLE_USER,
            "config_default_locale": "ru",
            "config_default_show": 17,
            "config_allowed_tags": "",
            "config_denied_tags": "",
            "config_allowed_column_value": "",
            "config_denied_column_value": "",
            "config_password_min_length": 8,
            "config_login_type": constants.LOGIN_STANDARD,
            "config_is_initial": False,
            "get_mail_server_configured": self.mail_configured,
        })()

        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="invite-registration-test",
            TESTING=True,
            WTF_CSRF_ENABLED=True,
            RATELIMIT_ENABLED=False,
        )
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

        def render_template(template, **_context):
            return "registration form" if template == "register.html" else "login form"

        def gettext(value, **kwargs):
            return value % kwargs if kwargs else value

        self.patchers = [
            patch.object(ub, "session", self.db),
            patch.object(self.web_module, "config", self.config),
            patch.object(self.web_module, "is_aubooks_active",
                         side_effect=lambda: self.config.config_theme == 3),
            patch.object(self.web_module, "render_title_template", side_effect=render_template),
            patch.object(self.web_module, "_", side_effect=gettext),
            patch.dict(self.web_module.feature_support, {"oauth": False}),
        ]
        for patcher in self.patchers:
            patcher.start()

        self.app.register_blueprint(self.web_module.web)
        self.client = self.app.test_client()

    def tearDown(self):
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

    def create_invite(self):
        token = ub.create_invite(self.db, created_by_user_id=self.admin_user.id)
        self.db.commit()
        return token

    def registration_data(self, **overrides):
        data = {
            "csrf_token": self.csrf_token(),
            "name": "new-reader",
            "email": "new-reader@example.org",
            "password": "chosen password",
            "confirm_password": "chosen password",
        }
        data.update(overrides)
        return data

    def post_invite(self, token, **overrides):
        return self.client.post(
            "/register/{}".format(token),
            data=self.registration_data(**overrides),
        )

    def assert_invite_unused(self, token):
        invite = self.db.query(ub.Invite).filter(ub.Invite.token_hash == ub._hash_token(token)).one()
        self.assertIsNone(invite.used_at)
        self.assertIsNone(invite.used_by_user_id)

    def assert_generic_invite_error(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/login"))
        with self.client.session_transaction() as session:
            messages = [message for _category, message in session.get("_flashes", [])]
        self.assertIn(self.web_module.INVITE_ERROR_MESSAGE, messages)

    def test_valid_get_renders_form_without_consuming(self):
        token = self.create_invite()
        response = self.client.get("/register/{}".format(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "registration form")
        self.assert_invite_unused(token)
        self.mail_configured.assert_not_called()

    def test_authenticated_get_redirects_home(self):
        token = self.create_invite()
        response = self.client.get(
            "/register/{}".format(token), headers={"X-Test-User": "admin"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/"))
        self.assert_invite_unused(token)

    def test_valid_post_creates_user_and_consumes_invite(self):
        token = self.create_invite()
        response = self.post_invite(token, role=str(constants.ROLE_ADMIN), created_by_user_id="999")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/login"))
        user = self.db.query(ub.User).filter(ub.User.name == "new-reader").one()
        self.assertTrue(check_password_hash(user.password, "chosen password"))
        self.assertEqual(user.role, constants.ROLE_USER)
        self.assertFalse(user.role_admin())
        self.assertFalse(user.role_upload())
        self.assertFalse(user.role_edit())
        self.assertFalse(user.role_delete_books())
        self.assertFalse(user.role_aubooks_upload_tts())
        self.assertEqual(user.locale, "ru")
        self.assertEqual(user.sidebar_view, 17)
        invite = self.db.query(ub.Invite).filter(ub.Invite.token_hash == ub._hash_token(token)).one()
        self.assertIsNotNone(invite.used_at)
        self.assertEqual(invite.used_by_user_id, user.id)
        self.assertEqual(invite.created_by_user_id, self.admin_user.id)
        self.mail_configured.assert_not_called()

    def test_invite_registration_does_not_change_existing_user_locale(self):
        self.admin_user.locale = "en"
        self.db.commit()
        token = self.create_invite()

        self.post_invite(token)

        self.db.refresh(self.admin_user)
        self.assertEqual(self.admin_user.locale, "en")

    def test_registered_user_can_change_interface_locale(self):
        token = self.create_invite()
        self.post_invite(token)
        user = self.db.query(ub.User).filter(ub.User.name == "new-reader").one()
        self.assertEqual(user.locale, "ru")

        with self.app.test_request_context("/me", method="POST", data={
            "email": user.email,
            "locale": "en",
            "default_language": "all",
        }), patch.object(self.web_module, "current_user", user):
            self.web_module.change_profile(False, {}, None, [], [])

        self.db.refresh(user)
        self.assertEqual(user.locale, "en")

    def test_configured_default_role_is_retained_exactly(self):
        self.config.config_default_role = constants.ROLE_VIEWER
        token = self.create_invite()
        self.post_invite(token, role=str(constants.ROLE_ADMIN))
        user = self.db.query(ub.User).filter(ub.User.name == "new-reader").one()
        self.assertEqual(user.role, constants.ROLE_VIEWER)

    def test_raw_token_not_persisted_or_put_in_session(self):
        token = self.create_invite()
        response = self.post_invite(token)
        self.assertEqual(response.status_code, 302)
        invite = self.db.query(ub.Invite).filter(ub.Invite.token_hash == ub._hash_token(token)).one()
        self.assertEqual(invite.token_hash, hashlib.sha256(token.encode("ascii")).hexdigest())
        self.assertNotEqual(invite.token_hash, token)
        with self.client.session_transaction() as session:
            self.assertNotIn(token, repr(dict(session)))
            self.assertNotIn("_user_id", session)

    def test_raw_token_is_not_application_logged(self):
        token = self.create_invite()
        with patch.object(self.web_module, "log") as log:
            self.post_invite(token)
        self.assertNotIn(token, repr(log.method_calls))

    def test_unknown_token_uses_generic_error(self):
        self.assert_generic_invite_error(self.client.get("/register/" + "x" * 43))

    def test_invalid_token_post_uses_generic_error_and_creates_no_user(self):
        response = self.post_invite("x" * 43)
        self.assert_generic_invite_error(response)
        self.assertIsNone(self.db.query(ub.User).filter(ub.User.name == "new-reader").first())

    def test_malformed_token_uses_generic_error(self):
        self.assert_generic_invite_error(self.client.get("/register/not-valid!"))

    def test_expired_token_uses_generic_error(self):
        token = self.create_invite()
        invite = self.db.query(ub.Invite).filter(ub.Invite.token_hash == ub._hash_token(token)).one()
        invite.expires_at = invite.created_at
        self.db.commit()
        self.assert_generic_invite_error(self.client.get("/register/{}".format(token)))

    def test_revoked_token_uses_generic_error(self):
        token = self.create_invite()
        invite = ub.get_invite_by_token(self.db, token)
        ub.revoke_invite(self.db, invite)
        self.db.commit()
        self.assert_generic_invite_error(self.client.get("/register/{}".format(token)))

    def test_used_token_uses_generic_error(self):
        token = self.create_invite()
        invite = ub.get_invite_by_token(self.db, token)
        ub.consume_invite(self.db, invite, self.admin_user.id)
        self.db.commit()
        self.assert_generic_invite_error(self.client.get("/register/{}".format(token)))

    def test_second_post_cannot_create_second_user(self):
        token = self.create_invite()
        self.assertEqual(self.post_invite(token).status_code, 302)
        second = self.post_invite(
            token,
            name="second-reader",
            email="second-reader@example.org",
        )
        self.assert_generic_invite_error(second)
        self.assertIsNone(self.db.query(ub.User).filter(ub.User.name == "second-reader").first())

    def test_duplicate_username_does_not_consume(self):
        token = self.create_invite()
        response = self.post_invite(token, name="admin")
        self.assertEqual(response.status_code, 200)
        self.assert_invite_unused(token)

    def test_duplicate_email_does_not_consume(self):
        token = self.create_invite()
        response = self.post_invite(token, email="admin@example.org")
        self.assertEqual(response.status_code, 200)
        self.assert_invite_unused(token)

    def test_password_mismatch_does_not_consume(self):
        token = self.create_invite()
        response = self.post_invite(token, confirm_password="different")
        self.assertEqual(response.status_code, 200)
        self.assert_invite_unused(token)

    def test_invalid_email_does_not_consume(self):
        token = self.create_invite()
        response = self.post_invite(token, email="not-an-email")
        self.assertEqual(response.status_code, 200)
        self.assert_invite_unused(token)

    def test_empty_password_does_not_consume_or_require_smtp(self):
        token = self.create_invite()
        response = self.post_invite(token, password="", confirm_password="")
        self.assertEqual(response.status_code, 200)
        self.assert_invite_unused(token)
        self.mail_configured.assert_not_called()

    def test_database_failure_rolls_back_user_and_invite(self):
        token = self.create_invite()
        with patch.object(self.db, "commit", side_effect=RuntimeError("forced commit failure")):
            response = self.post_invite(token)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.db.query(ub.User).filter(ub.User.name == "new-reader").first())
        self.assert_invite_unused(token)

    def test_post_requires_csrf(self):
        token = self.create_invite()
        response = self.client.post("/register/{}".format(token), data={
            "name": "new-reader",
            "email": "new-reader@example.org",
            "password": "chosen password",
            "confirm_password": "chosen password",
        })
        self.assertEqual(response.status_code, 400)
        self.assert_invite_unused(token)

    def test_plain_aubooks_register_redirects_and_cannot_create(self):
        get_response = self.client.get("/register")
        self.assertEqual(get_response.status_code, 302)
        self.assertTrue(get_response.location.endswith("/login"))
        with self.client.session_transaction() as session:
            messages = [message for _category, message in session.get("_flashes", [])]
        self.assertIn(self.web_module.INVITE_ONLY_MESSAGE, messages)
        post_response = self.client.post("/register", data=self.registration_data())
        self.assertEqual(post_response.status_code, 302)
        self.assertTrue(post_response.location.endswith("/login"))
        self.assertIsNone(self.db.query(ub.User).filter(ub.User.name == "new-reader").first())

    def test_standard_public_registration_remains_available(self):
        self.config.config_theme = 0
        self.mail_configured.return_value = True
        get_response = self.client.get("/register")
        self.assertEqual(get_response.status_code, 200)
        with patch.object(self.web_module, "send_registration_mail") as send_mail:
            post_response = self.client.post("/register", data={
                "csrf_token": self.csrf_token(),
                "name": "new-reader",
                "email": "new-reader@example.org",
            })
        self.assertEqual(post_response.status_code, 302)
        self.assertIsNotNone(self.db.query(ub.User).filter(ub.User.name == "new-reader").first())
        send_mail.assert_called_once()

    def test_created_user_can_log_in_with_chosen_password(self):
        token = self.create_invite()
        self.post_invite(token)
        with patch.object(
            self.web_module,
            "handle_login_user",
            side_effect=lambda *_args, **_kwargs: redirect(url_for("web.index")),
        ) as login_handler:
            response = self.client.post("/login", data={
                "csrf_token": self.csrf_token(),
                "username": "new-reader",
                "password": "chosen password",
            })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/"))
        login_handler.assert_called_once()

    def test_aubooks_templates_have_no_public_registration_link(self):
        root = Path(__file__).parent.parent / "cps" / "themes" / "aubooks" / "templates"
        login = (root / "login.html").read_text()
        layout = (root / "layout.html").read_text()
        register = (root / "register.html").read_text()
        self.assertNotIn("web.register", login)
        self.assertNotIn("web.register", layout)
        self.assertIn("Регистрация доступна по приглашению.", login)
        self.assertRegex(register, r'<form method="POST"(?![^>]*action=)')
        self.assertIsNone(re.search(r'https?://', register))

    def test_invite_post_keeps_public_registration_rate_limits(self):
        source = (Path(__file__).parent.parent / "cps" / "web.py").read_text()
        match = re.search(
            r"@web\.route\('/register/<token>'.*?def register_invite_post",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertIn("40/day", match.group(0))
        self.assertIn("3/minute", match.group(0))

    def test_builtin_access_log_redacts_invite_token(self):
        from cps import tornado_wsgi
        from cps.tornado_wsgi import MyWSGIContainer

        token = "a" * 43
        request = type("Request", (), {
            "method": "GET",
            "uri": "/register/{}?source=test".format(token),
            "remote_ip": "127.0.0.1",
            "request_time": lambda self: 0.001,
        })()
        container = object.__new__(MyWSGIContainer)
        container.env = {}
        with patch.object(tornado_wsgi.access_log, "info") as access_info:
            container._log(200, request)
        logged = repr(access_info.call_args)
        self.assertNotIn(token, logged)
        self.assertIn("/register/<redacted>?source=test", logged)


if __name__ == "__main__":
    unittest.main()

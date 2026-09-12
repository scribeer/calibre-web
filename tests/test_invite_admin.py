"""Hermetic tests for admin registration invite creation (Stage 2)."""

import hashlib
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cps import ub

ADMIN_PY_PATH = Path(__file__).parent.parent / "cps" / "admin.py"
ADMIN_HTML_PATH = Path(__file__).parent.parent / "cps" / "themes" / "standard" / "templates" / "admin.html"


def read_admin_source():
    return ADMIN_PY_PATH.read_text()


def read_admin_template():
    return ADMIN_HTML_PATH.read_text()


def _get_create_registration_link_block():
    """Extract the decorator+function block for create_registration_link."""
    lines = read_admin_source().splitlines(keepends=True)
    in_block = False
    block_lines = []
    for line in lines:
        if '@admi.route("/admin/registration-link"' in line:
            in_block = True
        if in_block:
            block_lines.append(line)
            if len(block_lines) > 1:
                stripped = line.lstrip()
                if stripped.startswith('@admi.route(') or (stripped.startswith('def ') and not stripped.startswith('def create_registration_link')):
                    block_lines.pop()
                    break
    return ''.join(block_lines)


# ---------------------------------------------------------------------------
# Source-text structural tests
# ---------------------------------------------------------------------------

class TestAdminRouteStructure(unittest.TestCase):
    """Verify the admin invite route exists with correct patterns."""

    def test_route_exists(self):
        src = read_admin_source()
        self.assertIn('/admin/registration-link', src)

    def test_route_is_post_only(self):
        src = read_admin_source()
        match = re.search(
            r'@admi\.route\("/admin/registration-link",\s*methods=\["POST"\]\)',
            src,
        )
        self.assertIsNotNone(match, "Route must be POST-only")

    def test_has_admin_required_decorator(self):
        block = _get_create_registration_link_block()
        self.assertIn('admin_required', block)

    def test_has_user_login_required_decorator(self):
        block = _get_create_registration_link_block()
        self.assertIn('user_login_required', block)

    def test_calls_create_invite(self):
        block = _get_create_registration_link_block()
        self.assertIn('ub.create_invite(', block)

    def test_created_by_current_user(self):
        block = _get_create_registration_link_block()
        self.assertIn('created_by_user_id=current_user.id', block)

    def test_does_not_accept_custom_expiry(self):
        block = _get_create_registration_link_block()
        self.assertNotIn('expires_at', block,
                         "Route must not accept custom expiry from browser")

    def test_does_not_accept_custom_role(self):
        block = _get_create_registration_link_block()
        self.assertNotIn('role', block,
                         "Route must not accept custom role from browser")

    def test_does_not_flash_raw_token(self):
        block = _get_create_registration_link_block()
        self.assertNotIn('flash(', block,
                         "Route must not flash the raw token")

    def test_renders_admin_page(self):
        block = _get_create_registration_link_block()
        self.assertIn('render_title_template("admin.html"', block)

    def test_passes_generated_invite_url(self):
        block = _get_create_registration_link_block()
        self.assertIn('generated_invite_url=', block)

    def test_get_not_allowed(self):
        block = _get_create_registration_link_block()
        self.assertNotIn('"GET"', block,
                         "GET method must not be allowed")


# ---------------------------------------------------------------------------
# Template tests
# ---------------------------------------------------------------------------

class TestAdminTemplate(unittest.TestCase):
    """Verify admin.html has invite UI elements."""

    def test_has_invite_form(self):
        html = read_admin_template()
        self.assertIn('admin.create_registration_link', html)

    def test_has_csrf_token_in_form(self):
        html = read_admin_template()
        self.assertIn('csrf_token', html)

    def test_has_invite_button(self):
        html = read_admin_template()
        self.assertIn('create_invite', html)

    def test_has_generated_url_display(self):
        html = read_admin_template()
        self.assertIn('generated_invite_url', html)

    def test_has_invite_list_table(self):
        html = read_admin_template()
        self.assertIn('invites', html)

    def test_invite_section_au_only(self):
        html = read_admin_template()
        self.assertIn('is_aubooks', html)

    def test_invite_url_is_readonly(self):
        html = read_admin_template()
        self.assertIn('readonly', html)


# ---------------------------------------------------------------------------
# Invite list helper tests (direct function call with temp DB)
# ---------------------------------------------------------------------------

class InviteTestBase(unittest.TestCase):
    """Base class with temporary in-memory SQLite database."""

    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        ub.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()


class TestInviteListHelper(InviteTestBase):
    """Test get_invite_list() through the ub module."""

    def test_empty_list_when_no_invites(self):
        result = ub.get_invite_list(self.session)
        self.assertEqual(result, [])

    def test_active_invite_shows_active_status(self):
        ub.create_invite(self.session)
        self.session.commit()
        result = ub.get_invite_list(self.session)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'Active')

    def test_used_invite_shows_used_status(self):
        raw = ub.create_invite(self.session, created_by_user_id=1)
        invite = ub.get_invite_by_token(self.session, raw)
        ub.consume_invite(self.session, invite, user_id=42)
        self.session.commit()
        result = ub.get_invite_list(self.session)
        self.assertEqual(result[0]['status'], 'Used')

    def test_revoked_invite_shows_revoked_status(self):
        raw = ub.create_invite(self.session)
        invite = ub.get_invite_by_token(self.session, raw)
        ub.revoke_invite(self.session, invite)
        self.session.commit()
        result = ub.get_invite_list(self.session)
        self.assertEqual(result[0]['status'], 'Revoked')

    def test_expired_invite_shows_expired_status(self):
        raw = ub.create_invite(self.session)
        invite = self.session.query(ub.Invite).one()
        invite.expires_at = datetime.utcnow() - timedelta(hours=1)
        self.session.commit()
        result = ub.get_invite_list(self.session)
        self.assertEqual(result[0]['status'], 'Expired')

    def test_list_never_shows_raw_token(self):
        raw = ub.create_invite(self.session)
        self.session.commit()
        result = ub.get_invite_list(self.session)
        for key, val in result[0].items():
            self.assertNotIn(raw, str(val),
                             f"Raw token found in field {key}")

    def test_created_by_shows_username(self):
        user = ub.User(name='admin', email='admin@test.com', role=1)
        self.session.add(user)
        self.session.commit()
        ub.create_invite(self.session, created_by_user_id=user.id)
        self.session.commit()
        result = ub.get_invite_list(self.session)
        self.assertEqual(result[0]['created_by_name'], 'admin')

    def test_created_by_empty_when_no_creator(self):
        ub.create_invite(self.session)
        self.session.commit()
        result = ub.get_invite_list(self.session)
        self.assertEqual(result[0]['created_by_name'], '')


# ---------------------------------------------------------------------------
# Token security verification
# ---------------------------------------------------------------------------

class TestTokenSecurityInAdminFlow(InviteTestBase):
    """Verify raw token is never persisted in DB."""

    def test_raw_token_not_in_invite_row(self):
        raw = ub.create_invite(self.session, created_by_user_id=1)
        self.session.commit()
        invite = self.session.query(ub.Invite).one()
        for col in invite.__table__.columns:
            val = getattr(invite, col.name)
            if isinstance(val, str) and raw in val:
                self.fail(f"Raw token found in column {col.name}")

    def test_only_sha256_hash_stored(self):
        raw = ub.create_invite(self.session)
        self.session.commit()
        invite = self.session.query(ub.Invite).one()
        expected = hashlib.sha256(raw.encode('ascii')).hexdigest()
        self.assertEqual(invite.token_hash, expected)
        self.assertEqual(len(invite.token_hash), 64)


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------

class TestAdminModuleRegression(unittest.TestCase):
    """Verify admin module has expected attributes."""

    def test_admin_blueprint_has_create_registration_link(self):
        import cps
        cps.cli_param.gd_path = "/tmp/test_gdrive.db"
        from cps import admin
        self.assertTrue(callable(getattr(admin, 'create_registration_link', None)))

    def test_get_invite_list_helper_exists(self):
        import cps
        cps.cli_param.gd_path = "/tmp/test_gdrive.db"
        from cps import admin
        self.assertTrue(callable(getattr(admin, '_get_invite_list', None)))

    def test_ub_get_invite_list_exists(self):
        self.assertTrue(callable(ub.get_invite_list))


class TestInviteModelRegression(InviteTestBase):
    """Run Stage 1 model tests to ensure no regression."""

    def test_create_and_consume_cycle(self):
        raw = ub.create_invite(self.session, created_by_user_id=1)
        self.session.commit()
        invite = ub.get_invite_by_token(self.session, raw)
        self.assertIsNotNone(invite)
        ok = ub.consume_invite(self.session, invite, user_id=42)
        self.assertTrue(ok)
        self.session.commit()
        self.assertIsNone(ub.get_invite_by_token(self.session, raw))

    def test_revoke_cycle(self):
        raw = ub.create_invite(self.session)
        self.session.commit()
        invite = ub.get_invite_by_token(self.session, raw)
        ok = ub.revoke_invite(self.session, invite)
        self.assertTrue(ok)
        self.session.commit()
        self.assertIsNone(ub.get_invite_by_token(self.session, raw))

    def test_expiry_boundary(self):
        raw = ub.create_invite(self.session)
        invite = self.session.query(ub.Invite).one()
        delta = invite.expires_at - invite.created_at
        self.assertEqual(delta, timedelta(days=7))


class TestPyCompile(unittest.TestCase):
    """Verify modified files compile without syntax errors."""

    def test_admin_py_compiles(self):
        import py_compile
        py_compile.compile(str(ADMIN_PY_PATH), doraise=True)

    def test_ub_py_compiles(self):
        import py_compile
        py_compile.compile(
            str(Path(__file__).parent.parent / 'cps' / 'ub.py'),
            doraise=True,
        )


if __name__ == '__main__':
    unittest.main()

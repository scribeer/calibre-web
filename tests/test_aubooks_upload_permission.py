"""Focused tests for the AU-Books upload-for-TTS permission."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestAubooksUploadPermission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cps
        cps.cli_param.gd_path = "/home/feninf/calibre-web-dev-data/gdrive.db"
        from cps import admin, aubooks_permissions, constants, ub

        cls.admin = admin
        cls.permissions = aubooks_permissions
        cls.constants = constants
        cls.user_base = ub.UserBase

    @staticmethod
    def _user(authenticated, role=0, admin=False):
        return SimpleNamespace(
            is_authenticated=authenticated,
            role_admin=MagicMock(return_value=admin),
            role_aubooks_upload_tts=MagicMock(
                return_value=bool(role & (1 << 10))
            ),
        )

    def _can_upload(self, user, theme=3):
        with patch.object(self.permissions.config, "config_theme", theme, create=True):
            return self.permissions.can_upload_for_tts(user)

    def test_anonymous_cannot_upload_for_tts(self):
        self.assertFalse(self._can_upload(self._user(False)))

    def test_authenticated_role_zero_cannot_upload_for_tts(self):
        self.assertFalse(self._can_upload(self._user(True)))

    def test_authenticated_uploader_can_upload_for_tts(self):
        self.assertTrue(self._can_upload(
            self._user(True, self.constants.ROLE_AUBOOKS_UPLOAD_TTS)
        ))

    def test_admin_without_upload_bit_can_upload_for_tts(self):
        user = self._user(True, self.constants.ROLE_ADMIN, admin=True)
        self.assertTrue(self._can_upload(user))
        user.role_aubooks_upload_tts.assert_not_called()

    def test_non_aubooks_theme_never_grants_capability(self):
        user = self._user(True, self.constants.ROLE_AUBOOKS_UPLOAD_TTS)
        self.assertFalse(self._can_upload(user, theme=0))
        user.role_admin.assert_not_called()

    def test_user_helper_checks_upload_bit(self):
        user = self.user_base()
        user.role = self.constants.ROLE_AUBOOKS_UPLOAD_TTS
        self.assertTrue(user.role_aubooks_upload_tts())
        user.role = 0
        self.assertFalse(user.role_aubooks_upload_tts())

    def test_edit_checkbox_on_sets_upload_bit(self):
        user = SimpleNamespace(role=0, is_anonymous=False)
        self.admin._update_user_roles({"aubooks_upload_tts_role": "on"}, user)
        self.assertEqual(user.role, self.constants.ROLE_AUBOOKS_UPLOAD_TTS)

    def test_edit_checkbox_off_removes_upload_bit(self):
        user = SimpleNamespace(
            role=self.constants.ROLE_AUBOOKS_UPLOAD_TTS,
            is_anonymous=False,
        )
        self.admin._update_user_roles({}, user)
        self.assertEqual(user.role, 0)

    def test_edit_preserves_unrelated_unknown_bits(self):
        unknown_bit = 1 << 14
        user = SimpleNamespace(role=unknown_bit, is_anonymous=False)
        self.admin._update_user_roles({"download_role": "on"}, user)
        self.assertEqual(user.role, unknown_bit | self.constants.ROLE_DOWNLOAD)

    def test_edit_preserves_tts_bit_when_checkbox_is_checked(self):
        user = SimpleNamespace(
            role=self.constants.ROLE_GENERATE_TTS,
            is_anonymous=False,
        )
        self.admin._update_user_roles({"tts_role": "on"}, user)
        self.assertEqual(user.role, self.constants.ROLE_GENERATE_TTS)

    def test_admin_edit_does_not_require_upload_bit(self):
        user = SimpleNamespace(role=self.constants.ROLE_ADMIN, is_anonymous=False)
        self.admin._update_user_roles({"admin_role": "on"}, user)
        self.assertEqual(user.role, self.constants.ROLE_ADMIN)
        policy_user = self._user(True, user.role, admin=True)
        self.assertTrue(self._can_upload(policy_user))

    def test_admin_default_mask_does_not_gain_upload_bit(self):
        self.assertEqual(self.constants.ROLE_AUBOOKS_UPLOAD_TTS, 1024)
        self.assertEqual(self.constants.ADMIN_USER_ROLES, 991)
        self.assertFalse(
            self.constants.ADMIN_USER_ROLES
            & self.constants.ROLE_AUBOOKS_UPLOAD_TTS
        )


class TestAubooksUploadPermissionUi(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent.parent

    def _read(self, relative_path):
        return (self.root / relative_path).read_text(encoding="utf-8")

    def test_create_and_edit_form_exposes_both_tts_permissions(self):
        source = self._read("cps/themes/standard/templates/user_edit.html")
        self.assertIn('name="tts_role"', source)
        self.assertIn('name="aubooks_upload_tts_role"', source)
        self.assertIn("content.role_aubooks_upload_tts()", source)

    def test_caliblur_edit_form_preserves_both_tts_permissions(self):
        source = self._read("cps/themes/caliblur/templates/user_edit.html")
        self.assertIn('name="tts_role"', source)
        self.assertIn('name="aubooks_upload_tts_role"', source)

    def test_default_role_form_exposes_upload_permission(self):
        source = self._read("cps/themes/standard/templates/config_view_edit.html")
        self.assertIn('name="tts_role"', source)
        self.assertIn('name="aubooks_upload_tts_role"', source)
        self.assertIn("conf.role_aubooks_upload_tts()", source)

    def test_bulk_edit_exposes_upload_permission(self):
        source = self._read("cps/themes/standard/templates/user_table.html")
        self.assertIn('"tts_role"', source)
        self.assertIn('"aubooks_upload_tts_role"', source)

    def test_bulk_edit_accepts_only_declared_role_bits(self):
        source = self._read("cps/admin.py")
        self.assertIn("if value in constants.ALL_ROLES.values():", source)
        self.assertNotIn("value <= constants.ROLE_VIEWER", source)


if __name__ == "__main__":
    unittest.main()

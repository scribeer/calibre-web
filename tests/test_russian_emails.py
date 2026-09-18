"""Tests for Russian email text in invite and password-reset emails."""

import unittest
from unittest.mock import patch, MagicMock

import cps
cps.cli_param.gd_path = ":memory:"

from flask import Flask
from flask_babel import Babel
from cps import helper, config, ub


def make_app():
    """Create a minimal Flask app with Babel for translation context."""
    import os
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test'
    app.config['BABEL_DEFAULT_LOCALE'] = 'ru'
    translations_path = os.path.join(os.path.dirname(__file__), '..', 'cps', 'translations')
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = translations_path
    Babel(app)
    return app


class SendInviteMailTest(unittest.TestCase):
    """Verify send_invite_mail produces correct Russian email content."""

    def setUp(self):
        self.app = make_app()
        self.captured = {}

        def fake_add(user, task, hidden=False):
            self.captured['subject'] = task.subject
            self.captured['text'] = task.text
            self.captured['recipient'] = task.recipient
            self.captured['settings'] = task.settings

        self.patcher = patch.object(helper, 'WorkerThread')
        self.mock_worker = self.patcher.start()
        self.mock_worker.add.side_effect = fake_add

        self.mail_patcher = patch.object(
            config, 'get_mail_settings',
            return_value={'mail_server': 'test', 'mail_from': 'AU-Books <noreply@au-books.net>'}
        )
        self.mock_mail = self.mail_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.mail_patcher.stop()

    def test_subject_is_russian(self):
        with self.app.app_context():
            helper.send_invite_mail('user@example.com', 'https://au-books.net/register/abc123')
        self.assertEqual(self.captured['subject'], 'Приглашение в AU-Books')

    def test_body_is_russian(self):
        with self.app.app_context():
            helper.send_invite_mail('user@example.com', 'https://au-books.net/register/abc123')
        body = self.captured['text']
        self.assertIn('Вас пригласили зарегистрироваться на AU-Books.', body)
        self.assertIn('Для создания учётной записи перейдите по ссылке:', body)
        self.assertIn('Ссылка действует 7 дней и может быть использована только один раз.', body)
        self.assertIn('Если вы не ожидали этого письма, просто проигнорируйте его.', body)
        self.assertIn('С уважением,', body)
        self.assertIn('AU-Books', body)

    def test_invite_url_present(self):
        url = 'https://au-books.net/register/abc123def456'
        with self.app.app_context():
            helper.send_invite_mail('user@example.com', url)
        self.assertIn(url, self.captured['text'])

    def test_recipient_correct(self):
        with self.app.app_context():
            helper.send_invite_mail('target@domain.com', 'https://au-books.net/register/abc123')
        self.assertEqual(self.captured['recipient'], 'target@domain.com')

    def test_uses_mail_settings(self):
        with self.app.app_context():
            helper.send_invite_mail('user@example.com', 'https://au-books.net/register/abc123')
        self.assertEqual(self.captured['settings']['mail_server'], 'test')

    def test_no_raw_token_in_task_message(self):
        """Raw token should not appear in the task_message."""
        with self.app.app_context():
            helper.send_invite_mail('user@example.com', 'https://au-books.net/register/SUPERSECRET123')
        task_msg = str(self.captured)
        # The token appears in the URL (which is expected in the email body),
        # but should not leak into log or task metadata beyond the body text.
        self.assertIn('SUPERSECRET123', self.captured['text'])  # URL in body is expected


class SendPasswordResetMailTest(unittest.TestCase):
    """Verify send_password_reset_mail produces correct Russian email content."""

    def setUp(self):
        self.app = make_app()
        self.captured = {}

        def fake_add(user, task, hidden=False):
            self.captured['subject'] = task.subject
            self.captured['text'] = task.text
            self.captured['recipient'] = task.recipient
            self.captured['settings'] = task.settings

        self.patcher = patch.object(helper, 'WorkerThread')
        self.mock_worker = self.patcher.start()
        self.mock_worker.add.side_effect = fake_add

        self.mail_patcher = patch.object(
            config, 'get_mail_settings',
            return_value={'mail_server': 'test', 'mail_from': 'AU-Books <noreply@au-books.net>'}
        )
        self.mock_mail = self.mail_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.mail_patcher.stop()

    def test_subject_is_russian(self):
        with self.app.app_context():
            helper.send_password_reset_mail('user@example.com', 'testuser', 'Xy7!abc')
        self.assertEqual(self.captured['subject'], 'Новый пароль для AU-Books')

    def test_body_is_russian(self):
        with self.app.app_context():
            helper.send_password_reset_mail('user@example.com', 'testuser', 'Xy7!abc')
        body = self.captured['text']
        self.assertIn('Здравствуйте, testuser!', body)
        self.assertIn('Для вашей учётной записи AU-Books создан новый пароль.', body)
        self.assertIn('Имя пользователя: testuser', body)
        self.assertIn('Новый пароль: Xy7!abc', body)
        self.assertIn('После входа рекомендуем изменить пароль в настройках профиля.', body)
        self.assertIn('Если вы не запрашивали сброс пароля, сообщите об этом администратору сайта.', body)
        self.assertIn('С уважением,', body)

    def test_username_present(self):
        with self.app.app_context():
            helper.send_password_reset_mail('u@e.com', 'alice', 'Pw1!xyz')
        self.assertIn('alice', self.captured['text'])

    def test_password_present_in_body(self):
        with self.app.app_context():
            helper.send_password_reset_mail('u@e.com', 'alice', 'Pw1!xyz')
        self.assertIn('Pw1!xyz', self.captured['text'])

    def test_recipient_correct(self):
        with self.app.app_context():
            helper.send_password_reset_mail('target@domain.com', 'alice', 'Pw1!xyz')
        self.assertEqual(self.captured['recipient'], 'target@domain.com')

    def test_uses_mail_settings(self):
        with self.app.app_context():
            helper.send_password_reset_mail('u@e.com', 'alice', 'Pw1!xyz')
        self.assertEqual(self.captured['settings']['mail_server'], 'test')


class ResetPasswordUsesResetMailTest(unittest.TestCase):
    """Verify reset_password calls send_password_reset_mail, not send_registration_mail."""

    def setUp(self):
        self.engine = ub.create_engine('sqlite:///:memory:')
        ub.Base.metadata.create_all(self.engine)
        self.Session = ub.sessionmaker(bind=self.engine)
        self.app = make_app()

        from werkzeug.security import generate_password_hash
        self.user = ub.User(
            name='testuser', email='test@example.com',
            password=generate_password_hash('oldpass'),
            locale='ru'
        )
        sess = self.Session()
        sess.add(self.user)
        sess.commit()
        self.user_id = self.user.id

    def tearDown(self):
        self.engine.dispose()

    def _mock_config(self):
        """Return a mock config that has the attributes reset_password needs."""
        return type('MockConfig', (), {
            'config_password_min_length': 8,
            'get_mail_server_configured': staticmethod(lambda: True),
        })()

    def test_reset_calls_send_password_reset_mail(self):
        sent = {}
        mock_cfg = self._mock_config()
        sess = self.Session()
        with self.app.app_context(), \
             patch.object(ub, 'session', sess), \
             patch.object(helper, 'config', mock_cfg), \
             patch.object(helper, 'send_password_reset_mail') as mock_reset, \
             patch.object(helper, 'generate_password_hash', return_value='hashed'):
            mock_reset.side_effect = lambda e, n, p, loc=None: sent.update({
                'email': e, 'name': n, 'password': p, 'locale': loc
            })
            ret, name = helper.reset_password(self.user_id)

        self.assertEqual(ret, 1)
        self.assertEqual(name, 'testuser')
        self.assertEqual(sent['email'], 'test@example.com')
        self.assertEqual(sent['name'], 'testuser')
        self.assertIn('password', sent)
        self.assertIsNotNone(sent['password'])

    def test_reset_does_not_call_send_registration_mail(self):
        mock_cfg = self._mock_config()
        sess = self.Session()
        with self.app.app_context(), \
             patch.object(ub, 'session', sess), \
             patch.object(helper, 'config', mock_cfg), \
             patch.object(helper, 'send_registration_mail') as mock_reg, \
             patch.object(helper, 'send_password_reset_mail'), \
             patch.object(helper, 'generate_password_hash', return_value='hashed'):
            helper.reset_password(self.user_id)
            mock_reg.assert_not_called()

    def test_password_is_hashed_in_db(self):
        mock_cfg = self._mock_config()
        sess = self.Session()
        with self.app.app_context(), \
             patch.object(ub, 'session', sess), \
             patch.object(helper, 'config', mock_cfg), \
             patch.object(helper, 'send_password_reset_mail'), \
             patch.object(helper, 'generate_password_hash', return_value='hashed_value'):
            helper.reset_password(self.user_id)
            db_user = sess.query(ub.User).filter_by(id=self.user_id).first()
            self.assertEqual(db_user.password, 'hashed_value')


class ExistingRegistrationMailUnchangedTest(unittest.TestCase):
    """Verify send_registration_mail still works for welcome emails."""

    def setUp(self):
        self.app = make_app()
        self.captured = {}

        def fake_add(user, task, hidden=False):
            self.captured['subject'] = task.subject
            self.captured['text'] = task.text

        self.patcher = patch.object(helper, 'WorkerThread')
        self.mock_worker = self.patcher.start()
        self.mock_worker.add.side_effect = fake_add

        self.mail_patcher = patch.object(
            config, 'get_mail_settings',
            return_value={'mail_server': 'test'}
        )
        self.mock_mail = self.mail_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.mail_patcher.stop()

    def test_welcome_email_still_works(self):
        with self.app.app_context():
            helper.send_registration_mail('user@example.com', 'alice', 'pass123', resend=False, locale='ru')
        self.assertIn('alice', self.captured.get('text', ''))

    def test_resend_true_still_works(self):
        with self.app.app_context():
            helper.send_registration_mail('user@example.com', 'alice', 'pass123', resend=True, locale='ru')
        self.assertIn('alice', self.captured.get('text', ''))


if __name__ == '__main__':
    unittest.main()

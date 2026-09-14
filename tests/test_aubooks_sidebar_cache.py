import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from cps import calibre_db, render_template


class TestAubooksSidebarCache(unittest.TestCase):
    def setUp(self):
        render_template._aubooks_sidebar_genre_cache.update(key=None, tree=None)

    @staticmethod
    def _query_mock():
        query = MagicMock()
        query.join.return_value = query
        query.filter.return_value = query
        query.group_by.return_value = query
        query.all.return_value = [SimpleNamespace(id=1, name="sf_fantasy")]
        return query

    @patch("cps.aubooks_genres.build_sidebar_genre_tree")
    @patch("cps.render_template.os.stat")
    @patch("cps.render_template.config.get_book_path", return_value="/library")
    @patch.object(calibre_db, "common_filters", return_value=True)
    @patch.object(type(calibre_db), "session", new_callable=PropertyMock)
    def test_reuses_tree_while_metadata_mtime_is_unchanged(
            self, session_mock, __, ___, stat_mock, build_tree_mock):
        session_mock.return_value.query.return_value = self._query_mock()
        stat_mock.return_value = SimpleNamespace(st_mtime_ns=100)
        build_tree_mock.return_value = [{"category": "Фантастика"}]

        first = render_template._get_aubooks_sidebar_genre_tree()
        second = render_template._get_aubooks_sidebar_genre_tree()

        self.assertIs(first, second)
        self.assertEqual(session_mock.return_value.query.call_count, 1)
        self.assertEqual(build_tree_mock.call_count, 1)

    @patch("cps.aubooks_genres.build_sidebar_genre_tree")
    @patch("cps.render_template.os.stat")
    @patch("cps.render_template.config.get_book_path", return_value="/library")
    @patch.object(calibre_db, "common_filters", return_value=True)
    @patch.object(type(calibre_db), "session", new_callable=PropertyMock)
    def test_rebuilds_tree_after_metadata_mtime_changes(
            self, session_mock, __, ___, stat_mock, build_tree_mock):
        session_mock.return_value.query.return_value = self._query_mock()
        stat_mock.side_effect = [SimpleNamespace(st_mtime_ns=100), SimpleNamespace(st_mtime_ns=101)]
        build_tree_mock.side_effect = [[{"version": 1}], [{"version": 2}]]

        first = render_template._get_aubooks_sidebar_genre_tree()
        second = render_template._get_aubooks_sidebar_genre_tree()

        self.assertEqual(first, [{"version": 1}])
        self.assertEqual(second, [{"version": 2}])
        self.assertEqual(session_mock.return_value.query.call_count, 2)

    @patch("cps.render_template.themed_render", return_value="rendered")
    @patch("cps.render_template._get_aubooks_sidebar_genre_tree")
    @patch("cps.render_template.get_active_theme_identifier", return_value="aubooks")
    @patch("cps.render_template.get_sidebar_config", return_value=([], False))
    @patch("cps.render_template.current_user", SimpleNamespace(is_authenticated=True))
    @patch("cps.render_template.config", SimpleNamespace(
        config_calibre_web_title="AU-Books",
        config_upload_formats="epub,fb2",
    ))
    def test_login_does_not_build_genre_tree(
            self, __, ___, get_tree_mock, themed_render_mock):
        result = render_template.render_title_template("login.html")

        self.assertEqual(result, "rendered")
        get_tree_mock.assert_not_called()
        self.assertNotIn("aubooks_sidebar_genre_tree", themed_render_mock.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()

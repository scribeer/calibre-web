#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2022 OzzieIsaacs
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

from markupsafe import escape

from flask import Blueprint, jsonify, url_for
from sqlalchemy.orm import selectinload
from .cw_login import current_user
from flask_babel import gettext as _
from flask_babel import format_datetime
from babel.units import format_unit

from . import logger, calibre_db, db
from .render_template import render_title_template
from .services.worker import WorkerThread, STAT_WAITING, STAT_FAIL, STAT_STARTED, STAT_FINISH_SUCCESS, STAT_ENDED, \
    STAT_CANCELLED
from .usermanagement import user_login_required
from .aubooks_permissions import can_download, can_generate_tts

tasks = Blueprint('tasks', __name__)

log = logger.create()


@tasks.route("/ajax/emailstat")
@user_login_required
def get_email_status_json():
    tasks = WorkerThread.get_instance().tasks
    return jsonify(render_task_status(tasks))


@tasks.route("/ajax/tts-jobs")
@user_login_required
def get_tts_jobs_json():
    """Return audio jobs from audio.db with metadata from calibre DB."""
    from .aubooks_audio import get_audio_jobs, STATUS_LABELS

    rows = get_audio_jobs()
    if not rows:
        return jsonify([])

    # Batch-fetch only books visible to the current user.
    book_ids = [r["book_id"] for r in rows]
    books_map = {}
    try:
        books = (calibre_db.session.query(db.Books)
                 .options(selectinload(db.Books.authors))
                 .filter(db.Books.id.in_(book_ids))
                 .filter(calibre_db.common_filters(allow_show_archived=True))
                 .all())
        for b in books:
            authors = ", ".join(a.name for a in b.authors) if b.authors else ""
            books_map[b.id] = {"title": b.title, "author": authors}
    except Exception as e:
        log.debug("Failed to fetch book metadata for TTS jobs: %s", e)

    result = []
    for r in rows:
        bid = r["book_id"]
        meta = books_map.get(bid)
        if meta is None:
            continue
        status = r["status"]
        owner_id = r.get("requested_by_user_id")
        can_cancel = (can_generate_tts(current_user)
                      and status in ("queued", "processing")
                      and (current_user.role_admin()
                           or (owner_id is not None and int(owner_id) == int(current_user.id))))
        item = {
            "book_id": bid,
            "title": meta["title"],
            "author": meta["author"],
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "filesize": r["filesize"],
            "duration": r["duration"],
            "error": "Ошибка генерации аудиокниги" if status == "failed" else None,
            "book_url": url_for("web.show_book", book_id=bid),
            "download_url": (url_for("web.download_audiobook", book_id=bid)
                              if status == "ready" and can_download(current_user) else None),
            "can_cancel": can_cancel,
            "cancel_url": (url_for("web.cancel_audio_job", book_id=bid, job_id=r["job_id"])
                           if can_cancel else None),
        }
        result.append(item)

    return jsonify(result)


@tasks.route("/tasks")
@user_login_required
def get_tasks_status():
    # if current user admin, show all email, otherwise only own emails
    return render_title_template('tasks.html', title=_("Tasks"), page="tasks")


# helper function to apply localize status information in tasklist entries
def render_task_status(tasklist):
    rendered_tasklist = list()
    for __, user, __, task, __ in tasklist:
        if user == current_user.name or current_user.role_admin():
            ret = {}
            if task.start_time:
                ret['starttime'] = format_datetime(task.start_time, format='short')
                ret['runtime'] = format_runtime(task.runtime)

            # localize the task status
            if isinstance(task.stat, int):
                if task.stat == STAT_WAITING:
                    ret['status'] = _('Waiting')
                elif task.stat == STAT_FAIL:
                    ret['status'] = _('Failed')
                elif task.stat == STAT_STARTED:
                    ret['status'] = _('Started')
                elif task.stat == STAT_FINISH_SUCCESS:
                    ret['status'] = _('Finished')
                elif task.stat == STAT_ENDED:
                    ret['status'] = _('Ended')
                elif task.stat == STAT_CANCELLED:
                    ret['status'] = _('Cancelled')
                else:
                    ret['status'] = _('Unknown Status')

            ret['taskMessage'] = "{}: {}".format(task.name, task.message) if task.message else task.name
            ret['progress'] = "{} %".format(int(task.progress * 100))
            ret['user'] = escape(user)  # prevent xss

            # Hidden fields
            ret['task_id'] = task.id
            ret['stat'] = task.stat
            ret['is_cancellable'] = task.is_cancellable
            ret['error'] = task.error

            rendered_tasklist.append(ret)

    return rendered_tasklist


# helper function for displaying the runtime of tasks
def format_runtime(runtime):
    ret_val = ""
    if runtime.days:
        ret_val = format_unit(runtime.days, 'duration-day', length="long") + ', '
    minutes, seconds = divmod(runtime.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    # ToDo: locale.number_symbols._data['timeSeparator'] -> localize time separator ?
    if hours:
        ret_val += '{:d}:{:02d}:{:02d}s'.format(hours, minutes, seconds)
    elif minutes:
        ret_val += '{:2d}:{:02d}s'.format(minutes, seconds)
    else:
        ret_val += '{:2d}s'.format(seconds)
    return ret_val

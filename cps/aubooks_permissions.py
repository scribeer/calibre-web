# -*- coding: utf-8 -*-

from . import config, themes


def is_aubooks_active():
    return themes.get_theme_identifier(getattr(config, "config_theme", 0)) == "aubooks"


def can_download(user):
    if is_aubooks_active():
        return bool(user and user.is_authenticated)
    return user.role_download()


def can_generate_tts(user):
    if is_aubooks_active():
        return bool(user and user.is_authenticated)
    return user.role_tts()

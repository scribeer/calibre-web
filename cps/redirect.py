# -*- coding: utf-8 -*-

# Flask License
#
# Copyright © 2010 by the Pallets team.
#
# Some rights reserved.

# Redistribution and use in source and binary forms of the software as well as
# documentation, with or without modification, are permitted provided that the
# following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this list of conditions
# and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice, this list of conditions
# and the following disclaimer in the documentation and/or other materials provided with the distribution.
# Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products
# derived from this software without specific prior written permission.
#
# THIS SOFTWARE AND DOCUMENTATION IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS” AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE AND DOCUMENTATION, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# https://web.archive.org/web/20120517003641/http://flask.pocoo.org/snippets/62/

from urllib.parse import urlparse, urljoin

from flask import request, url_for, current_app
from werkzeug.exceptions import HTTPException


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return ""


def get_redirect_location(next_url, endpoint, **values):
    fallback = url_for(endpoint, **values)
    if not next_url or not is_safe_url(next_url):
        return fallback

    parsed = urlparse(urljoin(request.host_url, next_url))
    target = remove_prefix(parsed.path, request.environ.get('HTTP_X_SCRIPT_NAME', ""))
    if not target:
        return fallback
    adapter = current_app.url_map.bind(urlparse(request.host_url).netloc)
    try:
        if "GET" in adapter.allowed_methods(target):
            return next_url
    except HTTPException:
        pass
    return fallback

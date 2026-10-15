# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The languages: the system prompts and the messages
#
#  Copyright (C) 2026 Alexey Fedoseev <aleksey@fedoseev.net>
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program. If not, see https://www.gnu.org/licenses/
#
#  -----------------------------------------------------------------------------

"""A language is a directory of prompts/: system.md and messages.json."""

import json
import os
import re

from .client import ConfigError
from .notation import WARNING

AUTO = 'auto'
DEFAULT = 'en'
CYRILLIC_LANGUAGE = 'ru'
# the interface language the editor gives a plugin run
EDITOR_LANGUAGE = 'CYBERIADA_EDITOR_LANGUAGE'

PROMPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')
SYSTEM = 'system.md'
MESSAGES = 'messages.json'

CYRILLIC_RE = re.compile('[Ѐ-ӿ]')
LATIN_RE = re.compile('[A-Za-z]')
HEADER_RE = re.compile(r'\A\s*<!--.*?-->\s*', re.S)


def languages():
    """The available languages."""
    return sorted(name for name in os.listdir(PROMPTS)
                  if os.path.isfile(os.path.join(PROMPTS, name, SYSTEM)))


def detect(text):
    """The language of a prompt by its letters."""
    cyrillic = len(CYRILLIC_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    return CYRILLIC_LANGUAGE if cyrillic > latin else DEFAULT


def choose(language, prompt, environ=None):
    """The language of a run: detected from the prompt for AUTO; a prompt
    without a majority of letters takes the editor's language, else DEFAULT."""
    if not language or language == AUTO:
        text = prompt or ''
        cyrillic = len(CYRILLIC_RE.findall(text))
        latin = len(LATIN_RE.findall(text))
        if cyrillic != latin:
            language = detect(text)
        else:
            editor = (os.environ if environ is None else environ).get(EDITOR_LANGUAGE, '')
            language = editor if editor in languages() else DEFAULT
    if language not in languages():
        raise ConfigError('unknown language {!r}: {}'.format(
            language, ', '.join([AUTO] + languages())))
    return language


class Texts:
    """The texts of a language."""

    def __init__(self, language):
        if language not in languages():
            raise ConfigError('unknown language {!r}'.format(language))
        self.language = language
        folder = os.path.join(PROMPTS, language)
        with open(os.path.join(folder, SYSTEM), encoding='utf-8') as source:
            self.system = HEADER_RE.sub('', source.read(), count=1)
        with open(os.path.join(folder, MESSAGES), encoding='utf-8') as source:
            self.messages = json.load(source)

    def text(self, key, **fields):
        return self.messages[key].format(**fields)

    def message(self, issue):
        """The message of an issue without its line."""
        text = self.text(issue.code, **issue.fields)
        if issue.severity == WARNING:
            text = self.text('warning', text=text)
        return text

    def change(self, change):
        """The message of a change of the patch."""
        return self.text(change.code, **change.fields)

    def render(self, issue):
        """line N: message."""
        text = self.text(issue.code, **issue.fields)
        if issue.line is not None:
            text = self.text('line', line=issue.line, text=text)
        if issue.severity == WARNING:
            text = self.text('warning', text=text)
        return text

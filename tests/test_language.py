# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the languages and their texts
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

import os
import re
import string

import pytest

from conftest import ROOT
from hsm_maker import language as L
from hsm_maker.client import ConfigError
from hsm_maker.notation import Issue, WARNING

SOURCES = [os.path.join(ROOT, 'hsm_maker', name)
           for name in ('notation.py', 'builder.py')]


def fields(template):
    return sorted(name for _, name, _, _ in
                  string.Formatter().parse(template) if name)


def test_languages():
    assert L.languages() == ['en', 'ru']


@pytest.mark.parametrize('text, language', [
    ('A lift with a call button', 'en'), ('Лифт с кнопкой вызова', 'ru'),
    ('Лифт: CALL, FLOOR, TIMEOUT events', 'en'), ('', 'en')])
def test_detect(text, language):
    assert L.detect(text) == language


def test_choose():
    assert L.choose(L.AUTO, 'Тостер') == 'ru'
    assert L.choose(None, 'Toaster') == 'en'
    assert L.choose('ru', 'Toaster') == 'ru'
    with pytest.raises(ConfigError):
        L.choose('de', 'Toaster')


def test_same_keys_and_fields():
    english = L.Texts('en').messages
    for language in L.languages():
        messages = L.Texts(language).messages
        assert sorted(messages) == sorted(english), language
        for key, template in messages.items():
            assert fields(template) == fields(english[key]), (language, key)


def test_every_code_has_a_text():
    used = set()
    for path in SOURCES:
        with open(path, encoding='utf-8') as source:
            used |= set(re.findall(r"(?:Issue|_Fail)\('([A-Z]\d\d)'",
                                   source.read()))
    assert used and used <= set(L.Texts('en').messages)


def test_documented_texts():
    with open(os.path.join(ROOT, 'docs', 'NOTATION.md'),
              encoding='utf-8') as source:
        table = dict(re.findall(r'^\| ([NRSWB]\d\d) \| (.*) \|$',
                                source.read(), re.M))
    english = L.Texts('en').messages
    assert {code: text.replace('\\\\', '\\') for code, text in
            table.items()} == {code: english[code] for code in table}
    assert set(table) == {k for k in english if re.match(r'[A-Z]\d\d$', k)}


def test_system_prompts_without_header():
    assert L.Texts('en').system.startswith('You turn a description')
    assert L.Texts('ru').system.startswith('Ты преобразуешь описание')
    for language in L.languages():
        assert '<!--' not in L.Texts(language).system


def test_render():
    texts = L.Texts('en')
    assert texts.render(Issue('N04')) == 'the diagram has no machine'
    assert texts.render(Issue('S05', 3, name='M')) == \
        "line 3: machine 'M' is empty"
    assert texts.render(Issue('W01', 7, WARNING, name='B')) == \
        "warning: line 7: 'B' is unreachable"
    assert texts.message(Issue('W01', 7, WARNING, name='B')) == \
        "warning: 'B' is unreachable"
    assert L.Texts('ru').render(Issue('S05', 3, name='M')) == \
        "строка 3: машина 'M' пуста"

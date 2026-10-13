# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the examples in the prompts and the documents
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

import pytest

from conftest import ROOT
from hsm_maker import language as L
from hsm_maker.maker import convert

BLOCK_RE = re.compile(r'```hsm\n(.*?)```', re.S)


def blocks(text):
    found = BLOCK_RE.findall(text)
    assert found
    return found


@pytest.mark.parametrize('language', L.languages())
def test_system_prompt_example(language):
    for block in blocks(L.Texts(language).system):
        conversion = convert(block)
        assert conversion.ok, conversion.errors
        assert conversion.warnings == []


def test_notation_document():
    with open(os.path.join(ROOT, 'docs', 'NOTATION.md'),
              encoding='utf-8') as source:
        for block in blocks(source.read()):
            assert convert(block).ok

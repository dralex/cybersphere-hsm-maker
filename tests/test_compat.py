# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the Python 3.8 syntax and of the source headers
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

import ast
import glob
import os

import pytest

from conftest import ROOT

OLDEST = (3, 8)
SOURCES = sorted(glob.glob(os.path.join(ROOT, 'hsm_maker', '*.py')) +
                 glob.glob(os.path.join(ROOT, 'tests', '*.py')))
PROMPTS = sorted(glob.glob(os.path.join(ROOT, 'hsm_maker', 'prompts', '*',
                                        '*.md')))
# the standard library of the newer versions
NEWER = ('removeprefix', 'removesuffix', 'functools.cache', 'zoneinfo',
         'graphlib', 'importlib.resources.files')
GENERICS = ('list', 'dict', 'set', 'tuple', 'type', 'frozenset')
HEADER = ('Cybersphere HSM Maker',
          'Copyright (C) 2026 Alexey Fedoseev <aleksey@fedoseev.net>',
          'GNU Lesser General Public')
HEADER_LINES = 21


def read(path):
    with open(path, encoding='utf-8') as source:
        return source.read()


def annotations(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation is not None:
            yield node.annotation
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.returns is not None:
            yield node.returns
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation


@pytest.mark.parametrize('path', SOURCES, ids=os.path.basename)
def test_python_38(path):
    text = read(path)
    tree = ast.parse(text, path, feature_version=OLDEST)
    if os.path.abspath(path) != os.path.abspath(__file__):
        for name in NEWER:
            assert name not in text, name
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
           and node.func.id == 'zip':
            assert 'strict' not in [k.arg for k in node.keywords]
    for annotation in annotations(tree):
        for node in ast.walk(annotation):
            assert not isinstance(node, ast.BinOp), 'X | Y'
            assert not (isinstance(node, ast.Subscript) and
                        isinstance(node.value, ast.Name) and
                        node.value.id in GENERICS), node.value.id


@pytest.mark.parametrize('path', SOURCES + PROMPTS, ids=os.path.basename)
def test_header(path):
    head = '\n'.join(read(path).split('\n')[:HEADER_LINES])
    for line in HEADER:
        assert line in head, line

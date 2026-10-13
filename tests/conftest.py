# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The test helpers
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

import json
import os
import subprocess
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)

DIAGRAMS = os.path.join(TESTS, 'diagrams')


def diagram(name):
    """The text of a notation file of tests/diagrams."""
    with open(os.path.join(DIAGRAMS, name), encoding='utf-8') as source:
        return source.read()


GOOD =os.path.join(TESTS, 'good')
VALIDATOR = os.path.join(os.path.dirname(ROOT), 'cyberiadaml-compat-tests')


def validate(path):
    """The ERROR and WARNING findings of the strict validator of
    cyberiadaml-compat-tests for a file; None when it is not found."""
    if not os.path.isdir(os.path.join(VALIDATOR, 'cgmlval')):
        return None
    result = subprocess.run([sys.executable, '-B', '-m', 'cgmlval', 'validate',
                             '--strict', '--json', os.path.abspath(path)],
                            cwd=VALIDATOR, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    report = json.loads(result.stdout.decode('utf-8'))
    return ['{} {}'.format(f['req'], f['message'])
            for entry in report for f in entry['findings']
            if f['severity'] in ('ERROR', 'WARNING')]

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

import http.server
import json
import os
import subprocess
import sys
import threading

import pytest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)

# HSM_MAKER_BACKEND=cml runs the tests on the pure-Python interface even
# where the binding is installed
if os.environ.get('HSM_MAKER_BACKEND') == 'cml':
    from cyberiadaml_py import cml  # pylint: disable=wrong-import-position
    sys.modules['CyberiadaML'] = cml

# the package is imported from the tree, not from an installation
from hsm_maker.client import Reply, RequestLimitError, Usage  # pylint: disable=wrong-import-position

DIAGRAMS = os.path.join(TESTS, 'diagrams')
POLL = 0.01
FAKE_INPUT = 100
FAKE_OUTPUT = 10


def diagram(name):
    """The text of a notation file of tests/diagrams."""
    with open(os.path.join(DIAGRAMS, name), encoding='utf-8') as source:
        return source.read()


GOOD =os.path.join(TESTS, 'good')

from hsm_maker.cyberiadaml import CyberiadaML  # pylint: disable=wrong-import-position,wrong-import-order
PURE_PYTHON = CyberiadaML.__name__ == 'cyberiadaml_py.cml'


def same_document(text, good):
    """A written document equals a recorded one: the bytes of the binding,
    which recorded them; the canonical dump of cyberiadaml-py for the
    pure-Python interface, whose writer formats the text its own way."""
    if not PURE_PYTHON:
        return text == good
    from cyberiadaml_py import core  # pylint: disable=import-outside-toplevel
    return core.dump(core.read(text)) == core.dump(core.read(good))
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


class Stub:
    """A local HTTP server answering a scripted queue of (status, body,
    headers) and recording every request as (path, headers, body)."""

    def __init__(self):
        self.answers = []
        self.requests = []
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # pylint: disable=invalid-name
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length).decode('utf-8'))
                headers = {k.lower(): v for k, v in self.headers.items()}
                stub.requests.append((self.path, headers, body))
                status, answer, headers = stub.answers.pop(0) \
                    if stub.answers else (500, {'error': 'no answer'}, {})
                data = answer if isinstance(answer, bytes) else \
                    json.dumps(answer).encode('utf-8')
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        self.url = 'http://127.0.0.1:{}/v1'.format(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       args=(POLL,), daemon=True)
        self.thread.start()

    def answer(self, body, status=200, headers=None):
        self.answers.append((status, body, headers or {}))

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def chat_answer(text, finish='stop', prompt_tokens=10, completion_tokens=5):
    return {'choices': [{'message': {'role': 'assistant', 'content': text},
                         'finish_reason': finish}],
            'usage': {'prompt_tokens': prompt_tokens,
                      'completion_tokens': completion_tokens}}


@pytest.fixture
def stub(monkeypatch):
    for name in ('http_proxy', 'HTTP_PROXY'):
        monkeypatch.delenv(name, raising=False)
    server = Stub()
    yield server
    server.close()


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith('HSM_MAKER_'):
            monkeypatch.delenv(name)


class FakeClient:
    """A scripted model: the answers in order, a text or (text, truncated);
    the request limit when they run out."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []
        self.usage = Usage()

    def complete(self, system, messages):
        if not self.answers:
            raise RequestLimitError('no more answers')
        self.calls.append((system, [dict(m) for m in messages]))
        answer = self.answers.pop(0)
        text, truncated = answer if isinstance(answer, tuple) \
            else (answer, False)
        spent = Usage(1, FAKE_INPUT, FAKE_OUTPUT)
        self.usage.add(spent)
        return Reply(text, spent, truncated)


def fenced(text):
    return 'The diagram:\n```hsm\n' + text + '```\n'

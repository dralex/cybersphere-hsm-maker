# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the command line
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

import io
import os

from conftest import DIAGRAMS, PNG, chat_answer, diagram, fenced, validate
from hsm_maker import cli
from hsm_maker.language import Texts

LIFT = os.path.join(DIAGRAMS, 'lift.hsm')
WRONG = 'machine M\n  initial -> A\n  state A\n    GO -> Missng\n'


def test_offline(tmp_path):
    out = tmp_path / 'lift.graphml'
    assert cli.main(['--notation', LIFT, '-o', str(out)]) == cli.EXIT_MADE
    assert validate(str(out)) in (None, [])


def test_offline_to_stdout(capfd):
    assert cli.main(['--notation', LIFT, '--geometry', 'none']) == \
        cli.EXIT_MADE
    assert 'geometry/ none' in capfd.readouterr().out


def test_offline_issues(tmp_path, capsys):
    bad = tmp_path / 'bad.hsm'
    bad.write_text(WRONG, encoding='utf-8')
    out = tmp_path / 'out.graphml'
    assert cli.main(['--notation', str(bad), '-o', str(out)]) == \
        cli.EXIT_NOT_MADE
    assert "bad.hsm:4: unknown target 'Missng'" in capsys.readouterr().err
    assert not out.exists()


def test_configuration_errors(capsys):
    assert cli.main(['a lift']) == cli.EXIT_USAGE
    assert 'HSM_MAKER_URL' in capsys.readouterr().err
    assert cli.main(['--url', 'https://api.example.org/v1', '--model', 'm',
                     'a lift']) == cli.EXIT_USAGE
    assert 'EXAMPLE_API_KEY' in capsys.readouterr().err
    assert cli.main(['--language', 'ru', '--notation', 'absent.hsm']) == \
        cli.EXIT_USAGE


def test_model_run(stub, tmp_path, capsys):
    stub.answer(chat_answer(fenced(WRONG)))
    stub.answer(chat_answer(fenced(diagram('lift.hsm'))))
    out = tmp_path / 'lift.graphml'
    notation = tmp_path / 'lift.hsm'
    assert cli.main(['--url', stub.url, '--model', 'm', '-o', str(out),
                     '--save-notation', str(notation), '-v',
                     'a lift']) == cli.EXIT_MADE
    err = capsys.readouterr().err
    assert '== round 1: requests: 1' in err and '== 1 issues' in err
    assert 'rounds: 2, requests: 2, input tokens: 20, output tokens: 10' in err
    assert notation.read_text(encoding='utf-8') == diagram('lift.hsm')
    assert validate(str(out)) in (None, [])
    assert stub.requests[0][2]['messages'][1]['content'] == 'a lift'


def test_not_made(stub, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('HSM_MAKER_URL', stub.url)
    monkeypatch.setenv('HSM_MAKER_MODEL', 'm')
    monkeypatch.setattr('sys.stdin', io.StringIO('a lift'))
    stub.answer(chat_answer(fenced(WRONG)))
    out = tmp_path / 'out.graphml'
    assert cli.main(['--rounds', '1', '-f', '-', '-o', str(out)]) == \
        cli.EXIT_NOT_MADE
    assert "line 4: unknown target 'Missng'" in capsys.readouterr().err
    assert not out.exists()


def test_request_limit(stub, capsys):
    stub.answer(chat_answer(fenced(WRONG)))
    assert cli.main(['--url', stub.url, '--model', 'm', '--max-requests', '1',
                     'a lift']) == cli.EXIT_NOT_MADE
    assert 'the request limit is reached' in capsys.readouterr().err


def test_server_error(stub, capsys):
    stub.answer({'error': 'unknown model'}, 400)
    assert cli.main(['--url', stub.url, '--model', 'm', 'a lift']) == \
        cli.EXIT_SERVER
    assert 'HTTP 400' in capsys.readouterr().err


def picture_files(tmp_path):
    picture = tmp_path / 'lift.png'
    picture.write_bytes(PNG)
    comment = tmp_path / 'comment.txt'
    comment.write_text('', encoding='utf-8')
    return str(picture), str(comment)


def test_picture(stub, tmp_path):
    picture, comment = picture_files(tmp_path)
    stub.answer(chat_answer(fenced(diagram('lift.hsm'))))
    out = tmp_path / 'lift.graphml'
    assert cli.main(['--url', stub.url, '--model', 'm', '--picture', picture,
                     '-f', comment, '-o', str(out)]) == cli.EXIT_MADE
    content = stub.requests[0][2]['messages'][1]['content']
    assert [part['type'] for part in content] == ['image_url', 'text']
    assert content[1]['text'] == Texts('en').text('picture_alone')
    assert validate(str(out)) in (None, [])


def test_picture_refused(tmp_path, capsys):
    picture, comment = picture_files(tmp_path)
    svg = tmp_path / 'lift.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>',
                   encoding='utf-8')
    assert cli.main(['--url', 'http://127.0.0.1:9/v1', '--model', 'm',
                     '--picture', str(svg), 'a lift']) == cli.EXIT_USAGE
    assert 'export it as PNG' in capsys.readouterr().err
    assert cli.main(['--notation', LIFT, '--picture', picture]) == \
        cli.EXIT_USAGE
    assert '--picture needs the model' in capsys.readouterr().err
    assert cli.main(['--url', 'http://127.0.0.1:9/v1', '--model', 'm',
                     '-f', comment]) == cli.EXIT_USAGE
    assert 'give a description' in capsys.readouterr().err


def test_no_picture(stub, tmp_path, capsys):
    picture, _ = picture_files(tmp_path)
    stub.answer(chat_answer('NO PICTURE'))
    out = tmp_path / 'lift.graphml'
    assert cli.main(['--url', stub.url, '--model', 'm', '--picture', picture,
                     '-o', str(out), 'a lift']) == cli.EXIT_NOT_MADE
    assert 'the model does not see the picture' in capsys.readouterr().err
    assert not out.exists()

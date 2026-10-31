# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the client of the model servers
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

import base64
import socket

import pytest

from conftest import PNG, chat_answer
from hsm_maker import client as C

MESSAGES = [{'role': 'user', 'content': 'make it'}]


def make(stub, protocol=C.CHAT_COMPLETIONS, key='secret', **options):
    pauses = []
    client = C.Client(protocol, stub.url, 'model-1', key,
                      sleep=pauses.append, **options)
    return client, pauses


def test_chat_completions(stub):
    stub.answer(chat_answer('```hsm\nmachine M\n```', prompt_tokens=12,
                            completion_tokens=7))
    client, _ = make(stub)
    reply = client.complete('the system', MESSAGES)
    assert reply.text == '```hsm\nmachine M\n```'
    assert not reply.truncated
    path, headers, body = stub.requests[0]
    assert path == '/v1/chat/completions'
    assert headers['authorization'] == 'Bearer secret'
    assert body == {'model': 'model-1', 'messages': [
        {'role': 'system', 'content': 'the system'},
        {'role': 'user', 'content': 'make it'}]}
    assert (reply.usage.input_tokens, reply.usage.output_tokens) == (12, 7)
    assert str(client.usage) == 'requests: 1, input tokens: 12, ' \
        'output tokens: 7'


def test_messages(stub):
    stub.answer({'content': [{'type': 'thinking', 'thinking': '...'},
                             {'type': 'text', 'text': 'machine '},
                             {'type': 'text', 'text': 'M'}],
                 'stop_reason': 'max_tokens',
                 'usage': {'input_tokens': 20, 'output_tokens': 30}})
    client, _ = make(stub, C.MESSAGES, max_tokens=100)
    reply = client.complete('the system', MESSAGES)
    assert reply.text == 'machine M'
    assert reply.truncated
    path, headers, body = stub.requests[0]
    assert path == '/v1/messages'
    assert headers['x-api-key'] == 'secret'
    assert headers[C.MESSAGES_VERSION[0]] == C.MESSAGES_VERSION[1]
    assert body == {'model': 'model-1', 'max_tokens': 100,
                    'system': 'the system', 'messages': MESSAGES}
    assert (client.usage.input_tokens, client.usage.output_tokens) == (20, 30)


def test_no_key_no_header(stub):
    stub.answer(chat_answer('x'))
    client, _ = make(stub, key=None)
    client.complete('s', MESSAGES)
    assert 'authorization' not in stub.requests[0][1]


def test_length_cut(stub):
    stub.answer(chat_answer('machine', finish='length'))
    assert make(stub)[0].complete('s', MESSAGES).truncated


def test_retry_after(stub):
    stub.answer({'error': 'busy'}, 429, {'Retry-After': '7'})
    stub.answer({'error': 'down'}, 503)
    stub.answer(chat_answer('ok'))
    client, pauses = make(stub)
    assert client.complete('s', MESSAGES).text == 'ok'
    assert pauses == [7.0, C.BACKOFF * 2]
    assert client.usage.requests == 3


def test_client_error_is_not_retried(stub):
    stub.answer({'error': 'bad model'}, 400)
    client, pauses = make(stub)
    with pytest.raises(C.ClientError) as error:
        client.complete('s', MESSAGES)
    assert 'HTTP 400' in str(error.value) and 'bad model' in str(error.value)
    assert 'secret' not in str(error.value)
    assert not pauses and client.usage.requests == 1


def test_server_errors_exhaust_the_retries(stub):
    for _ in range(C.RETRIES):
        stub.answer({'error': 'down'}, 500)
    client, pauses = make(stub)
    with pytest.raises(C.ClientError):
        client.complete('s', MESSAGES)
    assert len(pauses) == C.RETRIES - 1


def test_no_retries_still_sends(stub):
    stub.answer({'error': 'down'}, 500)
    client, pauses = make(stub, retries=0)
    with pytest.raises(C.ClientError):
        client.complete('s', MESSAGES)
    assert (len(stub.requests), pauses) == (1, [])


def test_unreachable():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    pauses = []
    client = C.Client(C.CHAT_COMPLETIONS, 'http://127.0.0.1:{}'.format(port),
                      'm', sleep=pauses.append)
    with pytest.raises(C.ClientError) as error:
        client.complete('s', MESSAGES)
    assert 'cannot reach' in str(error.value)
    assert (error.value.status, error.value.kind) == (None, C.NETWORK)
    assert len(pauses) == C.RETRIES - 1


@pytest.mark.parametrize('answer', [
    {'choices': []}, {'nothing': 1}, b'not json'])
def test_malformed(stub, answer):
    stub.answer(answer)
    with pytest.raises(C.ClientError):
        make(stub)[0].complete('s', MESSAGES)


def test_request_limit(stub):
    stub.answer(chat_answer('a'))
    client, _ = make(stub, max_requests=1)
    client.complete('s', MESSAGES)
    with pytest.raises(C.RequestLimitError):
        client.complete('s', MESSAGES)
    assert len(stub.requests) == 1


@pytest.mark.parametrize('url, expected', [
    ('https://api.deepseek.com/v1', 'DEEPSEEK_API_KEY'),
    ('https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY'),
    ('https://my-models.example.org', 'EXAMPLE_API_KEY'),
    ('http://127.0.0.1:8080/v1', None),
    ('http://localhost:8080/v1', None),
])
def test_conventional_key_env(url, expected):
    assert C.conventional_key_env(url) == expected


@pytest.mark.parametrize('url, local', [
    ('http://localhost:1/v1', True), ('http://127.0.0.2/v1', True),
    ('http://[::1]:8000', True), ('http://models.localhost', True),
    ('https://api.deepseek.com', False), ('http://10.0.0.1', False)])
def test_is_local(url, local):
    assert C.is_local(url) == local


def test_resolve_key():
    url = 'https://api.deepseek.com/v1'
    environ = {'DEEPSEEK_API_KEY': 'conventional', 'HSM_MAKER_API_KEY': 'own',
               'MINE': 'named'}
    assert C.resolve_key(url, 'MINE', environ) == 'named'
    assert C.resolve_key(url, None, environ) == 'own'
    del environ['HSM_MAKER_API_KEY']
    assert C.resolve_key(url, None, environ) == 'conventional'
    with pytest.raises(C.ConfigError):
        C.resolve_key(url, 'ABSENT', environ)
    with pytest.raises(C.ConfigError) as error:
        C.resolve_key(url, None, {})
    assert 'DEEPSEEK_API_KEY' in str(error.value)
    assert C.resolve_key('http://localhost:8080/v1', None, {}) is None


def test_from_environment():
    environ = {'HSM_MAKER_URL': 'https://api.deepseek.com/v1',
               'HSM_MAKER_MODEL': 'flash', 'DEEPSEEK_API_KEY': 'k'}
    client = C.from_environment(environ=environ, timeout=None, retries=2)
    assert (client.protocol, client.url, client.model, client.key,
            client.retries) == (C.CHAT_COMPLETIONS,
                                'https://api.deepseek.com/v1', 'flash', 'k', 2)
    client = C.from_environment(protocol=C.MESSAGES, url='http://localhost/x/',
                                model='m', environ={})
    assert (client.protocol, client.url, client.key) == \
        (C.MESSAGES, 'http://localhost/x', None)
    with pytest.raises(C.ConfigError):
        C.from_environment(model='m', environ={})
    with pytest.raises(C.ConfigError):
        C.from_environment(url='http://localhost', environ={})
    with pytest.raises(C.ConfigError):
        C.from_environment(protocol='rest', url='http://localhost',
                           model='m', environ={})


PICTURE = [{'role': 'user', 'content': 'make it',
            'images': [C.Image(PNG, C.PNG, 'lift.png')]}]
ENCODED = base64.b64encode(PNG).decode('ascii')


def test_chat_completions_picture(stub):
    stub.answer(chat_answer('machine M'))
    make(stub)[0].complete('the system', PICTURE)
    assert stub.requests[0][2]['messages'][1] == {'role': 'user', 'content': [
        {'type': 'image_url',
         'image_url': {'url': 'data:image/png;base64,' + ENCODED}},
        {'type': 'text', 'text': 'make it'}]}


def test_messages_picture(stub):
    stub.answer({'content': [{'type': 'text', 'text': 'M'}], 'usage': {}})
    make(stub, C.MESSAGES)[0].complete('the system', PICTURE)
    assert stub.requests[0][2]['messages'] == [{'role': 'user', 'content': [
        {'type': 'image', 'source': {'type': 'base64',
                                     'media_type': 'image/png',
                                     'data': ENCODED}},
        {'type': 'text', 'text': 'make it'}]}]


@pytest.mark.parametrize('data, media_type', [
    (PNG, C.PNG), (b'\xff\xd8\xff\xe0' + bytes(8), C.JPEG),
    (b'GIF87a', C.GIF), (b'GIF89a' + bytes(4), C.GIF),
    (b'RIFF\x10\x00\x00\x00WEBPVP8 ', C.WEBP),
    (b'RIFF\x10\x00\x00\x00WAVEfmt ', None), (b'BM', None), (b'', None)])
def test_image_type(data, media_type):
    assert C.image_type(data) == media_type


def test_load_picture(tmp_path):
    path = tmp_path / 'lift.png'
    path.write_bytes(PNG)
    image = C.load_picture(str(path))
    assert (image.data, image.media_type, image.name) == \
        (PNG, C.PNG, 'lift.png')
    assert image.data_url() == 'data:image/png;base64,' + ENCODED
    with pytest.raises(OSError):
        C.load_picture(str(tmp_path / 'absent.png'))


@pytest.mark.parametrize('data, message', [
    (b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg">',
     'is an SVG: export it as PNG'),
    (b'%PDF-1.7', 'is not PNG, JPEG, GIF or WebP'),
    (b'', 'is not PNG, JPEG, GIF or WebP')])
def test_refused_pictures(tmp_path, data, message):
    path = tmp_path / 'picture'
    path.write_bytes(data)
    with pytest.raises(C.ConfigError, match=message):
        C.load_picture(str(path))


def test_large_picture(tmp_path, monkeypatch):
    monkeypatch.setattr(C, 'MAX_IMAGE', len(PNG) - 1)
    path = tmp_path / 'lift.png'
    path.write_bytes(PNG)
    with pytest.raises(C.ConfigError, match='is larger than'):
        C.load_picture(str(path))


@pytest.mark.parametrize('status', [401, 402, 404])
def test_http_status(stub, status):
    stub.answer({'error': 'refused'}, status)
    with pytest.raises(C.ClientError) as error:
        make(stub)[0].complete('s', MESSAGES)
    assert (error.value.status, error.value.kind) == (status, C.HTTP)


def test_server_status_after_retries(stub):
    for _ in range(C.RETRIES):
        stub.answer({'error': 'down'}, 503)
    with pytest.raises(C.ClientError) as error:
        make(stub)[0].complete('s', MESSAGES)
    assert error.value.status == 503


def test_timeout():
    # a server that takes the connection and never answers
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        client = C.Client(C.CHAT_COMPLETIONS, 'http://127.0.0.1:{}'.format(
            server.getsockname()[1]), 'm', timeout=0.2, retries=1)
        with pytest.raises(C.ClientError) as error:
            client.complete('s', MESSAGES)
    assert error.value.kind == C.TIMED_OUT
    assert 'no answer from' in str(error.value)


def test_malformed_kind(stub):
    stub.answer({'choices': []})
    with pytest.raises(C.ClientError) as error:
        make(stub)[0].complete('s', MESSAGES)
    assert error.value.kind == C.ANSWER


def test_key_hint():
    with pytest.raises(C.ConfigError) as error:
        C.resolve_key('https://api.example.org/v1', environ={})
    assert error.value.hint == C.KEY_HINT
    with pytest.raises(C.ConfigError) as error:
        C.resolve_key('https://api.example.org/v1', 'MY_KEY', environ={})
    assert error.value.hint == C.KEY_HINT

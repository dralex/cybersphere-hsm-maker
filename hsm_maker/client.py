# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The client of the model servers
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

"""The model servers of the chat-completions and the messages protocols,
over urllib: retries, the request limit, the usage, the key."""

import ipaddress
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

CHAT_COMPLETIONS = 'chat-completions'
MESSAGES = 'messages'
PROTOCOLS = (CHAT_COMPLETIONS, MESSAGES)

TIMEOUT = 300.0
RETRIES = 3
BACKOFF = 2.0
RETRY_AFTER_LIMIT = 60.0
MAX_REQUESTS = 16
MAX_TOKENS = 8192
ERROR_TEXT = 500
TOO_MANY = 429
SERVER_ERRORS = 500

# the version header the messages protocol requires
MESSAGES_VERSION = ('anthropic-version', '2023-06-01')

ENV_PROTOCOL = 'HSM_MAKER_PROTOCOL'
ENV_URL = 'HSM_MAKER_URL'
ENV_MODEL = 'HSM_MAKER_MODEL'
ENV_KEY_ENV = 'HSM_MAKER_KEY_ENV'
ENV_KEY = 'HSM_MAKER_API_KEY'
KEY_SUFFIX = '_API_KEY'


class ConfigError(Exception):
    """A missing or bad option, URL, model or key."""


class ClientError(Exception):
    """The server failed or answered something unreadable."""


class RequestLimitError(ClientError):
    """The request limit is reached."""


class Usage:
    """The requests and the tokens."""

    def __init__(self, requests=0, input_tokens=0, output_tokens=0):
        self.requests = requests
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def add(self, usage):
        self.requests += usage.requests
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    def __str__(self):
        return 'requests: {}, input tokens: {}, output tokens: {}'.format(
            self.requests, self.input_tokens, self.output_tokens)


class Reply:
    """An answer of the model."""

    def __init__(self, text, usage, truncated=False):
        self.text = text
        self.usage = usage
        self.truncated = truncated


def _host(url):
    try:
        return urllib.parse.urlsplit(url).hostname
    except ValueError:
        return None


def _address(host):
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def is_local(url):
    """Whether the server is on the local host."""
    host = _host(url)
    if not host:
        return False
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    address = _address(host)
    return address is not None and address.is_loopback


def conventional_key_env(url):
    """The conventional key variable of the server: the second-level name
    of the host in capitals with _API_KEY; None for an address."""
    host = _host(url)
    if not host or _address(host) is not None:
        return None
    labels = host.split('.')
    if len(labels) < 2:
        return None
    return re.sub(r'\W', '_', labels[-2].upper()) + KEY_SUFFIX


def resolve_key(url, key_env=None, environ=None):
    """The key for the server; None for a local server without a key."""
    environ = os.environ if environ is None else environ
    if key_env:
        if not environ.get(key_env):
            raise ConfigError('the key variable {} is not set'.format(key_env))
        return environ[key_env]
    if environ.get(ENV_KEY):
        return environ[ENV_KEY]
    if is_local(url):
        return None
    conventional = conventional_key_env(url)
    if conventional and environ.get(conventional):
        return environ[conventional]
    raise ConfigError('no key for {}: set {}{}, or name the variable with '
                      '--key-env'.format(_host(url) or url, ENV_KEY,
                                         ' or ' + conventional
                                         if conventional else ''))


class Client:
    """A client of one model."""

    def __init__(self, protocol, url, model, key=None, timeout=TIMEOUT,
                 retries=RETRIES, max_requests=MAX_REQUESTS,
                 max_tokens=MAX_TOKENS, sleep=time.sleep):
        if protocol not in PROTOCOLS:
            raise ConfigError('unknown protocol {!r}: {}'.format(
                protocol, ', '.join(PROTOCOLS)))
        if not url or not _host(url):
            raise ConfigError('bad server URL {!r}'.format(url))
        if not model:
            raise ConfigError('no model name')
        self.protocol = protocol
        self.url = url.rstrip('/')
        self.model = model
        self.key = key
        self.timeout = timeout
        self.retries = retries
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.sleep = sleep
        self.usage = Usage()

    def complete(self, system, messages):
        """Send the system prompt and the messages; return a Reply."""
        messages = [{'role': m['role'], 'content': m['content']}
                    for m in messages]
        if self.protocol == CHAT_COMPLETIONS:
            headers = {}
            if self.key:
                headers['Authorization'] = 'Bearer ' + self.key
            body = {'model': self.model,
                    'messages': [{'role': 'system', 'content': system}] +
                    messages}
            answer = self._post('/chat/completions', headers, body)
            return self._chat_reply(answer)
        headers = dict([MESSAGES_VERSION])
        if self.key:
            headers['x-api-key'] = self.key
        body = {'model': self.model, 'max_tokens': self.max_tokens,
                'system': system, 'messages': messages}
        return self._messages_reply(self._post('/messages', headers, body))

    def _chat_reply(self, answer):
        try:
            choice = answer['choices'][0]
            text = choice['message'].get('content') or ''
            usage = answer.get('usage') or {}
            spent = Usage(1, usage.get('prompt_tokens', 0),
                          usage.get('completion_tokens', 0))
            truncated = choice.get('finish_reason') == 'length'
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise ClientError('malformed answer: {!r}'.format(error)) from None
        return self._reply(text, spent, truncated)

    def _messages_reply(self, answer):
        try:
            text = ''.join(block.get('text', '') for block in answer['content']
                           if block.get('type') == 'text')
            usage = answer.get('usage') or {}
            spent = Usage(1, usage.get('input_tokens', 0),
                          usage.get('output_tokens', 0))
            truncated = answer.get('stop_reason') == 'max_tokens'
        except (KeyError, TypeError, AttributeError) as error:
            raise ClientError('malformed answer: {!r}'.format(error)) from None
        return self._reply(text, spent, truncated)

    def _reply(self, text, spent, truncated):
        # the requests are counted when sent, the tokens when answered
        self.usage.add(Usage(0, spent.input_tokens, spent.output_tokens))
        return Reply(text, spent, truncated)

    def _pause(self, attempt, error):
        pause = BACKOFF * (2 ** attempt)
        retry_after = error.headers.get('Retry-After') \
            if isinstance(error, urllib.error.HTTPError) and error.headers \
            else None
        if retry_after:
            try:
                pause = min(float(retry_after), RETRY_AFTER_LIMIT)
            except ValueError:
                pass
        self.sleep(pause)

    def _post(self, path, headers, body):
        url = self.url + path
        data = json.dumps(body).encode('utf-8')
        failure = None
        for attempt in range(self.retries):
            if self.usage.requests >= self.max_requests:
                raise RequestLimitError('the request limit {} is reached'
                                        .format(self.max_requests))
            self.usage.requests += 1
            request = urllib.request.Request(
                url, data=data, method='POST',
                headers=dict(headers, **{'Content-Type': 'application/json'}))
            try:
                with urllib.request.urlopen(request,
                                            timeout=self.timeout) as answer:
                    return json.loads(answer.read().decode('utf-8'))
            except urllib.error.HTTPError as error:
                text = error.read().decode('utf-8', 'replace')[:ERROR_TEXT]
                failure = ClientError('HTTP {} from {}: {}'.format(
                    error.code, url, text))
                if error.code != TOO_MANY and error.code < SERVER_ERRORS:
                    raise failure from None
                last = error
            except ValueError as error:
                raise ClientError('unreadable answer from {}: {}'.format(
                    url, error)) from None
            except (urllib.error.URLError, OSError) as error:
                failure = ClientError('cannot reach {}: {}'.format(url, error))
                last = error
            if attempt + 1 < self.retries:
                self._pause(attempt, last)
        raise failure


def from_environment(protocol=None, url=None, model=None, key=None,
                     key_env=None, environ=None, **options):
    """A Client from the arguments, else from the HSM_MAKER_* variables."""
    environ = os.environ if environ is None else environ
    protocol = protocol or environ.get(ENV_PROTOCOL) or CHAT_COMPLETIONS
    url = url or environ.get(ENV_URL)
    if not url:
        raise ConfigError('give --url or set ' + ENV_URL)
    model = model or environ.get(ENV_MODEL)
    if not model:
        raise ConfigError('give --model or set ' + ENV_MODEL)
    if key is None:
        key = resolve_key(url, key_env or environ.get(ENV_KEY_ENV), environ)
    options = {name: value for name, value in options.items()
               if value is not None}
    return Client(protocol, url, model, key, **options)

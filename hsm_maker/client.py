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
over urllib: the pictures, retries, the request limit, the usage, the key."""

import base64
import ipaddress
import json
import os
import re
import socket
import struct
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

# the raster pictures the servers read, by their first bytes
PNG = 'image/png'
JPEG = 'image/jpeg'
GIF = 'image/gif'
WEBP = 'image/webp'
IMAGE_TYPES = (PNG, JPEG, GIF, WEBP)
IMAGE_MAGIC = ((b'\x89PNG\r\n\x1a\n', PNG), (b'\xff\xd8\xff', JPEG),
               (b'GIF87a', GIF), (b'GIF89a', GIF))
RIFF_MAGIC = b'RIFF'
WEBP_MAGIC = b'WEBP'
WEBP_OFFSET = len(RIFF_MAGIC) + 4
MEBIBYTE = 1024 * 1024
MAX_IMAGE = 20 * MEBIBYTE
SVG_HEAD = 1024
# the headers that carry the size of a picture
PNG_SIZE = struct.Struct('>II')
PNG_SIZE_AT = 16
GIF_SIZE = struct.Struct('<HH')
GIF_SIZE_AT = 6
JPEG_MARKER = 0xFF
# the start-of-frame markers; C4, C8 and CC are tables, not frames
JPEG_FRAMES = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
JPEG_STANDALONE = set(range(0xD0, 0xDA)) | {0x01}
JPEG_LENGTH = struct.Struct('>H')
JPEG_FRAME_SIZE = struct.Struct('>xHH')    # precision, height, width
WEBP_CHUNK_AT = 12
WEBP_DATA_AT = 20
VP8_SIZE = struct.Struct('<HH')
VP8_SIZE_AT = WEBP_DATA_AT + 6
VP8_DIMENSION = 0x3FFF
VP8L_BITS_AT = WEBP_DATA_AT + 1
VP8L_BITS = struct.Struct('<I')
VP8L_DIMENSION_BITS = 14
VP8X_SIZE_AT = WEBP_DATA_AT + 4
VP8X_DIMENSION = 3
SVG_RE = re.compile(rb'<svg[\s>]', re.I)

# the kinds of a ClientError
HTTP = 'http'
NETWORK = 'network'
TIMED_OUT = 'timeout'
ANSWER = 'answer'
# the hint of a missing key, in messages.json
KEY_HINT = 'hint_key'

ENV_PROTOCOL = 'HSM_MAKER_PROTOCOL'
ENV_URL = 'HSM_MAKER_URL'
ENV_MODEL = 'HSM_MAKER_MODEL'
ENV_KEY_ENV = 'HSM_MAKER_KEY_ENV'
ENV_KEY = 'HSM_MAKER_API_KEY'
KEY_SUFFIX = '_API_KEY'


class ConfigError(Exception):
    """A missing or bad option, URL, model or key; `hint` names the hint
    text in messages.json."""

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.hint = hint


class ClientError(Exception):
    """The server failed or answered something unreadable: the HTTP status
    and the kind of the failure."""

    def __init__(self, message, status=None, kind=HTTP):
        super().__init__(message)
        self.status = status
        self.kind = kind


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


class Image:
    """A raster picture for the model."""

    def __init__(self, data, media_type, name=None):
        self.data = data
        self.media_type = media_type
        self.name = name

    def base64(self):
        """The data in base64."""
        return base64.b64encode(self.data).decode('ascii')

    def data_url(self):
        """The data URL of the chat-completions protocol."""
        return 'data:{};base64,{}'.format(self.media_type, self.base64())


def image_type(data):
    """The media type of a raster picture by its first bytes; None for
    another format."""
    for magic, media_type in IMAGE_MAGIC:
        if data.startswith(magic):
            return media_type
    if data.startswith(RIFF_MAGIC) and \
            data[WEBP_OFFSET:WEBP_OFFSET + len(WEBP_MAGIC)] == WEBP_MAGIC:
        return WEBP
    return None


def _jpeg_size(data):
    at = 2
    while at + 4 <= len(data):
        if data[at] != JPEG_MARKER:
            return None
        marker = data[at + 1]
        if marker in JPEG_STANDALONE:
            at += 2
            continue
        if marker in JPEG_FRAMES and at + 9 <= len(data):
            height, width = JPEG_FRAME_SIZE.unpack_from(data, at + 4)
            return width, height
        at += 2 + JPEG_LENGTH.unpack_from(data, at + 2)[0]
    return None


def _webp_size(data):
    chunk = data[WEBP_CHUNK_AT:WEBP_CHUNK_AT + 4]
    if chunk == b'VP8 ' and len(data) >= VP8_SIZE_AT + VP8_SIZE.size:
        width, height = VP8_SIZE.unpack_from(data, VP8_SIZE_AT)
        return width & VP8_DIMENSION, height & VP8_DIMENSION
    if chunk == b'VP8L' and len(data) >= VP8L_BITS_AT + VP8L_BITS.size:
        bits = VP8L_BITS.unpack_from(data, VP8L_BITS_AT)[0]
        mask = (1 << VP8L_DIMENSION_BITS) - 1
        return (bits & mask) + 1, ((bits >> VP8L_DIMENSION_BITS) & mask) + 1
    if chunk == b'VP8X' and len(data) >= VP8X_SIZE_AT + 2 * VP8X_DIMENSION:
        width = int.from_bytes(data[VP8X_SIZE_AT:VP8X_SIZE_AT +
                                    VP8X_DIMENSION], 'little') + 1
        height = int.from_bytes(data[VP8X_SIZE_AT + VP8X_DIMENSION:
                                     VP8X_SIZE_AT + 2 * VP8X_DIMENSION],
                                'little') + 1
        return width, height
    return None


def image_size(data):
    """The (width, height) of a picture from its header; None when it cannot
    be read."""
    media_type = image_type(data)
    try:
        if media_type == PNG:
            return PNG_SIZE.unpack_from(data, PNG_SIZE_AT)
        if media_type == GIF:
            return GIF_SIZE.unpack_from(data, GIF_SIZE_AT)
        if media_type == JPEG:
            return _jpeg_size(data)
        if media_type == WEBP:
            return _webp_size(data)
    except struct.error:
        return None
    return None


def load_picture(path):
    """The Image of a file. Raise ConfigError for an SVG, another format or
    a file too large, OSError when it cannot be read."""
    with open(path, 'rb') as source:
        data = source.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        raise ConfigError('the picture {} is larger than {} MiB'.format(
            path, MAX_IMAGE // MEBIBYTE))
    media_type = image_type(data)
    if media_type is None:
        if SVG_RE.search(data[:SVG_HEAD]):
            raise ConfigError('the picture {} is an SVG: export it as PNG'
                              .format(path))
        raise ConfigError('the picture {} is not PNG, JPEG, GIF or WebP'
                          .format(path))
    return Image(data, media_type, os.path.basename(path))


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


def _timed_out(error):
    """Whether a network failure is a timeout, raised or wrapped."""
    timeouts = (socket.timeout, TimeoutError)
    return isinstance(error, timeouts) or \
        isinstance(getattr(error, 'reason', None), timeouts)


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
            raise ConfigError('the key variable {} is not set'.format(key_env),
                              KEY_HINT)
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
                                         if conventional else ''), KEY_HINT)


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
        messages = [self._message(m) for m in messages]
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

    def _message(self, message):
        """A message of the protocol: the pictures first, then the text."""
        images = message.get('images')
        if not images:
            return {'role': message['role'], 'content': message['content']}
        parts = [self._image(image) for image in images]
        parts.append({'type': 'text', 'text': message['content']})
        return {'role': message['role'], 'content': parts}

    def _image(self, image):
        if self.protocol == CHAT_COMPLETIONS:
            return {'type': 'image_url', 'image_url': {'url': image.data_url()}}
        return {'type': 'image', 'source': {'type': 'base64',
                                            'media_type': image.media_type,
                                            'data': image.base64()}}

    def _chat_reply(self, answer):
        try:
            choice = answer['choices'][0]
            text = choice['message'].get('content') or ''
            usage = answer.get('usage') or {}
            spent = Usage(1, usage.get('prompt_tokens', 0),
                          usage.get('completion_tokens', 0))
            truncated = choice.get('finish_reason') == 'length'
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise ClientError('malformed answer: {!r}'.format(error),
                              kind=ANSWER) from None
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
            raise ClientError('malformed answer: {!r}'.format(error),
                              kind=ANSWER) from None
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
        failure = last = None
        attempts = max(1, self.retries)
        for attempt in range(attempts):
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
                    error.code, url, text), error.code)
                if error.code != TOO_MANY and error.code < SERVER_ERRORS:
                    raise failure from None
                last = error
            except ValueError as error:
                raise ClientError('unreadable answer from {}: {}'.format(
                    url, error), kind=ANSWER) from None
            except (urllib.error.URLError, OSError) as error:
                failure = ClientError('no answer from {} in {:g} s'.format(
                    url, self.timeout), kind=TIMED_OUT) if _timed_out(error) \
                    else ClientError('cannot reach {}: {}'.format(url, error),
                                     kind=NETWORK)
                last = error
            if attempt + 1 < attempts:
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

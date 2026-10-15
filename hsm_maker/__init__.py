# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The package: the LLM-based maker of the CyberiadaML HSM diagrams
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

"""The LLM-based maker of the CyberiadaML HSM diagrams."""

__version__ = '0.1.0'

from .builder import GEOMETRY_FULL, GEOMETRY_NONE, GEOMETRY_UPDATE
from .client import (Client, ClientError, ConfigError, RequestLimitError,
                     Usage, from_environment)
from .language import AUTO
from .maker import (ROUNDS, Conversion, Result, change, convert, run,
                    run_update)
from .notation import Issue
from .patcher import Change
from .reader import ReadError

__all__ = ['GEOMETRY_FULL', 'GEOMETRY_NONE', 'GEOMETRY_UPDATE', 'AUTO',
           'ROUNDS', 'Client', 'ClientError', 'ConfigError',
           'RequestLimitError', 'Usage', 'Conversion', 'Result', 'Change',
           'Issue', 'ReadError', 'convert', 'change', 'run', 'run_update',
           'make', 'update']


def make(prompt, client=None, *, protocol=None, url=None, model=None,
         key=None, key_env=None, language=AUTO, code_language=AUTO,
         geometry=GEOMETRY_FULL, rounds=ROUNDS, max_requests=None,
         timeout=None, log=None):
    """Make a diagram from the description `prompt`; return a Result."""
    if client is None:
        client = from_environment(protocol, url, model, key, key_env,
                                  max_requests=max_requests, timeout=timeout)
    return run(prompt, client, language, geometry, rounds, log,
               code_language)


def update(graphml, prompt, client=None, *, protocol=None, url=None,
           model=None, key=None, key_env=None, language=AUTO,
           code_language=AUTO, geometry=GEOMETRY_UPDATE, rounds=ROUNDS,
           max_requests=None, timeout=None, log=None):
    """Change the diagram of the GraphML text by the description `prompt`;
    return a Result with the changes."""
    if client is None:
        client = from_environment(protocol, url, model, key, key_env,
                                  max_requests=max_requests, timeout=timeout)
    return run_update(graphml, prompt, client, language, geometry, rounds,
                      log, code_language)

# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The command line: hsm-maker
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

"""hsm-maker: a CyberiadaML HSM diagram from a description."""

import argparse
import json
import os
import sys

from . import __version__
from .builder import (CHANGE_GEOMETRIES, GEOMETRY_FULL, GEOMETRY_UPDATE,
                      ROUTINGS, ROUTING_ORTHOGONAL)
from .client import (ClientError, ConfigError, PROTOCOLS, from_environment,
                     load_picture)
from .language import AUTO, Texts, choose, languages
from .maker import ROUNDS, Original, change, convert, run, run_update
from .notation import ERROR, WARNING
from .placement import GEOMETRY_PICTURE, SIZES, SIZE_PICTURE
from .plugin import PLUGIN_ID, PluginError, install
from .reader import ReadError
from .report import PROGRAM, Report

EXIT_MADE = 0
# the check round of a run with a picture
CHECK_ON = 'on'
CHECK_OFF = 'off'
EXIT_NOT_MADE = 1
EXIT_USAGE = 2
EXIT_SERVER = 3

ENV_LANGUAGE = 'HSM_MAKER_LANGUAGE'
ENV_CODE_LANGUAGE = 'HSM_MAKER_CODE_LANGUAGE'
STDIN = '-'


def parser():
    commands = argparse.ArgumentParser(
        prog=PROGRAM,
        description='Make a CyberiadaML HSM diagram from a description of '
        'a system with a language model.')
    commands.add_argument('prompt', nargs='?',
                          help='the description of the system')
    commands.add_argument('-f', '--file', metavar='FILE',
                          help='read the description from a file, - for '
                          'the standard input')
    commands.add_argument('--notation', metavar='FILE',
                          help='convert a notation file without a model')
    commands.add_argument('--update', metavar='FILE',
                          help='change the diagram of the file; the prompt '
                          'describes the change')
    commands.add_argument('--render', metavar='FILE',
                          help='print the notation of the diagram')
    commands.add_argument('--picture', metavar='FILE', action='append',
                          dest='pictures',
                          help='a picture of the system: PNG, JPEG, GIF or '
                          'WebP; the prompt is its comment and may be empty; '
                          'repeatable')
    commands.add_argument('--install-editor-plugin', nargs='?', const='',
                          metavar='DIR',
                          help='install the editor plugin into DIR or the '
                          'user plugin folder of the editor, run by this '
                          'Python')
    commands.add_argument('-o', '--output', metavar='FILE',
                          help='the GraphML file; the standard output by '
                          'default')
    commands.add_argument('--diagnostics', metavar='FILE',
                          help='write the issues and the changes as the '
                          'editor diagnostics JSON')
    commands.add_argument('--geometry',
                          choices=CHANGE_GEOMETRIES + (GEOMETRY_PICTURE,),
                          help='full: lay the diagram out, update: keep the '
                          'drawing, none: no geometry, picture: arrange a '
                          'new diagram as its picture (full; update with '
                          '--update; picture with --picture)')
    commands.add_argument('--routing', choices=ROUTINGS,
                          default=ROUTING_ORTHOGONAL,
                          help='the routes of the transitions: orthogonal - '
                          'runs along and across the flow, polyline - '
                          'straight segments ({})'.format(ROUTING_ORTHOGONAL))
    commands.add_argument('--check-picture', nargs='?', const=CHECK_ON,
                          choices=(CHECK_ON, CHECK_OFF), default=CHECK_ON,
                          help='compare the made diagram with the picture '
                          'once more and take a correction ({})'.format(
                              CHECK_ON))
    commands.add_argument('--no-check-picture', dest='check_picture',
                          action='store_const', const=CHECK_OFF,
                          help='no check round')
    commands.add_argument('--picture-size', choices=SIZES,
                          default=SIZE_PICTURE,
                          help='the sizes of the picture layout: fit - from '
                          'the texts, picture - at least the picture\'s '
                          'proportions ({})'.format(SIZE_PICTURE))
    commands.add_argument('--language', choices=[AUTO] + languages(),
                          help='the language of the instructions '
                          '(${}, auto)'.format(ENV_LANGUAGE))
    commands.add_argument('--code-language', metavar='NAME',
                          help='the programming language of the actions: '
                          'auto (the model declares it) or a name, e.g. '
                          'Python (${}, auto)'.format(ENV_CODE_LANGUAGE))
    commands.add_argument('--save-notation', metavar='FILE',
                          help='write the last notation to a file')
    commands.add_argument('--rounds', type=int, default=ROUNDS,
                          help='the rounds of repair ({})'.format(ROUNDS))
    commands.add_argument('--max-requests', type=int, metavar='N',
                          help='the request limit')
    commands.add_argument('--timeout', type=float, metavar='SECONDS',
                          help='the timeout of a request')
    commands.add_argument('--protocol', choices=PROTOCOLS,
                          help='the protocol of the server '
                          '($HSM_MAKER_PROTOCOL, chat-completions)')
    commands.add_argument('--url', help='the server ($HSM_MAKER_URL)')
    commands.add_argument('--model', help='the model ($HSM_MAKER_MODEL)')
    commands.add_argument('--key-env', metavar='NAME',
                          help='the variable with the key '
                          '($HSM_MAKER_KEY_ENV)')
    commands.add_argument('-v', '--verbose', action='count', default=0,
                          help='show the dialog with the model: the messages '
                          'and the answers of every round; -vv adds the '
                          'system prompt')
    commands.add_argument('--version', action='version',
                          version='%(prog)s ' + __version__)
    return commands


def _read(path):
    if path == STDIN:
        return sys.stdin.read()
    with open(path, encoding='utf-8') as source:
        return source.read()


def _write(path, text):
    if path:
        with open(path, 'w', encoding='utf-8') as target:
            target.write(text)
    else:
        sys.stdout.buffer.write(text.encode('utf-8'))
        sys.stdout.flush()


def _prompt(options):
    if options.prompt and options.file:
        raise ConfigError('give either PROMPT or -f FILE')
    if options.prompt:
        text = options.prompt
    elif options.file:
        text = _read(options.file)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        text = ''
    if not text.strip() and not options.pictures:
        raise ConfigError('give a description: PROMPT, -f FILE or the '
                          'standard input')
    return text


def _say(text):
    print(text, file=sys.stderr)


def _diagnostics(path, texts, outcome):
    """The issues and the changes as the editor diagnostics JSON."""
    if not path:
        return
    entries = []
    for issue in outcome.errors + outcome.warnings:
        entries.append({'severity': ERROR if issue.severity == ERROR
                        else WARNING,
                        'message': texts.render(issue), 'rule': issue.code})
    for item in outcome.changes:
        entry = {'severity': 'info', 'message': texts.change(item),
                 'rule': item.code}
        if item.element:
            entry['element'] = item.element
        entries.append(entry)
    placed = getattr(outcome, 'placement', None)
    if placed is not None and placed.error is not None:
        entries.append({'severity': WARNING, 'rule': 'placement',
                        'message': texts.text('placement_failed',
                                              reason=placed.error)})
    with open(path, 'w', encoding='utf-8') as target:
        json.dump(entries, target, ensure_ascii=False, indent=1)


def _offline(options, language, graphml):
    notation = _read(options.notation)
    texts = Texts(choose(language, notation))
    if graphml is None:
        conversion = convert(notation, options.geometry,
                             options.code_language, options.routing)
    else:
        conversion = change(graphml, notation, options.geometry,
                            code_language=options.code_language,
                            routing=options.routing)
    for issue in conversion.errors + conversion.warnings:
        prefix = '{}:{}: '.format(options.notation, issue.line) \
            if issue.line is not None else '{}: '.format(options.notation)
        _say(prefix + texts.message(issue))
    _diagnostics(options.diagnostics, texts, conversion)
    if not conversion.ok:
        return EXIT_NOT_MADE
    _write(options.output, conversion.graphml)
    return EXIT_MADE


def _made(options, result, report):
    if options.save_notation and result.notation is not None:
        with open(options.save_notation, 'w', encoding='utf-8') as target:
            target.write(result.notation)
    _diagnostics(options.diagnostics, report.texts, result)
    report.summary(result)
    if not result.ok:
        return EXIT_NOT_MADE
    _write(options.output, result.graphml)
    return EXIT_MADE


def _original(options):
    """The text of the diagram to change; None for a new diagram (no
    --update, or an empty file: the empty document of the editor)."""
    if not options.update:
        return None
    text = _read(options.update)
    return text if text.strip() else None


def _install_plugin(target):
    folder = install(target or None)
    print('installed the editor plugin {} {} to\n  {}\nit runs {}; restart '
          'the editor'.format(PLUGIN_ID, __version__, folder, sys.executable))
    return EXIT_MADE


def _explain(report, error):
    """The error and its hint, in the language of the run when it is
    known."""
    if report is None:
        report = Report(Texts(choose(AUTO, '')), sys.stderr)
    report.explain(error)


def main(argv=None):
    options = parser().parse_args(argv)
    report = None
    language = options.language or os.environ.get(ENV_LANGUAGE) or AUTO
    options.code_language = options.code_language or \
        os.environ.get(ENV_CODE_LANGUAGE) or AUTO
    try:
        if options.install_editor_plugin is not None:
            return _install_plugin(options.install_editor_plugin)
        if options.pictures and (options.render or options.notation):
            raise ConfigError('--picture needs the model: not with --render '
                              'or --notation')
        if options.render:
            _write(None, Original(_read(options.render)).notation)
            return EXIT_MADE
        graphml = _original(options)
        if options.geometry is None:
            options.geometry = GEOMETRY_UPDATE if graphml is not None \
                else GEOMETRY_PICTURE if options.pictures else GEOMETRY_FULL
        if options.geometry == GEOMETRY_PICTURE and \
                (graphml is not None or options.notation):
            raise ConfigError('--geometry picture draws a new diagram by a '
                              'model: not with --update or --notation')
        if options.notation:
            return _offline(options, language, graphml)
        prompt = _prompt(options)
        # the messages go beside a document written to a file, else beside
        # the errors
        report = Report(Texts(choose(language, prompt)),
                        sys.stdout if options.output else sys.stderr,
                        options.verbose, rounds=options.rounds)
        pictures = [load_picture(path) for path in options.pictures or ()]
        client = from_environment(options.protocol, options.url,
                                  options.model, key_env=options.key_env,
                                  max_requests=options.max_requests,
                                  timeout=options.timeout)
        report.model = client.model
        if graphml is None:
            result = run(prompt, client, language, options.geometry,
                         options.rounds, report.log, options.code_language,
                         pictures, report.trace, options.picture_size,
                         options.routing, options.check_picture == CHECK_ON)
        else:
            result = run_update(graphml, prompt, client, language,
                                options.geometry, options.rounds, report.log,
                                options.code_language, pictures,
                                report.trace, options.routing)
        return _made(options, result, report)
    except (ConfigError, ReadError, PluginError) as error:
        _explain(report, error)
        return EXIT_USAGE
    except OSError as error:
        _explain(report, error)
        return EXIT_USAGE
    except ClientError as error:
        _explain(report, error)
        return EXIT_SERVER


if __name__ == '__main__':
    sys.exit(main())

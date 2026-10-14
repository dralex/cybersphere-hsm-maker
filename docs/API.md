# The Cybersphere HSM Maker Interface Specification

Document version: 0.3 (2026-10-14)

The package `hsm_maker` and the command `hsm-maker`. The reasons are in
`ARCHITECTURE.md`, the notation and its issue codes in `NOTATION.md`.

## Package hsm_maker

* `__version__` - the version of the package.
* `make(prompt, client=None, *, protocol=None, url=None, model=None,
  key=None, key_env=None, language='auto', geometry='full', rounds=3,
  max_requests=None, timeout=None, log=None)` - make a diagram from the
  description `prompt`; return a `Result`; `log` as in `maker.run`.
  Without `client` a `Client` is created from the arguments and the
  environment (`client.from_environment`). Raises `ConfigError` for a bad
  configuration and `ClientError` when the server fails.

* `update(graphml, prompt, client=None, *, ...)` - change the diagram of the
  GraphML text by the description of the change `prompt`; the keywords of
  `make`, with `geometry='update'`. Returns a `Result` with the changes.
  Raises `ReadError` when the diagram cannot be read or shown in the
  notation.

The names `Result`, `Conversion`, `Change`, `Issue`, `Client`, `Usage`,
`ConfigError`, `ClientError`, `ReadError`, `convert`, `change`, `run` and
`run_update` are exported by the package too.

## Module notation

The notation tree, its parser and its checks. It does not use the binding.

* `MACHINE`, `STATE`, `INITIAL`, `FINAL`, `TERMINATE`, `CHOICE`, `HISTORY`,
  `DEEP_HISTORY`, `ENTRY_POINT`, `EXIT_POINT`, `SUBMACHINE` - the kinds of
  the vertices.
* `ERROR`, `WARNING` - the severities of the issues.
* `Issue(code, line=None, severity=ERROR, **fields)` - an issue: the code of
  `NOTATION.md`, the line (counted from 1, `None` for the whole text) and
  the fields of the message.
* `NotationError(issues)` - the syntax errors of a text; `issues` lists
  them all.
* `Diagram` - the tree: `name`, `description`, `machines` (the vertices of
  the kind `MACHINE`), `notes` (`(vertex or None, text)`, written as `#
  note:` lines), `walk()` (every vertex in the notation order).
* `Vertex` - a machine, a state, a submachine, a pseudostate or a point:
  `kind`, `name`, `line`, `parent`, `children`, `behaviours`, `internals`
  (the internal transitions), `transitions` (the outgoing transitions),
  `reference` (the machine name of a submachine), `was` (the `(was OLD)`
  text), `element_id` (set by the reader), `machine`, `path` (the
  qualified name in the machine, `Moving::MovingUp`), `walk()`.
* `Behaviour` - `entry/` or `exit/`: `kind` (`'entry'`, `'exit'`),
  `action`, `line`.
* `Transition` - `line`, `source`, `event`, `guard`, `action`,
  `propagation` (`''`, `'propagate'`, `'block'`, `'defer'`), `target_ref`
  (the text after `->`, `None` for an internal transition), `target` (the
  vertex, set by `analyze`), `element_id` (set by the reader).
* `extract(answer)` - the first fenced block of a model answer, or the
  whole answer when it has none.
* `parse(text)` - read the notation; return a `Diagram`. Raises
  `NotationError` with every syntax issue.
* `analyze(diagram, changing=False)` - resolve the targets and check the
  semantics; return the list of issues, errors and warnings, ordered by
  line. A new diagram (`changing` false) refuses `(was OLD)` and `_` names.
* `render(diagram)` - the notation text of a tree, with the notes; the
  targets by name, by path where the name is not enough.

## Module builder

The tree to a `CyberiadaML.Document`.

* `GEOMETRY_FULL`, `GEOMETRY_NONE`, `GEOMETRY_UPDATE` - `'full'`, `'none'`
  and `'update'`.
* `BINDING_ERRORS` - the tuple of the exception classes of the binding.
* `BuildError(issues)` - the library rejected the document.
* `build(diagram, geometry=GEOMETRY_FULL)` - create the document of an
  analysed diagram; with `GEOMETRY_FULL` lay it out. Return the document.
  Raises `BuildError` with B01 issues.
* `layout(document, geometry)` - lay a document out (`full`), complete its
  drawing (`update`; the full layout when nothing is drawn) or clean it
  (`none`), and declare the geometry in the meta.
* `encode(document)` - the GraphML text of the document.
* `verify(graphml)` - read the text back with the strict check of the
  library. Raises `BuildError` with a B02 issue carrying the message of
  the library.

## Module reader

A document to the notation tree.

* `ReadError(message)` - the diagram cannot be read or shown in the
  notation.
* `decode(graphml)` - a `CyberiadaML.Document` of the text. Raises
  `ReadError`.
* `read(document)` - the `Diagram` of a document: the vertices and the
  transitions with their `element_id` (an empty entry or exit behaviour
  is left out), the names `_kindN` (`_final1`) for
  the unnamed final, choice, terminate, history and submachine states, the
  notes for the comments, the component declarations, the other formal
  comments and the meta parameters other than the name and the
  description. Raises `ReadError` for what the notation cannot show.

## Module patcher

The difference of two trees applied to a document.

* `Change(code, element=None, **fields)` - one change: the code of the
  message (`C01` added, `C02` removed, `C03` renamed, `C04` moved, `C05`
  behaviour changed, `C06` transition added, `C07` transition removed,
  `C08` transition action changed), the id of the element in the result.
* `PatchError(issues)` - the new tree names the old one wrongly (`U02` -
  `U04`).
* `patch(graphml, old, new, geometry=GEOMETRY_UPDATE)` - decode the
  original again, apply the difference of the analysed `new` tree against
  the `old` tree read from it, lay it out; return `(document, changes)`.
  Raises `PatchError`, `BuildError`.

## Module client

The model servers.

* `CHAT_COMPLETIONS`, `MESSAGES` - the protocols, `'chat-completions'` and
  `'messages'`.
* `ConfigError` - a missing or bad option, URL, model or key.
* `ClientError` - the server failed or answered something unreadable.
* `RequestLimitError(ClientError)` - the request limit is reached.
* `Usage` - `requests`, `input_tokens`, `output_tokens`; `add(usage)`.
* `Reply` - `text`, `usage` (of this request), `truncated` (the answer was
  cut by the length limit).
* `Client(protocol, url, model, key=None, timeout=300, retries=3,
  max_requests=16, max_tokens=8192)` - a client of one model.
  * `complete(system, messages)` - send the system prompt and the messages
    (`{'role': 'user' | 'assistant', 'content': text}`); return a `Reply`.
    Retries the codes 429 and 5xx and the network failures. Raises
    `ClientError`, `RequestLimitError`.
  * `usage` - the `Usage` of all the requests of the client.
* `is_local(url)` - whether the server is on the local host.
* `conventional_key_env(url)` - the conventional key variable of the
  server: `api.deepseek.com` - `DEEPSEEK_API_KEY`; `None` for an address.
* `resolve_key(url, key_env=None, environ=os.environ)` - the key: the
  variable `key_env`, else `HSM_MAKER_API_KEY`, else the conventional
  variable; `None` for a local server. Raises `ConfigError` when a key is
  needed and not found.
* `from_environment(protocol=None, url=None, model=None, key=None,
  key_env=None, environ=os.environ, **options)` - a `Client` from the
  arguments, else `HSM_MAKER_PROTOCOL`, `HSM_MAKER_URL`, `HSM_MAKER_MODEL`,
  `HSM_MAKER_KEY_ENV`. Raises `ConfigError`.

## Module language

The texts of the languages, `hsm_maker/prompts/<language>/`.

* `AUTO`, `DEFAULT` - `'auto'` and `'en'`.
* `languages()` - the available languages.
* `detect(text)` - `'ru'` when the text has more Cyrillic than Latin
  letters, else `'en'`.
* `choose(language, prompt)` - the language of a run: `detect(prompt)` for
  `AUTO`. Raises `ConfigError` for an unknown language.
* `Texts(language)` - the texts of a language:
  * `system` - the system prompt;
  * `text(key, **fields)` - a message by its key;
  * `message(issue)` - the message of an issue without its line;
  * `render(issue)` - `line N: message`, `warning: ...` for a warning;
  * `change(change)` - the message of a `Change`.

## Module maker

The conversion and the repair loop.

* `ROUNDS` - 3.
* `ACCEPTED`, `ROUNDS_SPENT`, `REQUEST_LIMIT` - the reasons of a `Result`.
* `Conversion` - one notation converted: `notation`, `diagram`,
  `document`, `graphml`, `errors`, `warnings`, `changes`, `ok`.
* `Result` - `ok`, `graphml`, `document`, `notation` (of the last round),
  `errors`, `warnings`, `changes`, `rounds`, `usage`, `language`, `reason`
  (`'accepted'`, `'rounds'`, `'request-limit'`).
* `convert(notation, geometry=GEOMETRY_FULL)` - parse, analyse, build,
  encode and verify one notation; return a `Conversion`. Never raises for
  a mistake of the text.
* `change(graphml, notation, geometry=GEOMETRY_UPDATE, old=None)` - apply
  one changed notation to the diagram of the GraphML text: analyse with the
  issues of the original as warnings, patch, encode and verify; return a
  `Conversion` with the changes. `old` is the tree read from the original
  (read again when absent).
* `feedback(conversion, texts, truncated=False)` - the message to the
  model about a rejected conversion.
* `run(prompt, client, language=AUTO, geometry=GEOMETRY_FULL,
  rounds=ROUNDS, log=None)` - the loop of `ARCHITECTURE.md`; return a
  `Result`. `log(number, reply, conversion)` is called after every round.
  Raises `ClientError` other than the request limit. A client is any
  object with `complete(system, messages)` and `usage`.
* `run_update(graphml, prompt, client, language=AUTO,
  geometry=GEOMETRY_UPDATE, rounds=ROUNDS, log=None)` - the loop of the
  update: the diagram rendered into the first message, every answer
  applied with `change`. Raises `ReadError` before the first request.

## Command hsm-maker

    hsm-maker [PROMPT] [-f FILE] [--notation FILE] [--update FILE]
              [--render FILE] [-o FILE] [--diagnostics FILE]
              [--geometry full|update|none] [--language auto|en|ru]
              [--save-notation FILE] [--rounds N] [--max-requests N]
              [--timeout SECONDS] [--protocol chat-completions|messages]
              [--url URL] [--model NAME] [--key-env NAME] [-v] [--version]

* `python -m hsm_maker` runs the same command.
* The prompt is `PROMPT`, the file `-f` (`-` is the standard input) or the
  standard input.
* `--notation FILE` converts a notation file without a model: a new
  diagram, or a change of the `--update` diagram.
* `--update FILE` changes the diagram of the file; the prompt describes the
  change; the geometry is `update` by default. An empty file is a new
  diagram.
* `--render FILE` prints the notation of the diagram and exits.
* `--diagnostics FILE` writes a JSON list for the editor: `{severity,
  message, rule, element}` - the issues of the last round (`rule` = the
  code) and, for a change, one `info` entry per change (`element` = the id
  in the result).
* The document goes to `-o FILE` or to the standard output; a file is
  written only for a made diagram. `--save-notation` writes the last
  notation in any case.
* The issues and the usage (`rounds: N, requests: N, input tokens: N,
  output tokens: N`) go to the standard error; `-v` adds every round.

Exit codes:

* `0` - the diagram is made;
* `1` - not made: issues remain after the last round, or the request limit
  is reached, or the notation file has errors;
* `2` - a usage or configuration error;
* `3` - the model server failed.

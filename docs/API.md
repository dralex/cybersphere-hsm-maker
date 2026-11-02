# The Cybersphere HSM Maker Interface Specification

Document version: 0.9 (2026-10-31)

The package `hsm_maker` and the command `hsm-maker`. The reasons are in
`ARCHITECTURE.md`, the notation and its issue codes in `NOTATION.md`.

## Package hsm_maker

* `__version__` - the version of the package.
* `make(prompt, client=None, *, protocol=None, url=None, model=None,
  key=None, key_env=None, language='auto', code_language='auto',
  geometry='full', rounds=3, max_requests=None, timeout=None, log=None,
  pictures=(), trace=None, size='fit', routing='orthogonal', check=True)` -
  make a diagram from the description `prompt`; return a `Result`;
  `code_language`, `log`, `pictures`, `trace`, `geometry` (`'picture'`
  too), `size`, `routing` and `check` as in `maker.run`.
  Without `client` a `Client` is created from the arguments and the
  environment (`client.from_environment`). Raises `ConfigError` for a bad
  configuration and `ClientError` when the server fails.

* `update(graphml, prompt, client=None, *, ...)` - change the diagram of the
  GraphML text by the description of the change `prompt`; the keywords of
  `make`, with `geometry='update'`. Returns a `Result` with the changes.
  Raises `ReadError` when the diagram cannot be read or shown in the
  notation.

The names `Result`, `Conversion`, `Change`, `Issue`, `Client`, `Usage`,
`Image`, `ConfigError`, `ClientError`, `ReadError`, `convert`, `change`,
`run`, `run_update` and `load_picture` are exported by the package too.

## Module notation

The notation tree, its parser and its checks. It does not use the `CyberiadaML` module.

* `MACHINE`, `STATE`, `INITIAL`, `FINAL`, `TERMINATE`, `CHOICE`, `HISTORY`,
  `DEEP_HISTORY`, `ENTRY_POINT`, `EXIT_POINT`, `SUBMACHINE` - the kinds of
  the vertices.
* `ERROR`, `WARNING` - the severities of the issues.
* `Issue(code, line=None, severity=ERROR, **fields)` - an issue: the code of
  `NOTATION.md`, the line (counted from 1, `None` for the whole text) and
  the fields of the message.
* `NotationError(issues)` - the syntax errors of a text; `issues` lists
  them all.
* `CODE_LANGUAGES` - the code languages of the editor: `'C'`, `'C++'`,
  `'C#'`, `'Java'`, `'JavaScript'`, `'Python'`.
* `language_spelling(name)` - the spelling of `CODE_LANGUAGES` of a name
  equal to one of them but for the case; else the name.
* `Diagram` - the tree: `name`, `description`, `language` (the code
  language, meta `platformLanguage`), `machines` (the vertices of
  the kind `MACHINE`), `notes` (`(vertex or None, text)`, written as `#
  note:` lines), `walk()` (every vertex in the notation order),
  `comments()` (every comment in the notation order).
* `Vertex` - a machine, a state, a submachine, a pseudostate or a point:
  `kind`, `name`, `line`, `parent`, `children`, `behaviours`, `internals`
  (the internal transitions), `transitions` (the outgoing transitions),
  `reference` (the machine name of a submachine), `was` (the `(was OLD)`
  text), `element_id` (set by the reader), `comments` (the comments
  written in it), `machine`, `path` (the qualified name in the machine,
  `Moving::MovingUp`), `walk()`.
* `Comment` - an informal comment: `name` (its title or its `_commentN`
  name, `None` when a new one has none), `title` (the title in the
  document, set by the reader), `body` (the Markdown text), `subjects`,
  `parent` (the machine or the state it is written in), `line`, `was`,
  `element_id`, `unnamed` (set by the reader).
* `Subject` - a link of a comment: `kind` (`'element'`, `'name'`,
  `'body'`), `fragment`, `ref` (a vertex or comment reference) or
  `source_ref`, `event`, `guard`, `propagation`, `target_ref` (a
  transition), `target` (the `Vertex`, `Comment` or `Transition`, set by
  `analyze`), `element_id` (set by the reader).
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
* `BINDING_ERRORS` - the tuple of the exception classes of the `CyberiadaML` module.
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
  informal comments with their links (`_commentN` for an unnamed comment
  or a title the notation cannot write; the links to an initial, its
  transition or a formal comment left out), the notes for the component
  declarations, the other formal comments and the meta parameters other
  than the name and the description. Raises `ReadError` for what the
  notation cannot show.

## Module patcher

The difference of two trees applied to a document.

* `Change(code, element=None, **fields)` - one change: the code of the
  message (`C01` added, `C02` removed, `C03` renamed, `C04` moved, `C05`
  behaviour changed, `C06` transition added, `C07` transition removed,
  `C08` transition label changed: the same ends, another event, guard,
  flag or action, edited in place, `C09` comment added, `C10` comment
  removed, `C11` comment text or title changed, `C12` comment links
  changed), the id of the element in the result.
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
* `ConfigError(message, hint=None)` - a missing or bad option, URL, model
  or key; `hint` - the key of a hint text of `messages.json` (`'hint_key'`
  for a missing key), else `None`.
* `HTTP`, `NETWORK`, `TIMED_OUT`, `ANSWER` - the kinds of a `ClientError`:
  an HTTP error, an unreachable server, no answer in time, an unreadable
  answer.
* `ClientError(message, status=None, kind=HTTP)` - the server failed or
  answered something unreadable; `status` - the HTTP code, else `None`.
* `RequestLimitError(ClientError)` - the request limit is reached.
* `Usage` - `requests`, `input_tokens`, `output_tokens`; `add(usage)`.
* `Reply` - `text`, `usage` (of this request), `truncated` (the answer was
  cut by the length limit).
* `Client(protocol, url, model, key=None, timeout=300, retries=3,
  max_requests=16, max_tokens=8192)` - a client of one model.
  * `complete(system, messages)` - send the system prompt and the messages
    (`{'role': 'user' | 'assistant', 'content': text}`, a user message may
    add `'images': [Image]`: sent as the parts of the protocol, the images
    first); return a `Reply`. Retries the codes 429 and 5xx and the network
    failures. Raises `ClientError`, `RequestLimitError`.
  * `usage` - the `Usage` of all the requests of the client.
* `IMAGE_TYPES` - the media types of the pictures: `'image/png'`,
  `'image/jpeg'`, `'image/gif'`, `'image/webp'`.
* `MAX_IMAGE` - the largest picture, 20 MiB.
* `Image(data, media_type, name=None)` - a raster picture: the bytes, the
  media type, the file name; `base64()` - the data in base64, `data_url()`
  - `data:<media type>;base64,<data>`.
* `image_size(data)` - `(width, height)` of a PNG, GIF, JPEG or WebP picture
  from its header; `None` when it cannot be read.
* `image_type(data)` - the media type of the bytes by their first bytes;
  `None` for another format.
* `load_picture(path)` - the `Image` of a file. Raises `ConfigError` for an
  SVG, another format or a file above `MAX_IMAGE`, `OSError` when the file
  cannot be read.
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

## Module placement

The placement round (`ARCHITECTURE.md`, The placement).

* `GEOMETRY_PICTURE` - `'picture'`: a new diagram arranged as its picture.
* `transitions(document, texts, listed)` - the `TransitionItem`s (`number`
  `'tN'`, `element_id`, `source_id`, `target_id`, `text`) of the transitions
  between two listed elements, loops aside; `request(texts, listed, width,
  height, edges=())` lists them after the elements;
  `parse_sides(answer, edges)` - `{element id: (from, to)}`, a side
  `'left'`, `'right'`, `'top'`, `'bottom'` or `None`; `apply(diagram,
  graphml, boxes, listed, size, routing='orthogonal', sides=None, edges=())`
  draws the ends of the transitions on their sides.
* `SIZE_FIT`, `SIZE_PICTURE`, `SIZES` - `'fit'`, `'picture'`: the sizes of the
  seed - under the texts, or the picture's proportions as minimums.
* `PlacementError(reason)` - the placement round gives no seed.
* `Item` - an element of the request: `number`, `element_id`, `mark` (a
  pseudostate or a point, placed by its centre), `rect` (placed by a rect),
  `text` (its line of the request).
* `Placement` - the outcome: `placed`, `total`, `error` (the reason of a
  failure, else `None`).
* `items(document, texts)` - the numbered elements of a document: the
  machines (their frames), the vertices in the notation order, the comments.
* `request(texts, items, width, height)` - the text of the request.
* `parse(answer, items, width, height)` - the boxes `{number: (left, top,
  right, bottom)}` of an answer (its first fenced block, else the whole
  text), clamped to the picture; unknown numbers and bad boxes dropped.
  Raises `PlacementError` when no box is left.
* `scale(boxes, items, needs, size)` - the factor of the boxes: `fit`, every
  box under its need (`{element_id: (width, height)}` of the full layout);
  `picture`, three quarters of the states fit their texts.
* `apply(diagram, graphml, boxes, items, size)` - the analysed diagram
  built without geometry, the scaled boxes as absolute (LegacyYED) rects
  and points, `Document.arrange_geometry`, Qt, encoded and verified;
  `graphml` is the full layout of the accepted round. Returns `(document,
  text)`. Raises `BuildError` and the errors of the `CyberiadaML` module.

## Module report

The messages of a run (`ARCHITECTURE.md`, The messages).

* `QUOTE_LIMIT` - the longest quoted line of an answer, in characters.
* `quoted(texts, issue, notation)` - `line N "the line": message`, the line
  of the notation cut at `QUOTE_LIMIT`; `texts.render(issue)` when the
  issue has no line or the line is not there.
* `hint(texts, error)` - the hint text of a `ConfigError`, `ClientError` or
  `ReadError`, `None` when there is none.
* `Report(texts, stream, verbosity=0, model=None, rounds=ROUNDS,
  errors=sys.stderr)` - the messages of one run: `stream` takes the
  progress and the dialog, `errors` the failure and its hint; `verbosity` 1
  adds the dialog, 2 the system prompt.
  * `trace(number, system, messages)`, `log(number, reply, conversion)` -
    the callbacks of `maker.run`.
  * `summary(result)` - the warnings, the usage, and for a diagram not made
    the issues quoted, the reason and its hint.
  * `explain(error)` - the message of an error and its hint.

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

## Module plugin

The installation of the editor plugin (`editor-plugin/`).

* `PLUGIN_ID` - `'hsm-maker'`.
* `source()` - the plugin directory of this installation: `editor-plugin/`
  beside the package in a source tree, else
  `share/cyberiada-pro/plugins/hsm-maker` under `sys.prefix` or under
  the user base of `site`; `None` when none has `plugin.json`.
* `user_folder(environ=None, system=None)` - the user plugin folder of
  `CyberiadaPro`: `<data>/Cyberiada/CyberiadaPro/plugins`, `<data>` being `XDG_DATA_HOME` (`~/.local/share`) on
  Linux, `APPDATA` on Windows, `~/Library/Application Support` on macOS;
  `system` is a `platform.system()` name.
* `pinned(descriptor, executable)` - the descriptor (a dict) without
  `interpreter`, every `argv` starting with `executable`; a descriptor
  without an interpreter is returned as it is.
* `install(target=None, executable=None)` - copy the plugin into
  `target/hsm-maker` (`target` defaults to `user_folder()`), replacing an
  earlier copy; its `plugin.json` loses `interpreter` and every command
  starts with `executable` (`sys.executable`); a copy from a source tree
  also sets `PYTHONPATH` to the tree in its `env`. Returns the installed
  directory. Raises `PluginError` when there is no plugin, when
  `target/hsm-maker` exists and is not this plugin, or when the copy
  fails.

## Module maker

The conversion and the repair loop.

* `ROUNDS` - 3.
* `ACCEPTED`, `ROUNDS_SPENT`, `REQUEST_LIMIT`, `NO_PICTURE` - the reasons
  of a `Result`.
* `NO_PICTURE_ANSWER` - `'NO PICTURE'`, the answer of a model that does not
  see the picture.
* `Conversion` - one notation converted: `notation`, `diagram`,
  `document`, `graphml`, `errors`, `warnings`, `changes`, `ok`.
* `Result` - `ok`, `graphml`, `document`, `notation` (of the last round),
  `errors`, `warnings`, `changes`, `rounds`, `usage`, `language`, `reason`
  (`'accepted'`, `'rounds'`, `'request-limit'`, `'no-picture'`), `truncated`
  (the last answer was cut by the length limit), `answer` (the text of the
  last answer), `placement` (the `Placement` of the placement round, else
  `None`).
* `convert(notation, geometry=GEOMETRY_FULL, code_language=AUTO)` - parse,
  analyse, build, encode and verify one notation; return a `Conversion`.
  A `code_language` other than `AUTO` replaces the `language:` of the
  notation. Never raises for a mistake of the text.
* `change(graphml, notation, geometry=GEOMETRY_UPDATE, old=None,
  code_language=AUTO)` - apply one changed notation to the diagram of the
  GraphML text: analyse with the issues of the original as warnings, patch,
  encode and verify; return a `Conversion` with the changes. `old` is the
  tree read from the original (read again when absent); `code_language` as
  in `convert`.
* `feedback(conversion, texts, truncated=False)` - the message to the
  model about a rejected conversion.
* `run(prompt, client, language=AUTO, geometry=GEOMETRY_FULL,
  rounds=ROUNDS, log=None, code_language=AUTO, pictures=(), trace=None,
  size=SIZE_FIT, routing=ROUTING_ORTHOGONAL, check=True)` -
  the loop of `ARCHITECTURE.md`; return a `Result`. `trace(number, system,
  messages)` is called before every request with what is sent (a user
  message may have `images`), `log(number, reply, conversion)` after every
  answer; `conversion` is `None` for a `NO PICTURE` answer. A `code_language` other than `AUTO` is asked of
  the model and written (`ARCHITECTURE.md`, The code language).
  `geometry='picture'` with pictures: the rounds lay the diagram out in
  full, then the placement round arranges it as the first picture
  (`size`: `'fit'` or `'picture'`); its `trace` and `log` have the number
  `None` and the `log` gets the `Placement`; a failed placement keeps the
  full layout. Without a picture `'picture'` is `'full'`. With pictures and
  `check` the check round asks once more whether the accepted diagram
  matches them: `result.check` is a `Check` - `outcome` `CHECK_SAME`
  (`'same'`, the answer `NO CHANGES`), `CHECK_CHANGED` (an accepted
  correction replaced the diagram) or `CHECK_REJECTED` (`issues` its
  errors), or `None` with `error` (a client error, the request limit); its
  `trace` and `log` have the number `CHECK` (`'check'`). `routing`:
  `ROUTING_ORTHOGONAL` (`'orthogonal'`, the runs along and across the
  flow) or `ROUTING_POLYLINE` (`'polyline'`) for every layout of the run;
  `convert`, `change`, `run_update`, `make`, `update`,
  `builder.build`, `patcher.patch` and `placement.apply` take it too.
  `pictures` - `Image` objects or file paths: the prompt becomes their
  comment and may be empty; they go with the first message of every round;
  the answer `NO PICTURE` ends the run with the reason `'no-picture'`.
  Raises `ConfigError` for a picture `load_picture` refuses.
  Raises `ClientError` other than the request limit. A client is any
  object with `complete(system, messages)` and `usage`.
* `run_update(graphml, prompt, client, language=AUTO,
  geometry=GEOMETRY_UPDATE, rounds=ROUNDS, log=None, code_language=AUTO,
  pictures=(), trace=None, routing=ROUTING_ORTHOGONAL)` - the loop of the
  update: the diagram rendered into the
  first message, every answer applied with `change`; `code_language` and
  `pictures` as in `run` (a picture shows the change). Raises
  `ReadError` before the first request.

## Command hsm-maker

    hsm-maker [PROMPT] [-f FILE] [--notation FILE] [--update FILE]
              [--render FILE] [--picture FILE]... [-o FILE]
              [--diagnostics FILE]
              [--geometry full|update|none|picture]
              [--picture-size fit|picture] [--routing orthogonal|polyline]
              [--check-picture [on|off]] [--no-check-picture]
              [--language auto|en|ru]
              [--code-language auto|NAME]
              [--save-notation FILE] [--rounds N] [--max-requests N]
              [--timeout SECONDS] [--protocol chat-completions|messages]
              [--url URL] [--model NAME] [--key-env NAME] [-v[v]] [--version]
    hsm-maker --install-editor-plugin [DIR]

* `python -m hsm_maker` runs the same command.
* The prompt is `PROMPT`, the file `-f` (`-` is the standard input) or the
  standard input.
* `--notation FILE` converts a notation file without a model: a new
  diagram, or a change of the `--update` diagram.
* `--update FILE` changes the diagram of the file; the prompt describes the
  change; the geometry is `update` by default. An empty file is a new
  diagram.
* `--render FILE` prints the notation of the diagram and exits.
* `--geometry picture` (the default with `--picture` and without `--update`)
  arranges the new diagram as its first picture by the placement round;
  `--picture-size fit|picture` (`fit`) the sizes of its seed. Refused with
  `--update` and `--notation`.
* `--check-picture [on|off]` (`on`), `--no-check-picture` - the check round
  of a new diagram made from a picture.
* `--routing orthogonal|polyline` (`orthogonal`) - the routes of the
  transitions of every layout: runs along and across the flow, or straight
  segments.
* `--picture FILE` - a raster picture of the system (PNG, JPEG, GIF, WebP),
  repeatable; the prompt is its comment and may be empty. Refused with
  `--notation` and `--render`. A model that does not see it ends the run
  (exit 1).
* `--code-language auto|NAME` (`HSM_MAKER_CODE_LANGUAGE`, `auto`) - the
  programming language of the actions: `auto` takes the model's `language:`
  header, a name is asked of the model and written; with `--notation` the
  name replaces the header.
* `--install-editor-plugin [DIR]` installs the editor plugin into `DIR` or
  the editor's user plugin folder, bound to the running Python
  (`plugin.install`), prints where and exits.
* `--diagnostics FILE` writes a JSON list for the editor: `{severity,
  message, rule, element}` - the issues of the last round (`rule` = the
  code) and, for a change, one `info` entry per change (`element` = the id
  in the result).
* The document goes to `-o FILE` or to the standard output; a file is
  written only for a made diagram. `--save-notation` writes the last
  notation in any case.
* The messages - the progress of every round, the warnings and the usage
  (`rounds: N, requests: N, input tokens: N, output tokens: N`) - go to the
  standard output when the document goes to `-o FILE`, else to the standard
  error. `-v` adds the dialog: every message sent, every answer, the
  issues of every round; `-vv` adds the system prompt.
* A failure goes to the standard error: the issues of the last answer with
  their lines quoted, or the error, and a hint what to do as the last line.

Exit codes:

* `0` - the diagram is made;
* `1` - not made: issues remain after the last round, or the request limit
  is reached, or the model does not see the picture, or the notation file
  has errors;
* `2` - a usage or configuration error;
* `3` - the model server failed.

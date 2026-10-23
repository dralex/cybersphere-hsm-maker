# The Cybersphere HSM Maker Architecture

Document version: 0.6 (2026-10-23)

The maker turns a description of a system written in a natural language
into a Hierarchical State Machine (HSM) diagram stored in the
CyberiadaML-GraphML format (CGML, PNST 1044-2025) with the semantics of
PNST 984-2024. A language model writes the structure of the diagram in a
compact text notation; the maker parses and checks it, returns the
mistakes to the model until the diagram is correct, builds the document
with the `CyberiadaML` module and lays it out.
It changes an existing diagram the same way: the model sees the diagram in
the notation and answers the changed one, the maker applies the difference
to the same document and lays out only what is new.

The maker is a library first and a command second. It depends on the
`CyberiadaML` module and on the Python 3 standard library only: no agent
framework, no vendor SDK, no editor. The module is the binding of
`libcyberiadamlpp-py` when it is installed, else the pure-Python interface
of `cyberiadaml-py` (`cyberiadaml_py.cml`, the same names and results,
`libhtreegeom` ported): `hsm_maker/cyberiadaml.py` chooses it.

```
     cli.py              maker.py              notation.py
 +-------------+      +-------------+  text  +-------------+
 |             | ---> |             | -----> |   parse,    |
 |  hsm-maker, |      |   draft,    | <----- |   analyze   |
 |   make()    | <--- |   check,    | issues +-------------+
 +-------------+      |   repair    |          builder.py
                      |    loop     |  tree  +-------------+
                      |             | -----> |   build,    |
                      |             | <----- |   layout,   |
                      |             | GraphML|   verify    |
                      +-------------+        +-------------+
                        |         ^                 |
                system, |         | reply,          | calls
               messages v         | usage           v
                      +-------------+       CyberiadaML module
                      |  client.py  |
                      +-------------+
                        |         ^
                   HTTP v         | HTTP
                         model server
```

## Usage requirements

| No | Requirement | Section |
|---|---|---|
| R1 | Make a new diagram from a description in a natural language. | The process |
| R2 | The result is a valid CGML document: it passes the strict check of the library. | The process |
| R3 | Work with any model server of the `chat-completions` or the `messages` protocol, local servers included, without a vendor SDK. | The client |
| R4 | The model never writes identifiers or coordinates. | The notation, The geometry |
| R5 | The instructions to the model exist in several languages, English and Russian at least. | The languages |
| R6 | Be embedded by other programs (`cybersphere-agents`, the editors) and run as a command. | The interface |
| R7 | Python 3.8+, the standard library and the `CyberiadaML` module only. | Code layout |
| R8 | Limit the requests and report the usage: requests, tokens. | The client |
| R9 | Change an existing diagram by a description of the change; what is not changed keeps its identity, its place and the parts the notation does not show. | The update |
| R10 | Run from `CyberiadaPro`: draw a new diagram, change the open one. | The editor plugin |
| R11 | Declare the programming language of the actions: the model's choice or the user's. | The code language |

## The notation

The model answers with the whole diagram in one block of the notation
specified in `NOTATION.md`. A state is a line, the nesting is the
indentation, the behaviour is the action text of PNST 1044, 6.8, and a
transition names its target:

```
machine Lift
  initial -> Idle / floor = 1
  state Idle
    entry/ lamp_off()
    CALL [call_floor > floor] -> MovingUp / target = call_floor
  state Moving
    state MovingUp
      entry/ motor_up()
    FLOOR [floor == target] -> Idle
```

Comments are a part of the diagram: a `comment` line with its title, its
Markdown text below it and the links to what it explains (`on Idle`, `on
DoorsOpen TIMEOUT -> Idle`, a quoted fragment of an action). The model is
asked to comment what the diagram does not say by itself - the purpose of
a state, an assumption, a design decision, an open question - and to keep
the comments true when it changes a diagram.

The choice follows the experience of the LLM tester of
`CyberiadaHSM-Editor`, which drew diagrams with editor scripts and later
with tool calls:

| Observation | Consequence |
|---|---|
| the answers of the model were well-formed; 62% of the rejected scripts named a wrong identifier | names instead of identifiers; the library assigns the identifiers |
| a script per answer cost about 1.6k tokens per command, a tool call per command about 22k | the whole diagram in one answer |
| the model cannot measure the text of a state | no coordinates; the library lays the diagram out |

## The process

```
 +---------+         +---------+         +---------+         +---------+
 |  model  | answer> | extract | -text-> |  parse  | -tree-> | analyze |
 +---------+         +---------+         +---------+         +---------+
      ^                                                           |
      | feedback                                                  | tree
      |                                                           v
 +---------+         +---------+         +---------+         +---------+
 | render  | <issues | verify  | <GraphML| encode  | <-doc-- |  build  |
 +---------+         +---------+         +---------+         +---------+
                          |
                          v no issue: the result
```

A round:

1. the client sends the system prompt and the conversation, the model
   answers;
2. `extract` takes the first fenced block of the answer, or the whole
   answer when there is none;
3. `parse` reads the notation, `analyze` resolves the target names and
   checks the semantics, `build` creates the document through the binding
   and lays it out, `encode` writes it and `verify` reads it back with the
   strict check of the library;
4. any issue ends the round: the issues are rendered as `line N: message`,
   with the known names where a name is wrong, and sent back with the
   request to answer with the whole corrected diagram.

The diagram is accepted when every step passes: a fact, never the opinion
of the model. The conversation of a round is the prompt, the last answer
and the feedback to it - the earlier answers are dropped, so a round costs
about the same as the first one. The process stops when the diagram is
accepted, after the last round (`--rounds`, 3 by default) or when the
request limit of the client is reached.

The checks of the maker come first because the library accepts some
mistakes silently (duplicate names on one level, a machine without an
initial, a second `entry/` merged into the first) and rejects others
without a reason the model could use (a bad event name, a bracket in a
guard).

## The geometry

The model writes no coordinates. The geometry is chosen when the document
is saved:

| `--geometry` | Document |
|---|---|
| `full` (default) | `reconstruct_geometry` - the layered layout of `libhtreegeom` 1.1 (containment, flow from the initial to the finals, few crossings, routed transitions, label places from the text sizes); the meta parameter `geometry/ full` |
| `none` | no layout; the meta parameter `geometry/ none` - for the programs that read the structure only (`hsm-dispatcher-py`, the code generators) |
| `update` (default of `--update`) | `update_geometry` - the drawn elements keep their places, the new ones are laid out around them (`libhtreegeom` 1.2); a diagram without geometry gets the full layout |

The order of the lines in the notation is the initial order of the
vertices inside each layer of the layout, so a diagram written in the
order of its flow is drawn in that order. A document without geometry
opens in `CyberiadaPro` only with the reconstruction on loading.

## The update

`hsm-maker --update in.graphml` changes a diagram. The answer of the model
is the whole changed diagram; the maker applies the difference to the
document itself, so an element that stays keeps its identifier, its
geometry and what the notation does not show: the formal comments
(component declarations, prompts), colours, meta parameters.

```
 in.graphml --decode--> Document --read--> old tree (+ element ids)
                                              |
                          render: the notation with the comments,
                          "# note:" lines for the hidden parts, `_n`
                          names for unnamed elements
                                              v
                  system prompt + the diagram + the change request
                                              |
                                            model
                                              v
             the changed notation --parse, analyze--> new tree
                                              |
                 diff by identity, patch a fresh decode of in.graphml:
                  1 remove the transitions that went, then the vertices
                    (their transitions and comment links first)
                  2 add the new vertices without geometry, parents first
                  3 move (copy + remove + add, the geometry cleaned;
                    kept in a wrap), rename
                  4 add the new transitions; update the changed actions
                  5 comments: remove, add, edit the text and the title,
                    then the links of every comment
                                              |
                 update_geometry: the drawing kept, the new parts laid out
                                              v
                        encode --> strict verify --> out.graphml
```

* **Identity.** A machine by its name; a vertex by its path in the old
  diagram - the `(was OLD)` of its line, else the old path of its parent
  and its name; the initial by its container; a `_n` name by the unnamed
  element it was given to. A vertex left unmatched is then matched by its
  name when exactly one unclaimed old vertex of its kind has it: a move
  the model did not declare. A transition by its source, event, guard,
  propagation and target: the same key with another action is an action
  change; a transition with the same ends and another event, guard or flag
  is edited in place (it keeps its route); anything else is a removal and
  an addition. A vertex of another
  kind under the same name is removed and added. A comment by its machine
  and its name - the `(was OLD)` of its line, the `_commentN` of an
  unnamed one - else by its unchanged text; it stays in its container.
  Its links are compared by the linked element, the kind (whole, name,
  body) and the fragment: a kept link keeps its geometry; the links the
  notation cannot show are kept.
* **Wraps.** Vertices moved from one parent into a new container keep
  their geometry: the container is laid out around the drawing, which
  keeps its routes (`libhtreegeom` moves a drawn transition with its ends
  when they moved alike). Any other move is laid out anew.
* **Sizes.** A drawn simple state whose text grew (actions, a longer
  name) grows from its corner by the difference of the text estimates of
  `libcyberiadaml` (20 px a line, 10 px a character); an unchanged text
  changes nothing. The layout keeps the ends of its routes on the new
  border. A drawn comment whose text grew grows the same way; a new
  comment is placed beside its first subject, an unlinked one beside the
  machine.
* **Texts.** An action or a guard that differs from the original only as
  the notation normalises it (indentation, `#` lines, spacing) keeps the
  original text.
* **Issues.** A semantic issue the original diagram already has (same code
  and fields) is reported as a warning; the model is not asked to fix it.
* **Refusals.** A diagram the library cannot read (several regions,
  `do/`), or one the notation cannot show (an internal transition without
  an event, a name with a quote), is refused before the model is asked.
* **Rounds.** Every round patches a fresh decode of the original, so a
  rejected answer leaves nothing behind.
* **Changes.** The patch lists what it did - added, removed, renamed,
  moved, actions changed, comments added, removed, edited and relinked -
  with the element identifiers; `--diagnostics` writes them for the
  editor.
* **Handles.** The binding rebuilds its element tree on decode and on the
  geometry calls: the patch fetches every element by its identifier when
  it uses it.

## The languages

```
   hsm_maker/prompts/
     en/  system.md      the instructions: the model, the notation, the rules, an example
          messages.json  the feedback and the issue texts by code
     ru/  system.md
          messages.json
```

A language is a directory: adding one needs no code. The language of a
run (`--language`, `HSM_MAKER_LANGUAGE`) is `auto` by default: Russian when
the prompt has more Cyrillic than Latin letters, English when it has more
Latin ones, and with no majority the editor's interface language
(`CYBERIADA_PRO_LANGUAGE`, given to a plugin run), else English. The same
language serves the system prompt, the feedback to the model and the
issues the command prints. The Russian texts use the terms of PNST 984,
clause 3. The keywords of the notation are English in every language;
names, events, guards and actions may be written in any script.

## The code language

The programming language of the actions is the `platformLanguage` of the
document: the editor highlights the actions by it, the code generators
read it. The model declares it in the `language:` header of the notation;
`--code-language` (`HSM_MAKER_CODE_LANGUAGE`) decides who chooses:

| `--code-language` | A new diagram | A changed diagram |
|---|---|---|
| `auto` (default) | the model's header; without it no language | the model's header; without it the diagram's language is kept |
| a name | the model is told to write the actions in it; the name is written whatever the answer declares | the same |

A changed diagram shows its language to the model as the header, so the
model keeps it unless the change asks for another. The editor's names (C,
C++, C#, Java, JavaScript, Python) are written in their spelling whatever
their case; the plugin offers them as the choices of its setting.

## The client

`client.py` speaks two protocols over `urllib`:

| Protocol | Request |
|---|---|
| `chat-completions` | `POST {url}/chat/completions`, a bearer key, the system prompt as the first message |
| `messages` | `POST {url}/messages`, a key header and the protocol version header, the system prompt as a field |

A request is retried on the codes 429 and 5xx and on network failures with
a growing pause; the other errors stop the run. Every request counts
against the request limit (`--max-requests`). The usage - requests, input
and output tokens - is summed and reported. The key never appears in a
message.

## The configuration

| Option | Environment | Default |
|---|---|---|
| `--protocol` | `HSM_MAKER_PROTOCOL` | `chat-completions` |
| `--url` | `HSM_MAKER_URL` | - |
| `--model` | `HSM_MAKER_MODEL` | - |
| `--key-env` | `HSM_MAKER_KEY_ENV` | - |
| `--language` | `HSM_MAKER_LANGUAGE` | `auto` |
| `--code-language` | `HSM_MAKER_CODE_LANGUAGE` | `auto` |

The key is the value of the variable named by `--key-env`; else of
`HSM_MAKER_API_KEY`; else of the conventional variable of the server, the
second-level name of its host in capitals with `_API_KEY`
(`api.deepseek.com` - `DEEPSEEK_API_KEY`). A server on the local host needs
no key. Nothing is stored.

## The interface

`hsm_maker.make(prompt, ...)` returns a `Result`: whether the diagram was
made, the GraphML text, the last notation, the issues, the rounds, the
usage; `hsm_maker.update(graphml, prompt, ...)` changes a diagram and adds
the changes to the `Result`. `hsm-maker` is the command around them:
`--update FILE` changes a diagram, `--render FILE` prints the notation of a
diagram, `--notation FILE` applies a notation file without a model (a new
diagram, or a change with `--update`), `--diagnostics FILE` writes the
issues and the changes for the editor. The details are in `API.md`.

## Code layout

| File | Content |
|---|---|
| `hsm_maker/__init__.py` | `make()`, the version, the public names |
| `hsm_maker/cyberiadaml.py` | the `CyberiadaML` module: the binding, else `cyberiadaml_py.cml` |
| `hsm_maker/notation.py` | the notation tree, `extract`, `parse`, `analyze`; no binding |
| `hsm_maker/builder.py` | the tree to a `CyberiadaML.Document`, the layout, `encode`, `verify` |
| `hsm_maker/client.py` | the protocols, the retries, the usage, the key |
| `hsm_maker/language.py` | the languages, the detection, the texts |
| `hsm_maker/reader.py` | a `CyberiadaML.Document` to the notation tree with the element ids and the notes |
| `hsm_maker/patcher.py` | the difference of two trees applied to a document, the change list |
| `hsm_maker/maker.py` | `convert`, `change` (one notation to a document) and `run` (the loop) |
| `hsm_maker/cli.py` | the command `hsm-maker` |
| `hsm_maker/plugin.py` | the installation of the editor plugin |
| `hsm_maker/prompts/` | the texts of the languages |
| `editor-plugin/` | the plugin of `CyberiadaPro`: `plugin.json`, the icons, its README |
| `pyproject.toml` | the Python package (pip, the wheel) |
| `CMakeLists.txt`, `HsmMakerPackOptions.cmake.in` | the Debian package |

## The editor plugin

`editor-plugin/` is the plugin of `CyberiadaPro` (contract `api` 1
of the editor's `docs/PLUGIN-API.md`): a descriptor that runs `python3 -m
hsm_maker`, no adapter. Its README is for the users of the editor.

```
 Plugins                                    the toolbar, right of the main one
 +-----------------------------+            +------------------+
 | HSM Maker                 > |            | HSM Maker [*][~] |   [*] draw, [~] change
 +-----------------------------+            +------------------+
   | Draw a new diagram...     |
   | Change the diagram...     |
   | Show the notation         |
   |---------------------------|
   | Settings...               |
   +---------------------------+

 +--------------------------------------------------+
 | HSM Maker - Change the diagram               [x] |
 +--------------------------------------------------+
 | What to change                                   |
 | +----------------------------------------------+ |
 | | Add a maintenance mode entered by SERVICE    | |
 | | from Idle; rename Idle to Waiting.           | |
 | +----------------------------------------------+ |
 | Layout     [update                           v]  |
 |                                 [Cancel]  [Run]  |
 +--------------------------------------------------+
```

| Action | Result | The command after `python3` |
|---|---|---|
| `draw` - Draw a new diagram... | `new-document` | `-m hsm_maker -f ${param-file:prompt} -o ${output} --diagnostics ${diagnostics}` + the model options |
| `change` - Change the diagram... | `replace` | `-m hsm_maker --update ${input} -f ${param-file:change} --geometry ${param:layout} -o ${output} --diagnostics ${diagnostics}` + the model options |
| `notation` - Show the notation | `log` | `-m hsm_maker --render ${input}` |

The model options come from the persistent parameters (Settings...):
model, server, protocol, language, code language, rounds and the key (`env:NAME` or
`file:PATH`, exported to the run as `HSM_MAKER_API_KEY`, never in the
command line; empty for a local server). The description and the change are asked at every run. The
`change` action keeps the identifiers of what it does not change, so the
selection and the earlier findings still point at them; its diagnostics
list the changes with links to the elements. The maker and the binding
must be importable by the interpreter the editor uses for `python3`.

## Packaging

`editor-plugin/` is the one source of the plugin; both packages bring it
where the editor looks for plugins.

```
 editor-plugin/ --+--> cpack -G DEB ---> /usr/share/cyberiada-pro/plugins/hsm-maker/
 hsm_maker/     --+                      /usr/lib/python3/dist-packages/hsm_maker/
                  |                      /usr/bin/hsm-maker
                  |
                  +--> pip install ----> <prefix>/share/cyberiada-pro/plugins/hsm-maker/
                                         <prefix>/.../site-packages/hsm_maker/
                                         <prefix>/bin/hsm-maker
                                                |
                                                | hsm-maker --install-editor-plugin [DIR]
                                                v
                                 <user folder>/hsm-maker/   (argv[0] = <prefix>'s Python)

 the editor looks in: CYBERIADA_PRO_PLUGIN_PATH, <user folder>,
                      <editor>/../share/cyberiada-pro/plugins/
```

| Package | Contents | Needs |
|---|---|---|
| `python3-cybersphere-hsm-maker` (deb, `all`) | the package in `/usr/lib/python3/dist-packages`, `/usr/bin/hsm-maker`, the plugin in `/usr/share/cyberiada-pro/plugins/hsm-maker/`, the documents | `python3 (>= 3.8)`, `python3-libcyberiadamlpp (>= 1.0.8)` or `python3-cyberiadaml (>= 1.8.0)`; enhances `cyberiada-pro` |
| `cybersphere-hsm-maker` (wheel) | the package, `hsm-maker`, the plugin as data files under the install prefix | `cyberiadaml-py` 1.8+ (a dependency on Python 3.8.1+, on Windows from Python 3.10), or the `CyberiadaML` binding installed apart |

* The deb plugin keeps the logical interpreter `python3`: the system Python
  has the binding and the maker from their packages.
* `hsm-maker --install-editor-plugin [DIR]` (`plugin.install`) copies the
  plugin of the installed package (the data files of the prefix or the user
  base, or `editor-plugin/` of a source tree) into DIR or the editor's user
  folder (`AppDataLocation` of the editor + `plugins`: XDG data home on
  Linux, `%APPDATA%` on Windows, `~/Library/Application Support` on macOS).
  The copy drops `interpreter` and starts every command with the running
  Python, so a virtual environment needs no Preferences setting. It
  replaces an earlier copy; the stored parameter values stay. A user copy
  overrides the system plugin of the same id.

## Testing

The tests use pytest and need no model and no network: a scripted client
plays the model in the loop, a local HTTP stub plays the server for the
client. The notation tests pin every issue code and its line; the builder
tests compare the documents built without geometry with the good files of
`tests/good` and check the documents with geometry by the strict reading
and by the validator of `cyberiadaml-compat-tests` when it is found beside
the repository. A static test keeps the sources inside the Python 3.8
syntax. The tests run on the module the maker finds; `HSM_MAKER_BACKEND=cml`
runs them on `cyberiadaml_py.cml` beside an installed binding. The good
files were written by the binding: the pure-Python writer formats the text
its own way, so they are compared by the canonical dump of `cyberiadaml-py`
there. A run with a real model is a manual step.

The record of 2026-10-14, `deepseek-flash` over `chat-completions`, the
default options:

| Prompt | Language | Rounds | Input / output tokens | Diagram |
|---|---|---|---|---|
| keyboard with Caps Lock | en | 1 | 1109 / 1356 | 2 states |
| defusable time bomb | en | 1 | 1146 / 1905 | 3 states, a choice, a final |
| pedestrian crossing | en | 1 | 1166 / 3810 | a composite of 4 states, offline mode |
| toaster oven | ru | 1 | 1677 / 6022 | a composite of 2 states, door open |
| traffic light with a night mode | ru | 1 | 1650 / 1303 | a composite of 3 states, a path target |

Every document passed the strict check of the library and of `cgmlval`
and opened in `CyberiadaPro`. The checks see the form of a diagram,
not its design: a model may simplify the behaviour of a description.

The update runs of the same day, `--update` with the default options; the
first three diagrams were made by the maker, the microwave oven is a
person-drawn diagram of the corpus:

| Diagram | Change | Rounds | Input / output tokens | Result |
|---|---|---|---|---|
| pedestrian crossing | a maintenance mode from any phase | 1 | 1719 / 3824 | 6 of 6 drawn states kept |
| defusable time bomb | a pause while armed, a beep on every tick | 1 | 1637 / 8327 | `Armed` became a composite and grew from its corner |
| traffic light (ru) | a pedestrian button, a rename | 1 | 2342 / 872 | the rename kept the identifier, all kept |
| microwave oven (ru) | a child lock | 2 | 3598 / 14716 | the states wrapped in a new composite without `(was)`: matched by name, the drawing and its routes kept inside |
| microwave oven (ru) | the same, another answer | 1 | 1638 / 13004 | the lock in both states and a guard: 10 of 10 drawn elements kept, the door state grown by its text |

The editor plugin, run in the editor's batch mode (`--run-plugin`):
`hsm-maker:draw` made a coffee machine of 4 states in 1 round (1438 / 735
tokens) as a new tab; `hsm-maker:change` on it added a cleaning mode and
renamed the waiting state in 1 round (1612 / 1929, again 1612 / 469): 11
of 11 drawn elements kept, the four changes in the diagnostics with their
element identifiers. The real runs found four defects of the update
layout, fixed in `libhtreegeom` and `libcyberiadaml` (a new state on a
drawn route, the routes of a wrapped drawing, the label of a drawn
transition without one, the ends of a route on a grown state).

## Reuse

| Need | Existing tool |
|---|---|
| writing, reading and checking CGML | `libcyberiadamlpp-py` (`CyberiadaML`), or `cyberiadaml-py` (`cyberiadaml_py.cml`) |
| the layout | `libhtreegeom` through the binding, or its port in `cyberiadaml-py` |
| the validation of the documents in the tests | `cgmlval` of `cyberiadaml-compat-tests` |
| showing a diagram as text | `hsmview.py` of `hsm-console-viewer` |
| editing a diagram by hand | `CyberiadaPro` |

## Known limits

* One incoming transition per choice, no `do/` - limits of the library.
* A drawn composite that grows sideways in the update may shift its drawn
  neighbours (`libhtreegeom`).
* A drawn composite whose own actions grow keeps its size: the editor shows
  its content below the longer header, off the drawn routes into it.
* A new composite wrapping drawn states is placed after the drawn ones it
  follows; the place the states left stays empty.
* Several regions and internal transitions without an event are not in
  the notation; the formal comments are shown as notes and kept, the
  links to an initial or its transition are kept unseen.

## Roadmap

1. Platforms: the components, signals and methods of a platform
   description given to the model, `CGML_COMPONENT` declarations written.
2. The rest of the standard: several regions.
3. A review step for the design of the diagram, not only its form.
4. Layout hints of the notation (the direction) passed to the layout.
5. A component of `cybersphere-agents`: the specifications as diagrams.

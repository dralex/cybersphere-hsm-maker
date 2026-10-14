# The Cybersphere HSM Maker Architecture

Document version: 0.3 (2026-10-14)

The maker turns a description of a system written in a natural language
into a Hierarchical State Machine (HSM) diagram stored in the
CyberiadaML-GraphML format (CGML, PNST 1044-2025) with the semantics of
PNST 984-2024. A language model writes the structure of the diagram in a
compact text notation; the maker parses and checks it, returns the
mistakes to the model until the diagram is correct, builds the document
with the `CyberiadaML` binding (`libcyberiadamlpp-py`) and lays it out.
It changes an existing diagram the same way: the model sees the diagram in
the notation and answers the changed one, the maker applies the difference
to the same document and lays out only what is new.

The maker is a library first and a command second. It depends on the
`CyberiadaML` binding and on the Python 3 standard library only: no agent
framework, no vendor SDK, no editor.

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
                      +-------------+       CyberiadaML binding
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
| R7 | Python 3.8+, the standard library and the binding only. | Code layout |
| R8 | Limit the requests and report the usage: requests, tokens. | The client |
| R9 | Change an existing diagram by a description of the change; what is not changed keeps its identity, its place and the parts the notation does not show. | The update |
| R10 | Run from `CyberiadaHSM-Editor`: draw a new diagram, change the open one. | The editor plugin |

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
opens in `CyberiadaHSM-Editor` only with the reconstruction on loading.

## The update

`hsm-maker --update in.graphml` changes a diagram. The answer of the model
is the whole changed diagram; the maker applies the difference to the
document itself, so an element that stays keeps its identifier, its
geometry and what the notation does not show: comments, component
declarations, prompts, colours, meta parameters.

```
 in.graphml --decode--> Document --read--> old tree (+ element ids)
                                              |
                          render: the notation, "# note:" lines for the
                          hidden parts, `_n` names for unnamed elements
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
                  3 move (copy + remove + add, the geometry cleaned),
                    rename
                  4 add the new transitions; update the changed actions
                                              |
                 update_geometry: the drawing kept, the new parts laid out
                                              v
                        encode --> strict verify --> out.graphml
```

* **Identity.** A machine by its name; a vertex by its path in the old
  diagram - the `(was OLD)` of its line, else the old path of its parent
  and its name; the initial by its container; a `_n` name by the unnamed
  element it was given to. A transition by its source, event, guard,
  propagation and target: the same key with another action is an action
  change, anything else is a removal and an addition. A vertex of another
  kind under the same name is removed and added.
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
  moved, actions changed - with the element identifiers; `--diagnostics`
  writes them for the editor.
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
the prompt has more Cyrillic than Latin letters, else English. The same
language serves the system prompt, the feedback to the model and the
issues the command prints. The Russian texts use the terms of PNST 984,
clause 3. The keywords of the notation are English in every language;
names, events, guards and actions may be written in any script.

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
| `hsm_maker/notation.py` | the notation tree, `extract`, `parse`, `analyze`; no binding |
| `hsm_maker/builder.py` | the tree to a `CyberiadaML.Document`, the layout, `encode`, `verify` |
| `hsm_maker/client.py` | the protocols, the retries, the usage, the key |
| `hsm_maker/language.py` | the languages, the detection, the texts |
| `hsm_maker/reader.py` | a `CyberiadaML.Document` to the notation tree with the element ids and the notes |
| `hsm_maker/patcher.py` | the difference of two trees applied to a document, the change list |
| `hsm_maker/maker.py` | `convert`, `change` (one notation to a document) and `run` (the loop) |
| `hsm_maker/cli.py` | the command `hsm-maker` |
| `hsm_maker/prompts/` | the texts of the languages |
| `editor-plugin/` | the plugin of `CyberiadaHSM-Editor`: `plugin.json`, the icons, its README |

## The editor plugin

`editor-plugin/` is the plugin of `CyberiadaHSM-Editor` (contract `api` 1
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
model, server, protocol, language, rounds and the key (`env:NAME` or
`file:PATH`, exported to the run as `HSM_MAKER_KEY`, never in the command
line). The description and the change are asked at every run. The
`change` action keeps the identifiers of what it does not change, so the
selection and the earlier findings still point at them; its diagnostics
list the changes with links to the elements. The maker and the binding
must be importable by the interpreter the editor uses for `python3`.

## Testing

The tests use pytest and need no model and no network: a scripted client
plays the model in the loop, a local HTTP stub plays the server for the
client. The notation tests pin every issue code and its line; the builder
tests compare the documents built without geometry with the good files of
`tests/good` and check the documents with geometry by the strict reading
and by the validator of `cyberiadaml-compat-tests` when it is found beside
the repository. A static test keeps the sources inside the Python 3.8
syntax. A run with a real model is a manual step.

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
and opened in `CyberiadaHSM-Editor`. The checks see the form of a diagram,
not its design: a model may simplify the behaviour of a description.

## Reuse

| Need | Existing tool |
|---|---|
| writing, reading and checking CGML | `libcyberiadamlpp-py` (`CyberiadaML`) |
| the layout | `libhtreegeom` through the binding |
| the validation of the documents in the tests | `cgmlval` of `cyberiadaml-compat-tests` |
| showing a diagram as text | `hsmview.py` of `hsm-console-viewer` |
| editing a diagram by hand | `CyberiadaHSM-Editor` |

## Known limits

* One incoming transition per choice, no `do/` - limits of the library.
* A drawn composite that grows sideways in the update may shift its drawn
  neighbours (`libhtreegeom`).
* Comments, several regions and internal transitions without an event are
  not in the notation; a changed diagram keeps its comments.

## Roadmap

1. Platforms: the components, signals and methods of a platform
   description given to the model, `CGML_COMPONENT` declarations written.
2. The rest of the standard: comments, several regions.
3. A review step for the design of the diagram, not only its form.
4. Layout hints of the notation (the direction) passed to the layout.
5. A component of `cybersphere-agents`: the specifications as diagrams.

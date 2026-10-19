# Cyberiada Cybersphere: The HSM Diagram Maker

The LLM-based HSM drawing utility of the Cyberiada project. It turns a
description of a system written in a natural language into a Hierarchical
State Machine diagram stored in the CyberiadaML-GraphML format (PNST
1044-2025). A language model writes the structure of the diagram in a
compact text notation; the maker checks it, returns the mistakes to the
model until the diagram is correct, builds the document with the
`CyberiadaML` module and lays it out. The maker is written in pure Python
3 and talks to any model server of the `chat-completions` or the
`messages` protocol.

The code is distributed under the Lesser GNU Public License (version 3), the
documentation -- under the GNU Free Documentation License (version 1.3).

## Documentation

The documentation is located in the `docs` directory and contains:

* The architecture - `ARCHITECTURE.md`: the process, the geometry, the
  languages, the configuration, the testing
* The notation - `NOTATION.md`: the text the model writes, its checks and
  its mapping onto CyberiadaML
* The interface specification - `API.md`: the modules of the package
  `hsm_maker` and the command `hsm-maker`

## Requirements

* python3 (version 3.8+)
* the `CyberiadaML` module: libcyberiadamlpp-py (version 1.0.8+, with
  libcyberiadamlpp and libcyberiadaml 1.0.8+, libhtreegeom 1.2+) or, when
  it is not installed, cyberiadaml-py (version 1.8+, Python 3.8.1+; on
  Windows Python 3.10+), its pure-Python interface
* pytest - for the tests
* cmake (version 3.16+) - for the Debian package

## Installation

The Debian package installs the maker, the command and the editor plugin:

    cmake -B build && cd build && ctest && cpack -G DEB
    sudo apt install ./python3-cybersphere-hsm-maker_0.1.0_all.deb

`ctest` runs the tests with the Python CMake finds; it needs pytest and the
binding (`-DPython3_EXECUTABLE=...` selects another one). The package
depends on `python3-libcyberiadamlpp` or `python3-cyberiadaml`; the plugin
goes to
`/usr/share/cyberiada-pro/plugins/hsm-maker/`, where `CyberiadaPro`
finds it.

With pip (a virtual environment, the user site, Windows, macOS) the maker
needs no binary build: pip installs cyberiadaml-py with it (on Windows from
Python 3.10; an older Windows Python needs the binding), and the maker uses
the binding only when it is installed; then

    pip install /path/to/cybersphere-hsm-maker
    hsm-maker --install-editor-plugin

copies the plugin into the editor's user plugin folder (or a given folder),
bound to the Python that runs the command.

## Usage

    export DEEPSEEK_API_KEY=...
    hsm-maker --url https://api.deepseek.com/v1 --model deepseek-flash \
        -o bomb.graphml "A countdown time bomb: UP and DOWN set the time, ARM arms it ..."

The model is chosen by `--protocol` (`chat-completions` by default or
`messages`), `--url` and `--model`, or by the environment variables
`HSM_MAKER_PROTOCOL`, `HSM_MAKER_URL` and `HSM_MAKER_MODEL`. The key is read
from the variable named by `--key-env`, else from `HSM_MAKER_API_KEY`, else
from the variable named after the server (`DEEPSEEK_API_KEY` for
`api.deepseek.com`); a local server needs none. The prompt comes from the
command line, from a file (`-f`) or from the standard input. `--language`
selects the language of the instructions (`en`, `ru`; by default the
language of the prompt). `--code-language` sets the programming language
of the actions (`Python`, `C++`, ...; by default the model declares it).
`--geometry none` saves the diagram without the
layout. `--notation FILE` builds a diagram from a notation file without a
model.

    hsm-maker --update lift.graphml -o lift2.graphml "add a maintenance mode"
    hsm-maker --render lift.graphml

`--update FILE` changes an existing diagram: what the change does not touch
keeps its identifier, its place and its comments, the new elements are
placed around the drawing. `--render FILE` prints a diagram in the notation.
`--diagnostics FILE` writes the issues and the changes as JSON.
`editor-plugin/` is the plugin of `CyberiadaPro` (see its README).

From Python:

```python
import hsm_maker

result = hsm_maker.make('A traffic light with a night mode ...',
                        url='http://localhost:8080/v1', model='local')
if result.ok:
    open('light.graphml', 'w', encoding='utf-8').write(result.graphml)
```

## Tests

    python3 -m pytest tests

The tests cover the notation parser and its checks, the building of the
documents, both protocols of the client against a local stub server, the
repair loop with a scripted model and the command line. The documents are
also checked with the validator of `cyberiadaml-compat-tests` when that
repository is found beside this one, and the editor plugin is run in the
batch mode of `CyberiadaPro` when its build is found there. `pylint.sh` runs the linter over the
sources. `REGEN=1` records the good files of `tests/good` again.

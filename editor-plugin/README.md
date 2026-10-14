# The HSM Maker plugin of the Cyberiada HSM Editor

The plugin brings the maker into `CyberiadaHSM-Editor`: draw a new diagram
from a description, change the open diagram by a description of the
change, or show the open diagram in the notation the model reads. The
description and the diagram are sent to the model server you choose.

## Installation

1. Install the maker and the `CyberiadaML` binding for the Python the
   editor runs, for example a virtual environment:

       python3 -m venv ~/hsm-venv
       ~/hsm-venv/bin/pip install /path/to/cybersphere-hsm-maker
       # the binding: its own build or package (libcyberiadamlpp-py)

2. In the editor, Preferences > Plugins: set the interpreter `python3` to
   that Python (`~/hsm-venv/bin/python`).
3. Copy this directory as `hsm-maker`:
   * Linux: `~/.local/share/Cyberiada/Cyberiada State Machine Editor/plugins/hsm-maker/`
   * Windows: `%APPDATA%\Cyberiada\Cyberiada State Machine Editor\plugins\hsm-maker\`
4. Restart the editor: the Plugins menu gets HSM Maker, the toolbar its two
   buttons.

## Use

```
 Plugins > HSM Maker > Draw a new diagram...   a new tab with the diagram
                       Change the diagram...   the open diagram changed (one undo step)
                       Show the notation       the notation in the plugin Output
                       Settings...             model, server, protocol, key, language, rounds
```

* **Draw a new diagram...** asks for the description and opens the result
  as a new document.
* **Change the diagram...** asks what to change and how to lay it out:
  `update` keeps your drawing and places only the new elements, `full`
  lays the whole diagram out anew. Unchanged elements keep their
  identifiers; the Diagnostics tab lists every change with a link to the
  element. Undo restores the diagram.
* The settings are asked once and kept: the model (`deepseek-flash`), the
  server (`https://api.deepseek.com/v1`, any server of the
  `chat-completions` or `messages` protocol, a local one too), the key as
  `env:NAME` or `file:PATH` (empty for a local server), the language of the
  instructions and the rounds of correction.

A run takes from a few seconds to a few minutes; the Output tab shows the
rounds and the tokens spent, Cancel stops it.

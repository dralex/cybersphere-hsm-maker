# The HSM Maker plugin of the Cyberiada HSM Editor

The plugin brings the maker into `CyberiadaHSM-Editor`: draw a new diagram
from a description, change the open diagram by a description of the
change, or show the open diagram in the notation the model reads. The
description and the diagram are sent to the model server you choose.

## Installation

* The Debian package `python3-cybersphere-hsm-maker` installs the plugin
  with the maker: nothing else to do. `python3` of the system runs it.
* With pip, install the maker and the `CyberiadaML` binding for one Python,
  for example a virtual environment, then let the maker install the plugin:

      python3 -m venv --system-site-packages ~/hsm-venv
      ~/hsm-venv/bin/pip install /path/to/cybersphere-hsm-maker
      ~/hsm-venv/bin/hsm-maker --install-editor-plugin

  The plugin goes to the editor's user plugin folder and runs that Python
  (`~/hsm-venv/bin/python`), so the editor needs no interpreter setting.
  Run the command again after an upgrade of the maker.
* By hand: copy this directory as `hsm-maker` into the user plugin folder
  and set the interpreter `python3` in Preferences > Plugins to a Python
  that has the maker and the binding.

| System | The user plugin folder |
|---|---|
| Linux | `~/.local/share/Cyberiada/Cyberiada State Machine Editor/plugins/` |
| Windows | `%APPDATA%\Cyberiada\Cyberiada State Machine Editor\plugins\` |
| macOS | `~/Library/Application Support/Cyberiada/Cyberiada State Machine Editor/plugins/` |

Restart the editor: the Plugins menu gets HSM Maker, the toolbar its two
buttons.

## Use

```
 Plugins > HSM Maker > Draw a new diagram...   a new tab with the diagram
                       Change the diagram...   the open diagram changed (one undo step)
                       Show the notation       the notation in the plugin Output
                       Settings...             model, server, protocol, key, language,
                                               code language, rounds
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
  instructions and the rounds of correction. With `auto` the description
  decides the language; one without a majority of letters takes the
  editor's interface language.
* **Code language** - the programming language of the actions, the
  `platformLanguage` of the diagram that the editor highlights. With
  `auto` the model chooses it from the description (none when nothing
  hints at one), and a changed diagram keeps its own unless the change
  asks for another; a chosen language is asked of the model and written.
* The menu and the dialog texts follow the editor's interface language
  (`i18n/ru.json`).

A run takes from a few seconds to a few minutes; the Output tab shows the
rounds and the tokens spent, Cancel stops it.

# cybersphere-hsm-maker project changelog

## Version 0.1.0

Added:
- the pure-Python interface of cyberiadaml-py is a dependency from Python
  3.8.1 (was 3.10), on Windows from Python 3.10 (the older Windows Python
  runs the binding); the Debian package takes `python3-cyberiadaml` when
  the binding package is not installed.
- the maker of CyberiadaML diagrams from a description: the name-based text
  notation the model writes, its checks and the rounds of repair, the
  layout; the `chat-completions` and `messages` protocols; the instructions
  in English and Russian;
- the points, the submachine states, the history and the event propagation
  in the notation;
- the change of an existing diagram (`--update`): what the change does not
  touch keeps its identifier, its drawing and its comments;
- the plugin of CyberiadaPro: draw, change, show the notation;

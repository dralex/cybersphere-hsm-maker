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
- the comments in the notation: a title, a Markdown text and the links to
  states, transitions, other comments and fragments of their texts; the
  model is asked to comment what the diagram does not say, and an update
  adds, edits, relinks and removes comments;
- the change of an existing diagram (`--update`): what the change does not
  touch keeps its identifier, its drawing and its comments;
- the plugin of CyberiadaPro: draw, change, show the notation;
- the pictures (`--picture`, the optional Picture of the plugin dialogs): a
  PNG, JPEG, GIF or WebP picture of a statechart or another schema with a
  short comment makes or changes a diagram; a model that does not see it
  stops the run;
- the messages of a run: the progress of every round, a failure explained
  with the lines of the answer and a hint what to do (the key, the
  balance, the model, the server, the rounds), the dialog with the model
  by `-v` (`-vv` with the system prompt) and the Show the dialog setting
  of the plugin;
- the routing (`--routing orthogonal|polyline`, the Routing setting of the
  plugin; `routing` of the API): the transitions in runs along and across
  the flow by default, the straight segments on request (libhtreegeom 1.3);
- the placement: a diagram drawn from a picture is arranged as the picture,
  its proportions and the sides the transitions leave and enter by kept, by one more request and the arrange layout of
  libhtreegeom 1.3
  (`--geometry picture`, the default with `--picture`; `--picture-size`;
  the Layout and Picture size options of the plugin); a failed placement
  keeps the full layout with a warning;

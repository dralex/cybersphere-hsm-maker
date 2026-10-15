# cybersphere-hsm-maker project changelog

## Version 0.1.0 (unreleased)

Added:
- the maker of CyberiadaML diagrams from a description: the name-based text
  notation the model writes, its checks and the rounds of repair, the
  layout; the `chat-completions` and `messages` protocols; the instructions
  in English and Russian;
- the points, the submachine states, the history and the event propagation
  in the notation;
- the change of an existing diagram (`--update`): what the change does not
  touch keeps its identifier, its drawing and its comments;
- the plugin of CyberiadaPro: draw, change, show the notation;
- the code language: the `language:` header of the notation, written as
  the `platformLanguage` of the document, `--code-language` and the
  plugin setting;
- the Debian package and the installation of the editor plugin with pip
  (`--install-editor-plugin`).

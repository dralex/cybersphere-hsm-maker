# The HSM Maker Notation

Document version: 0.1 (2026-10-13)

The notation is the text a language model writes for the maker: the
structure of one CyberiadaML document, without identifiers and without
geometry. A line is an element, the indentation is the nesting, a
transition names its target, and the behaviour is the action text of PNST
1044, 6.8. The maker checks the text, builds the document through the
`CyberiadaML` binding and reports every issue with its line.

```hsm
name: Lift
description: A lift with one call button on every floor
machine Lift
  initial -> Idle / floor = 1
  state Idle
    entry/ lamp_off()
    CALL [call_floor > floor] -> MovingUp
        / target = call_floor
    CALL [call_floor < floor] -> MovingDown
        / target = call_floor
    CALL [call_floor == floor] -> DoorsOpen
  state Moving
    entry/ lamp_on()
    exit/ stop_motor()
    state MovingUp
      entry/ motor_up()
      FLOOR [floor != target] / floor += 1
    state MovingDown
      entry/ motor_down()
      FLOOR [floor != target] / floor -= 1
    FLOOR [floor == target] -> DoorsOpen
  state DoorsOpen
    entry/ open_doors()
    TIMEOUT -> Idle / close_doors()
```

## Lines

| Line | Element | Where |
|---|---|---|
| `name: TEXT` | the document name (meta `name`) | before the first machine, once |
| `description: TEXT` | the document description (meta `description`) | before the first machine, once |
| `machine NAME` | a state machine | the top level |
| `state NAME` | a state; a state with child states is composite | a machine, a state |
| `initial -> TARGET [/ ACTION]` | the initial pseudostate of the level and its transition | a machine, a state |
| `final NAME` | a final state | a machine, a state |
| `terminate NAME` | a terminate pseudostate | a machine, a state |
| `choice NAME` | a choice pseudostate | a machine, a state |
| `[GUARD] -> TARGET [/ ACTION]` | a branch of the choice; one guard may be `[else]` | a choice |
| `entry/ ACTION`, `exit/ ACTION` | the entry and the exit behaviour | a state, once each |
| `EVENT [GUARD] -> TARGET [/ ACTION]` | an external transition from the state | a state |
| `EVENT [GUARD] / [ACTION]` | an internal transition: the state is not left | a state |
| `[GUARD] -> TARGET [/ ACTION]` | a completion transition (no event) | a state |

The parts in brackets `[...]` of the first column are optional, except the
guard brackets themselves.

## Lexical rules

* The text is UTF-8; the line ends may be LF or CRLF; trailing spaces are
  ignored.
* The indentation is made of spaces; a tab in it is an error. The parent
  of a line is the nearest line above it with a smaller indentation that
  opens a block: `machine`, `state` or `choice`. The width of a level is
  free; two spaces are recommended.
* A line indented deeper than the line above it, when that line does not
  open a block, **continues** it: a long action, or the `/ ACTION` part of
  a transition on its own line. The continuation lines keep their
  indentation relative to each other and are joined with line breaks.
* A line whose first character after the indentation is `#` is a comment,
  also between the lines of an action. Blank lines are ignored everywhere.
* A name is a word of letters, digits and `_` in any script, or a quoted
  name `"Doors open"` without quotes and without `::` inside.
* The keywords are English and case-sensitive: `machine`, `state`,
  `initial`, `final`, `terminate`, `choice`, `entry/`, `exit/`, `name:`,
  `description:`. `entry /` and `exit /` are accepted too.

## Grammar

```
diagram     = { header } machine { machine } ;
header      = ( "name:" | "description:" ) text ;
machine     = "machine" name { vertex } ;                  (* children indented *)
vertex      = state | initial | final | terminate | choice ;
state       = "state" name { vertex | behaviour | transition } ;
initial     = "initial" "->" target [ "/" action ] ;
final       = "final" name ;
terminate   = "terminate" name ;
choice      = "choice" name branch { branch } ;
branch      = guard "->" target [ "/" action ] ;
behaviour   = ( "entry/" | "exit/" ) action ;
transition  = event [ guard ] "->" target [ "/" action ]   (* external *)
            | event [ guard ] "/" [ action ]               (* internal *)
            | [ guard ] "->" target [ "/" action ] ;       (* completion *)
event       = word [ { word | " " | "." } word ] [ "(" word ")" ] ;
guard       = "[" ( "else" | condition ) "]" ;
target      = name { "::" name } ;
name        = word | '"' text '"' ;
```

* `event` is the trigger syntax of PNST 1044, 6.8.1: one event, letters,
  digits, `_`, inner spaces and dots, one optional parameter in
  parentheses (`CALL(floor)`, `button.PRESSED`). A space-separated word of
  an event may not be `entry`, `exit`, `do`, `propagate`, `block`, `defer`
  or `else`. The events in capitals are recommended (PNST 984, 7.11.7).
* `condition` is any text without `[` and `]`; write `\[` and `\]` for the
  brackets.
* `action` is the rest of the line and its continuation lines: statements
  of the platform language. It may not start with the word `defer`.

## Names and targets

Names are unique among the vertices of one level (the children of one
machine or one state); machine names are unique in the document. A target
of a transition leaving the vertex `V` is found:

1. among the vertices of the level of `V`;
2. among the vertices of each enclosing level, outwards to the machine;
3. in the whole machine, when the name is unique there.

A name found more than once in the machine needs its path from the top of
the machine: `Moving::MovingUp` - the qualified name of the `CyberiadaML`
binding. A transition never leaves its machine. A final, a terminate or a
choice is a target by its name, so each of them is declared with one.

## Checks

The issues come in stages: the syntax first, then the names and the
semantics, then the library; the next stage runs only when the previous
one found no error. An issue is reported as `line N: message`. A warning
does not stop the diagram. The texts below are the English ones; every
language of the maker has its own.

| Code | Message |
|---|---|
| N01 | tab in the indentation; indent with spaces |
| N02 | expected 'machine NAME' at the top level |
| N03 | a machine must be at the top level |
| N04 | the diagram has no machine |
| N05 | cannot read the line: {text} |
| N06 | bad name '{text}': use letters, digits and _ or a "quoted name" |
| N07 | {keyword} needs a name |
| N08 | unterminated quoted name |
| N09 | the name '{text}' contains '::', the path separator |
| N10 | a transition must be inside the state it leaves |
| N11 | entry/ and exit/ belong to a state |
| N12 | a choice holds only its branches: [GUARD] -> TARGET / ACTION |
| N13 | bad event '{event}': letters, digits, _, inner spaces and dots, one optional (parameter) |
| N14 | the event '{event}' uses the reserved word '{word}' |
| N15 | unterminated guard: ']' is missing |
| N16 | '[' inside the guard; write \\[ and \\] |
| N17 | empty guard |
| N18 | expected a target after '->' |
| N19 | expected '-> TARGET' or '/ ACTION' after the event '{event}' |
| N20 | unexpected text '{text}'; the order is EVENT [GUARD] -> TARGET / ACTION |
| N21 | empty {keyword} action |
| N22 | do/ is not supported; use entry/ or an internal transition |
| N23 | the action cannot start with the word 'defer' |
| N24 | the initial transition has no event and no guard: initial -> TARGET / ACTION |
| N25 | a choice branch needs a guard; use [else] for the default |
| N26 | unexpected text after {keyword} '{name}': {text} |
| N27 | the header '{header}' is allowed once, before the first machine |
| N28 | empty header '{header}' |
| N29 | an internal transition needs an event |
| R01 | unknown target '{target}'; known: {known} |
| R02 | ambiguous target '{target}': {candidates}; write the path |
| R03 | '{target}' is a keyword, not a name; declare '{target} NAME' and target the NAME |
| R04 | '{target}' is the machine; target a vertex inside it |
| S01 | duplicate machine name '{name}' (first at line {first}) |
| S02 | duplicate name '{name}' on one level (first at line {first}) |
| S03 | second initial on one level (first at line {first}) |
| S04 | machine '{name}' has no initial at its top level |
| S05 | machine '{name}' is empty |
| S06 | second {keyword} in the state '{name}' |
| S07 | the initial transition must target a vertex of its own level or below it |
| S08 | the transition enters the composite state '{target}' that has no initial; add 'initial -> ...' inside it or target a substate |
| S09 | choice '{name}' needs at least two branches |
| S10 | choice '{name}' has more than one incoming transition (lines {lines}); use one choice per source |
| S11 | more than one [else] leaves '{name}' |
| W01 | '{name}' is unreachable |
| B01 | the library rejected the element: {message} |
| B02 | the strict check of the document failed: {message} |

`{known}` lists the closest names of the machine, or its first names when
none is close. S08 does not apply to a transition from a substate of the
target: it stays inside the composite state (PNST 1044, 6.3.2). W01 is
counted from the top initial: a vertex is reached when a transition of it,
of one of its enclosing states or of an initial leads there.

## Mapping onto CyberiadaML

The notation order is the creation order: the vertices in the first pass,
the transitions in the second one.

| Notation | `CyberiadaML` call |
|---|---|
| `name:` | `document.set_name(text)` |
| `description:` | `document.meta().set_string('description', text)` |
| `machine NAME` | `document.new_state_machine(NAME)` |
| `state NAME` | `document.new_state(parent, NAME)` |
| `initial` | `document.new_initial(parent)` |
| `final NAME` | `document.new_final(parent, NAME)` |
| `terminate NAME` | `document.new_terminate(parent, NAME)` |
| `choice NAME` | `document.new_choice(parent, NAME)` |
| `entry/ A`, `exit/ A` | `state.add_action(Action(actionEntry, A))`, `actionExit` |
| `E [G] / A` | `state.add_action(Action(E, G, A))` |
| a transition, a branch, the initial transition | `document.new_transition(machine, transitionExternal, source, target, Action(E, G, A))` |

The identifiers are given by the library (`n0`, `n0::n1`, `n0-n1#0`). The
geometry is added by the layout of the library or left out (see
`ARCHITECTURE.md`).

## Limits

* One incoming transition per choice - a limit of the library; use one
  choice per source.
* No `do/`, no `propagate`, `block` and `defer` - not supported by the
  library or not needed for a new diagram.
* History, entry and exit points, submachine states, comments and several
  regions are not in this version.
* PNST 1044, 6.3.2: the format does not distinguish the local and the
  external transitions.

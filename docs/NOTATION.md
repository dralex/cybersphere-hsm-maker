# The HSM Maker Notation

Document version: 0.3 (2026-10-15)

The notation is the text a language model writes for the maker: the
structure of one CyberiadaML document, without identifiers and without
geometry. A line is an element, the indentation is the nesting, a
transition names its target, and the behaviour is the action text of PNST
1044, 6.8. The maker checks the text, builds the document through the
`CyberiadaML` binding and reports every issue with its line. When a
diagram is changed, the maker writes the diagram in the notation for the
model and applies the model's answer to the same document.

```hsm
name: Lift
description: A lift with one call button on every floor
language: Python
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
| `language: NAME` | the programming language of the actions (meta `platformLanguage`) | before the first machine, once |
| `machine NAME` | a state machine | the top level |
| `state NAME` | a state; a state with child states is composite | a machine, a state |
| `initial -> TARGET [/ ACTION]` | the initial pseudostate of the level and its transition | a machine, a state |
| `final NAME` | a final state | a machine, a state |
| `terminate NAME` | a terminate pseudostate | a machine, a state |
| `choice NAME` | a choice pseudostate | a machine, a state |
| `[GUARD] -> TARGET [/ ACTION]` | a branch of the choice; one guard may be `[else]` | a choice |
| `history NAME [-> TARGET [/ ACTION]]` | a shallow history with its optional default transition | a state |
| `deep history NAME [-> TARGET [/ ACTION]]` | a deep history | a state |
| `entry point NAME [[EVENT] [GUARD] -> TARGET [/ ACTION]]` | an entry point; its transition leads inside | a machine, a state, a submachine |
| `exit point NAME [[EVENT] [GUARD] -> TARGET [/ ACTION]]` | an exit point; its transition leads outside, it may wait for an event | a state, a submachine, a machine (no transition) |
| `submachine NAME of MACHINE` | a submachine state standing for another machine of the document | a machine, a state |
| `entry/ ACTION`, `exit/ ACTION` | the entry and the exit behaviour | a state, once each |
| `EVENT [GUARD] [propagate\|block] -> TARGET [/ ACTION]` | an external transition from the state | a state, a submachine |
| `EVENT [GUARD] [propagate\|block] / [ACTION]` | an internal transition: the state is not left | a state |
| `EVENT [GUARD] / defer` | a deferred event: kept until the state is left | a state |
| `[GUARD] -> TARGET [/ ACTION]` | a completion transition (no event) | a state, a submachine |

The parts in brackets `[...]` of the first column are optional, except the
guard brackets themselves.

## Lexical rules

* The text is UTF-8; the line ends may be LF or CRLF; trailing spaces are
  ignored.
* The indentation is made of spaces; a tab in it is an error. The parent
  of a line is the nearest line above it with a smaller indentation that
  opens a block: `machine`, `state`, `choice` or `submachine`. The width
  of a level is free; two spaces are recommended.
* A line indented deeper than the line above it, when that line does not
  open a block, **continues** it: a long action, or the `/ ACTION` part of
  a transition on its own line. The continuation lines keep their
  indentation relative to each other and are joined with line breaks.
* A line whose first character after the indentation is `#` is a comment,
  also between the lines of an action. Blank lines are ignored everywhere.
* A name is a word of letters, digits and `_` in any script, or a quoted
  name `"Doors open"` without quotes and without `::` inside.
* The keywords are English and case-sensitive: `machine`, `state`,
  `initial`, `final`, `terminate`, `choice`, `history`, `deep history`,
  `entry point`, `exit point`, `submachine`, `of`, `entry/`, `exit/`,
  `propagate`, `block`, `defer`, `was`, `name:`, `description:`,
  `language:`.
  `entry /` and `exit /` are accepted too.

## Grammar

```
diagram     = { header } machine { machine } ;
header      = ( "name:" | "description:" | "language:" ) text ;
machine     = "machine" declared { vertex } ;                  (* children indented *)
vertex      = state | initial | final | terminate | choice | history | point | submachine ;
state       = "state" declared { vertex | behaviour | transition } ;
initial     = "initial" "->" target [ "/" action ] ;
final       = "final" declared ;
terminate   = "terminate" declared ;
choice      = "choice" declared branch { branch } ;
branch      = guard "->" target [ "/" action ] ;
history     = [ "deep" ] "history" declared [ "->" target [ "/" action ] ] ;
point       = ( "entry" | "exit" ) "point" declared
              [ [ event ] [ guard ] "->" target [ "/" action ] ] ;
submachine  = "submachine" declared "of" name { point | transition } ;
behaviour   = ( "entry/" | "exit/" ) action ;
transition  = event [ guard ] [ flag ] "->" target [ "/" action ]   (* external *)
            | event [ guard ] [ flag ] "/" [ action ]               (* internal *)
            | event [ guard ] "/" "defer"                           (* deferred *)
            | [ guard ] "->" target [ "/" action ] ;                (* completion *)
flag        = "propagate" | "block" ;
declared    = name [ "(" "was" target ")" ] ;
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
* `flag` passes a handled event on to the enclosing states (`propagate`)
  or stops it (`block`), PNST 1044, 6.8.2.
* `condition` is any text without `[` and `]`; write `\[` and `\]` for the
  brackets.
* `action` is the rest of the line and its continuation lines: statements
  of the `language:` header's language. `defer` stands alone.
* `language:` takes any name; `C`, `C++`, `C#`, `Java`, `JavaScript` and
  `Python` - the languages of the editor - are written in this spelling
  whatever their case (`python` - `Python`).
* `(was OLD)` is used only when a diagram is changed (see below).

## Names and targets

Names are unique among the vertices of one level (the children of one
machine, one state or one submachine); machine names are unique in the
document. A target of a transition leaving the vertex `V` is found:

1. among the vertices of the level of `V`;
2. among the vertices of each enclosing level, outwards to the machine;
3. in the whole machine, when the name is unique there.

A name found more than once in the machine needs its path from the top of
the machine: `Moving::MovingUp` - the qualified name of the `CyberiadaML`
binding. A transition never leaves its machine. A final, a terminate, a
choice, a history and a point are targets by their names, so each of them
is declared with one.

## Points, submachines and history

```hsm
machine Caller
  initial -> Ready
  state Ready
    GO -> Job::Start
  submachine Job of Worker
    entry point Start
    exit point Done -> Ready
    exit point Failed -> Alarm
    ABORT -> Ready
  state Alarm
    RESET -> Ready
machine Worker
  initial -> Busy
  entry point Start -> Busy
  state Busy
    entry/ work()
    WORK_DONE -> Done
    WORK_FAILED -> Failed
  exit point Done
  exit point Failed
```

* An entry point of a state leads into the state: `entry point In ->
  Inner`; a transition from outside targets it by its path, `-> S::In`.
  An exit point of a state is the target of a transition from inside and
  leads outside: `exit point Out -> Next`.
* A submachine state stands for the machine named after `of`; its points
  are the points of that machine with the same names. A transition into
  the submachine targets an entry point (`-> Job::Start`); an exit point
  of the submachine leads on (`exit point Done -> Ready`), at once or on an
  event (`exit point Done FINISHED -> Ready`). The submachine holds no
  states and no behaviour.
* A machine's own entry point starts it (`entry point Start -> Busy`)
  when a submachine state enters it there; its exit point ends it and has
  no transition. Such a machine runs on its own too, so it has an initial.
* A history in a state remembers its last active substate (`deep history`
  - the whole nested configuration); its optional transition is taken when
  the state has not been active yet: `history H -> Waiting`.

## Changing a diagram

The maker writes the diagram in the notation for the model and applies
the answer to the same document: what stays the same keeps its identity,
its geometry and everything the notation does not show.

* **`(was OLD)`** after a declared name renames an element:
  `state Waiting (was Idle)`. A path moves it: `state Fan (was
  Cooling::Fan)`. Without it a renamed element counts as removed and new.
* **Unnamed elements** of the diagram are written with names starting with
  `_` (`final _final1`); such a name refers to that element, a new element
  may not start with `_`, and the element stays unnamed.
* **`language:`** - a missing header keeps the language of the diagram,
  another name changes it.
* **Notes** - the lines `# note: ...` show what the notation cannot
  express: comments, component declarations, prompts, the platform. They
  are kept by the maker whatever the answer holds.

```
machine Lift
  # note: comment "the call buttons" (on Waiting)
  initial -> Waiting / floor = 1
  state Waiting (was Idle)
    entry/ lamp_off()
    SERVICE -> Maintenance
  state Maintenance
    entry/ lock_doors()
    SERVICE_DONE -> Waiting
```

## Checks

The issues come in stages: the syntax first, then the names and the
semantics, then the library; the next stage runs only when the previous
one found no error. An issue is reported as `line N: message`. A warning
does not stop the diagram. When a diagram is changed, the semantic issues
the original diagram already had are reported as warnings. The texts below
are the English ones; every language of the maker has its own.

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
| N23 | defer stands alone: nothing may follow it |
| N24 | the initial transition has no event and no guard: initial -> TARGET / ACTION |
| N25 | a choice branch needs a guard; use [else] for the default |
| N26 | unexpected text after {keyword} '{name}': {text} |
| N27 | the header '{header}' is allowed once, before the first machine |
| N28 | empty header '{header}' |
| N29 | an internal transition needs an event |
| N30 | propagate and block need an event |
| N31 | defer belongs to an internal transition: EVENT [GUARD] / defer |
| N32 | write 'submachine NAME of MACHINE' |
| N33 | a submachine holds only its points and its transitions |
| N34 | {keyword} has no event and no guard: {keyword} NAME -> TARGET / ACTION |
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
| S12 | a history belongs to a state, not to the machine |
| S13 | second {keyword} in '{name}' (first at line {first}) |
| S14 | submachine '{name}' refers to the unknown machine '{machine}' |
| S15 | submachine '{name}' refers to its own machine |
| S16 | '{point}' is not a point of the machine '{machine}'; its points: {known} |
| S17 | an entry point of a submachine leads into its machine: remove '-> ...' |
| S18 | an exit point of a machine ends it: remove '-> ...' |
| W01 | '{name}' is unreachable |
| U01 | '(was {old})' is used only when a diagram is changed |
| U02 | the name '{name}' starts with _: such names belong to the unnamed elements of the diagram |
| U03 | '(was {old})' names no element of the diagram |
| U04 | '(was {old})' is claimed twice (first at line {first}) |
| B01 | the library rejected the element: {message} |
| B02 | the strict check of the document failed: {message} |

`{known}` lists the closest names of the machine, or its first names when
none is close. S08 does not apply to a transition from a substate of the
target: it stays inside the composite state (PNST 1044, 6.3.2). W01 is
counted from the top initial or the entry points of a machine: a vertex is
reached when a transition of it, of one of its enclosing states, of an
initial, a history or a point leads there.

## Mapping onto CyberiadaML

A new diagram is built in the notation order: the machines, then the
vertices, then the transitions.

| Notation | `CyberiadaML` call |
|---|---|
| `name:` | `document.set_name(text)` |
| `description:` | `document.meta().set_string('description', text)` |
| `language:` | `document.meta().set_string('platformLanguage', NAME)` |
| `machine NAME` | `document.new_state_machine(NAME)` |
| `state NAME` | `document.new_state(parent, NAME)` |
| `initial` | `document.new_initial(parent)` |
| `final NAME` | `document.new_final(parent, NAME)` |
| `terminate NAME` | `document.new_terminate(parent, NAME)` |
| `choice NAME` | `document.new_choice(parent, NAME)` |
| `history NAME`, `deep history NAME` | `document.new_shallow_history(parent, NAME)`, `new_deep_history` |
| `entry point NAME`, `exit point NAME` | `document.new_entry(parent, NAME)`, `new_exit` |
| `submachine NAME of M` | `document.new_submachine_state(parent, machine_id(M), NAME)` |
| `entry/ A`, `exit/ A` | `state.add_action(Action(actionEntry, A))`, `actionExit` |
| `E [G] / A` | `state.add_action(Action(E, G, A))` |
| `propagate`, `block`, `defer` | the propagation of the `Action`: `eventPropagationPropagate`, `Block`, `Defer` |
| a transition, a branch, an initial, history or point transition | `document.new_transition(machine, transitionExternal, source, target, Action(E, G, A))` |

The identifiers are given by the library (`n0`, `n0::n1`, `n0-n1#0`). The
geometry is added by the layout of the library or left out (see
`ARCHITECTURE.md`). A changed diagram is patched element by element (see
`ARCHITECTURE.md`, The update).

## Limits

* One incoming transition per choice - a limit of the library; use one
  choice per source.
* No `do/` - not supported by the library.
* Several regions in a state, and comments, are not in the notation; the
  comments of a changed diagram are kept as notes.
* An internal transition without an event is not in the notation.
* PNST 1044, 6.3.2: the format does not distinguish the local and the
  external transitions.

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import product
from typing import (
    Any,
    Dict,
    Generic,
    Iterable,
    List as TList,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

import tqdm
from synth.pruning.constraints.parsing import (
    Token,
    TokenAllow,
    TokenAtLeast,
    TokenAtMost,
    TokenFunction,
    TokenForceSubtree,
    TokenForbidSubtree,
    parse_specification,
)
from synth.syntax.automata.tree_automaton import DFTA
from synth.syntax.grammars.det_grammar import DerivableProgram
from synth.syntax.grammars.cfg import CFG
from synth.syntax.grammars.grammar import NGram
from synth.syntax.program import Variable
from synth.syntax.type_system import Type


# ========================================================================================
# PARSING
# ========================================================================================


U = TypeVar("U")
V = TypeVar("V")

State = Tuple[DerivableProgram, Tuple[U, ...]]


@dataclass
class ProcessState:
    new_terminal_no: int = field(default=1)
    duplicate_from: Dict[State, State] = field(default_factory=lambda: {})


@dataclass(frozen=True)
class Path(Generic[U]):
    predecessors: TList[Tuple[DerivableProgram, Tuple[U, ...], int]] = field(
        default_factory=lambda: []
    )

    def __hash__(self) -> int:
        return hash(tuple(self.predecessors))

    def __str__(self) -> str:
        if len(self) > 0:
            return "->".join(
                [
                    f"{P}(" + ",".join(map(str, args)) + ")"
                    for P, args, _ in self.predecessors
                ]
            )
        return "|"

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self) -> int:
        return len(self.predecessors)

    def last(self) -> Tuple[DerivableProgram, Tuple[U, ...], int]:
        return self.predecessors[-1]

    def next(self, P: DerivableProgram, args: Tuple[U, ...], index: int) -> "Path[U]":
        return Path(self.predecessors + [(P, args, index)])

    def next_argument(self) -> None:
        P, args, i = self.predecessors[-1]
        self.predecessors[-1] = (P, args, i + 1)


def __cfg2dfta__(
    grammar: CFG,
) -> DFTA[Tuple[Type, int], DerivableProgram]:
    StateT = Tuple[Type, int]
    dfta_rules: Dict[Tuple[DerivableProgram, Tuple[StateT, ...]], StateT] = {}
    max_depth = grammar.max_program_depth()
    all_cases: Dict[
        Tuple[int, Tuple[Type, ...]], Set[Tuple[Tuple[Type, int], ...]]
    ] = {}
    for S in grammar.rules:
        for P in grammar.rules[S]:
            args = grammar.rules[S][P][0]
            if len(args) == 0:
                dfta_rules[(P, ())] = (P.type, 0)
            else:
                key = (len(args), tuple([arg[0] for arg in args]))
                if key not in all_cases:
                    all_cases[key] = set(
                        [
                            tuple(x)
                            for x in product(
                                *[
                                    [(arg[0], j) for j in range(max_depth)]
                                    for arg in args
                                ]
                            )
                        ]
                    )
                for nargs in all_cases[key]:
                    dfta_rules[(P, nargs)] = (
                        P.type.returns(),
                        max(i for _, i in nargs) + 1,
                    )
    r = grammar.type_request.returns()
    return DFTA(dfta_rules, {(r, x) for x in range(max_depth)})


def __augment__(
    grammar: DFTA[Tuple[Type, U], DerivableProgram],
    relevant: TList[Tuple[Path, Tuple[Type, U]]],
) -> Tuple[
    DFTA[Tuple[Type, Tuple[U, int]], DerivableProgram],
    TList[Tuple[Path, Tuple[Type, Tuple[U, int]]]],
]:
    new_dfta = DFTA(
        {
            (P, tuple((arg[0], (arg[1], 0)) for arg in args)): (dst[0], (dst[1], 0))
            for (P, args), dst in grammar.rules.items()
        },
        {(t, (q, 0)) for t, q in grammar.finals},
    )
    new_relevant = [
        (
            Path(
                [
                    (P, tuple([(arg[0], (arg[1], 0)) for arg in args]), i)
                    for P, args, i in path.predecessors
                ]
            ),
            (S[0], (S[1], 0)),
        )
        for path, S in relevant
    ]

    return new_dfta, new_relevant


def __process__(
    grammar: DFTA[Tuple[Type, U], DerivableProgram],
    token: Token,
    sketch: bool,
    relevant: Optional[TList[Tuple[Path, Tuple[Type, U]]]] = None,
    level: int = 0,
    pstate: Optional[ProcessState] = None,
) -> Tuple[DFTA, TList[Tuple[Path, Tuple[Type, V]]]]:
    pstate = pstate or ProcessState()
    out_grammar: DFTA = grammar
    print("\t" * level, "processing:", token, "relevant:", relevant)
    if isinstance(token, TokenFunction):
        if relevant is None:
            # Compute relevant depending on sketch or not
            if sketch:
                relevant = [(Path(), q) for q in grammar.finals]
                grammar, relevant = __process__(
                    grammar, token.function, sketch, relevant, level, pstate
                )
            else:
                relevant = []
                for (P, args), dst in grammar.rules.items():
                    if P in token.function.allowed:
                        new_elem: Tuple[Path, Tuple[Type, U]] = (
                            Path(),
                            dst,
                        )
                        if new_elem not in relevant:
                            relevant.append(new_elem)
        else:
            # TODO: save or something alike
            # So here we have correct paths
            grammar, relevant = __process__(
                grammar, token.function, sketch, relevant, level, pstate
            )

        # Go from relevant to first argument context
        arg_relevant: TList[Tuple[Path, Tuple[Type, U]]] = []
        print("\t" * level, "relevant:", relevant)
        for path, end in relevant:
            for (P, args), dst in grammar.rules.items():
                if P in token.function.allowed and dst == end:
                    arg_relevant.append((path.next(P, args, 0), args[0]))
        print("\t" * level, "arg relevant:", arg_relevant)
        for arg in token.args:
            grammar, arg_relevant = __process__(
                grammar, arg, sketch, arg_relevant, level + 1, pstate
            )
        out_grammar = grammar
    elif isinstance(token, TokenAllow):
        assert relevant is not None
        # We need to augment grammar to tell that this we detected this the correct thing
        out_grammar, out_relevant = __augment__(grammar, relevant)
        old2new = lambda s: (s[0], (s[1][0], 1))
        relevant = []
        old_finals: Set[Tuple[Type, Tuple[U, int]]] = {q for q in out_grammar.finals}
        producables: Set[Tuple[Type, Tuple[U, int]]] = {
            dst for (P, args), dst in out_grammar.rules.items() if P in token.allowed
        }
        for path, path_end in out_relevant:
            new_end = old2new(path_end)
            for (P, p_args), p_dst in list(out_grammar.rules.items()):
                if p_dst == path_end and P in token.allowed:
                    out_grammar.rules[(P, p_args)] = new_end
                if any(arg == path_end for arg in p_args):
                    possibles = [
                        [arg] if arg != path_end else [arg, new_end] for arg in p_args
                    ]
                    for new_args in product(*possibles):
                        out_grammar.rules[(P, new_args)] = p_dst
                    # print("\t" * (level + 1), "P", P, "args", tuple([arg if arg != end else new_end for arg in args]), "=>", dst)
        for path, path_end in out_relevant:
            new_end = old2new(path_end)
            # Now we have to go back the track
            if len(path) == 0:
                if path_end in out_grammar.finals:
                    out_grammar.finals.remove(path_end)
                    out_grammar.finals.add(new_end)
            else:
                print("\t" * level, "path", path, "end", path_end)
                for P, p_args, i in reversed(path.predecessors):
                    old_dst = out_grammar.rules[(P, p_args)]
                    if p_args[i] not in producables:
                        continue
                    possibles = [
                        [arg, old2new(arg)] if j != i else [old2new(arg)]
                        for j, arg in enumerate(p_args)
                    ]
                    for new_args in product(*possibles):
                        out_grammar.rules[(P, new_args)] = old2new(old_dst)

                        print(
                            "\t" * (level + 1),
                            "REAL P",
                            P,
                            "args",
                            new_args,
                            "=>",
                            old2new(old_dst),
                        )
                    if old_dst in old_finals:
                        out_grammar.finals.add(old2new(old_dst))
                        if old_dst in out_grammar.finals:
                            out_grammar.finals.remove(old_dst)
            relevant.append((path, new_end))  # type: ignore
        # We don't need to go deeper in relevant since this is an end node
        out_grammar.reduce()
        print(out_grammar)
    elif isinstance(token, TokenAtMost):
        pass
    elif isinstance(token, TokenForbidSubtree):
        pass
    # Compute valid possible new states
    assert relevant is not None
    next_relevant: TList[Tuple[Path, Tuple[Type, V]]] = []
    for path, end in relevant:
        if len(path) == 0:
            next_relevant.append((path, end))  # type: ignore
            continue

        P, args, i = path.last()
        path.next_argument()
        if i >= len(args):
            continue
        next_relevant.append((path, args[i]))  # type: ignore
    return out_grammar, next_relevant


def add_dfta_constraints(
    current_grammar: CFG,
    constraints: Iterable[str],
    sketch: bool = False,
    progress: bool = True,
) -> DFTA[Set, DerivableProgram]:
    """
    Add constraints to the specified grammar.

    If sketch is True the constraints are for sketches otherwise they are pattern like.
    If progress is set to True use a tqdm progress bar.

    """
    constraint_plus = [(int("var" in c), c) for c in constraints]
    constraint_plus.sort(reverse=True)
    parsed_constraints = [
        parse_specification(constraint, current_grammar)
        for _, constraint in constraint_plus
    ]
    dfta = __cfg2dfta__(current_grammar)
    dfta.reduce()

    if progress:
        pbar = tqdm.tqdm(total=len(parsed_constraints), desc="constraints", smoothing=1)
    pstate = ProcessState()
    for constraint in parsed_constraints:
        dfta = __process__(dfta, constraint, sketch, pstate=pstate)[0]
        if progress:
            pbar.update(1)
    if progress:
        pbar.close()
    print(dfta)
    dfta.reduce()
    print(dfta)
    return dfta.minimise()  # type: ignore

import numpy as np

from synth.syntax.grammars.tagged_u_grammar import ProbUGrammar
from synth.syntax.grammars.u_cfg import UCFG
from synth.syntax.dsl import DSL
from synth.syntax.type_system import (
    INT,
    STRING,
    List,
    PolymorphicType,
    PrimitiveType,
)
from synth.syntax.type_helper import FunctionType

import pytest

syntax = {
    "+": FunctionType(INT, INT, INT),
    "-": FunctionType(INT, INT, INT),
    "head": FunctionType(List(PolymorphicType("a")), PolymorphicType("a")),
    "non_reachable": PrimitiveType("non_reachable"),
    "1": INT,
    "2": INT,
    "non_productive": FunctionType(INT, STRING),
}

dsl = DSL(syntax)
max_depths = [3, 7, 11]


@pytest.mark.parametrize("max_depth", max_depths)
def test_from_cfg(max_depth: int) -> None:
    cfg = UCFG.depth_constraint(dsl, FunctionType(INT, INT), max_depth)
    pcfg = ProbUGrammar.uniform(cfg)
    for rule in pcfg.rules:
        n = sum(len(pcfg.rules[rule][P]) for P in pcfg.rules[rule])
        for P in pcfg.rules[rule]:
            dico = pcfg.probabilities[rule][P]
            for _, prob in dico.items():
                assert np.isclose(prob, 1 / n)


# def test_from_ttcfg() -> None:
#     dsl = DSL(syntax)
#     for max_depth in [3, 7, 11]:
#         cfg = TTCFG.size_constraint(dsl, FunctionType(INT, INT), max_depth)
#         pcfg = ProbUGrammar.uniform(cfg)
#         for rule in pcfg.rules:
#             n = len(pcfg.rules[rule])
#             for P in pcfg.rules[rule]:
#                 prob = pcfg.probabilities[rule][P]
#                 assert np.isclose(prob, 1 / n)


@pytest.mark.parametrize("max_depth", max_depths)
def test_ready_for_sampling(max_depth: int) -> None:
    cfg = UCFG.depth_constraint(dsl, FunctionType(INT, INT), max_depth)
    pcfg = ProbUGrammar.uniform(cfg)
    assert not pcfg.ready_for_sampling
    pcfg.init_sampling()
    assert pcfg.ready_for_sampling


@pytest.mark.parametrize("max_depth", max_depths)
def test_seeding(max_depth: int) -> None:
    seed = 100
    cfg = UCFG.depth_constraint(dsl, FunctionType(INT, INT), max_depth)
    pcfg = ProbUGrammar.uniform(cfg)
    pcfg.init_sampling(seed)
    g1 = pcfg.sampling()
    cpy = ProbUGrammar.uniform(cfg)
    cpy.init_sampling(seed)
    assert pcfg == cpy
    g2 = cpy.sampling()
    for _ in range(200):
        p1, p2 = next(g1), next(g2)
        assert p1 == p2, f"[n°{_}]: {p1} != {p2}"


@pytest.mark.parametrize("max_depth", max_depths)
def test_depth(max_depth: int) -> None:
    cfg = UCFG.depth_constraint(dsl, FunctionType(INT, INT), max_depth)
    pcfg = ProbUGrammar.uniform(cfg)
    pcfg.init_sampling(0)
    g = pcfg.sampling()
    for _ in range(200):
        assert next(g).depth() <= max_depth

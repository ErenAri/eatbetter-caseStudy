from app.nutrition.normalization import canonical_gate_token_roles


def test_gate_roles_drop_function_words_and_normalize_accented_preparation() -> None:
    identity, preparation = canonical_gate_token_roles("rice and beans sautéed")

    assert identity == frozenset({"rice", "bean"})
    assert preparation == frozenset({"sauteed"})


def test_gate_roles_keep_collective_greens_distinct_from_green() -> None:
    identity, preparation = canonical_gate_token_roles("greens")

    assert identity == frozenset({"greens"})
    assert preparation == frozenset()

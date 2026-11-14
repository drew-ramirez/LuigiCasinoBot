import copy

from casinogames.pairagone.PairAGone import PairAGone


def test_pair_match_predicate_is_pure_and_matches_removal_rules():
    game = PairAGone(25)
    game.board = ["star", "star", "cloud", None, None] + [None] * 15
    game.deck = []
    before = copy.deepcopy(vars(game))
    assert game.is_match(0, 1)
    assert not game.is_match(0, 2)
    assert not game.is_match(3, 4)
    assert vars(game) == before
    assert not game.check_match(0, 2)
    assert vars(game) == before
    assert game.check_match(0, 1)
    assert game.board[0] == "cloud"
    assert game.board.count("star") == 0

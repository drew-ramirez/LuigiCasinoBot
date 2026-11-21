from casinogames.pairagone.PairAGone import PairAGone


def test_diagonal_pair_matches_without_revealing_or_removing_cards():
    game = PairAGone(25)
    game.board = ["star", "cloud", "star", None, None, None, "star"] + [None] * 13
    game.deck = ["flower", "mario"]
    before = game.board.copy()

    assert game.is_match(0, 6)
    assert not game.is_match(0, 1)
    assert not game.is_match(0, 2)
    assert not game.is_match(3, 4)
    assert game.board == before

    game.remove_and_fall([0, 6])
    assert game.board[:4] == ["cloud", "star", "mario", "flower"]

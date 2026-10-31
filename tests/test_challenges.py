import json
import pytest
from casinogames.challenges import MemoryMaster, EndlessPairs


@pytest.mark.parametrize('stars,size,cols,hints', [(0,16,4,4),(4,16,4,4),(5,18,6,6),(9,18,6,6),(10,20,5,8)])
def test_memory_progression(stars, size, cols, hints):
    g = MemoryMaster(stars=stars, seed=1)
    assert len(g.board) == size and g.cols == cols and len(g.hints) == hints
    assert len(g.known) == hints
    assert sum(c is not None for c in g.public_state()['cards']) == hints
    assert all(g.board.count(s) == 2 for s in set(g.board))


def test_fifth_mistake_no_duplicate_penalty_and_notes():
    g = MemoryMaster(stars=3, seed=7)
    a, b = next((a,b) for a in range(16) for b in range(16) if g.board[a] != g.board[b])
    for i in range(5):
        g.choose(a)
        assert g.mistakes == i
        with pytest.raises(ValueError):
            g.choose(a)
        g.choose(b)
    assert g.status == 'failed' and g.stars == 2 and g.attempts == 5
    assert g.known[str(a)] == g.board[a]
    assert g.public_state()['cards'][a] == g.board[a]
    with pytest.raises(ValueError):
        g.choose(a)
    g.next_board()
    assert g.mistakes == 0 and g.score == 0


def test_memory_clear_and_deterministic_next_board():
    g = MemoryMaster(stars=4, seed=11)
    for symbol in set(g.board):
        a,b = [i for i,v in enumerate(g.board) if v == symbol]
        g.choose(a)
        g.choose(b)
    assert g.stars == 5 and g.score == 16 and g.attempts == 8 and g.status == 'cleared'
    restored = MemoryMaster.from_dict(json.loads(json.dumps(g.to_dict())))
    g.next_board()
    restored.next_board()
    assert g.to_dict() == restored.to_dict() and len(g.board) == 18
    g.finish()
    with pytest.raises(ValueError):
        g.next_board()


def test_endless_adjacency_and_survivor_order():
    g = EndlessPairs(seed=2)
    assert g.adjacent(0,6) and g.adjacent(0,5) and g.adjacent(0,1)
    assert not g.adjacent(0,0) and not g.adjacent(4,5) and not g.adjacent(0,2)
    g.board[0] = g.board[6] = 'star'
    before = list(g.board)
    g.choose(0)
    g.choose(0)
    assert g.selected == [] and g.score == 0
    g.choose(0)
    g.choose(6)
    assert g.score == 2 and g.board[:18] == [x for i,x in enumerate(before) if i not in (0,6)]


def test_endless_resume_across_refill_and_finalization():
    g = EndlessPairs(seed=10)
    for _ in range(35):
        if g.finished:
            break
        restored = EndlessPairs.from_dict(json.loads(json.dumps(g.to_dict())))
        a,b = g.moves()[0]
        for game in (g, restored):
            game.choose(a)
            game.choose(b)
        assert g.to_dict() == restored.to_dict()
    g.finish()
    saved = g.to_dict()
    g.finish('stuck')
    assert g.to_dict() == saved
    with pytest.raises(ValueError):
        g.choose(1)


def test_natural_stuck_and_no_future_draws_in_projection():
    g = EndlessPairs(seed=5)
    g.board = [str(i) for i in range(20)]
    g.check_stuck()
    assert g.finished and g.reason == 'stuck'
    assert 'deck' not in g.public_state() and 'rng_state' not in g.public_state()
    m = MemoryMaster(seed=6)
    assert 'board' not in m.public_state() and 'rng_state' not in m.public_state()

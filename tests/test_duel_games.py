"""Whole-game integration through the production SQLite transaction boundary."""
import json
import random

import pytest

from casinogames.casino_war import CasinoWar
from casinogames.cuttle import Cuttle
from casinogames.duel_session import DuelService
from casinogames.pazaak import Pazaak
from casinogames.platoon import Platoon
from casinogames.red7 import Red7
from casinogames.scopa import Scopa
from casinogames.session_store import SessionStore
from casinogames.triple_triad import TripleTriad

ENGINES = {'casino_war': CasinoWar, 'cuttle': Cuttle, 'pazaak': Pazaak,
           'platoon': Platoon, 'red7': Red7, 'scopa': Scopa,
           'triple_triad': TripleTriad}
OWNER = 12345


def canonical(value):
    return json.loads(json.dumps(value))


def choose(game, randomizer):
    """Use supported controls, with varied human choices for board/capture games."""
    legal = game.legal_actions(game.turn)
    assert legal and all(len(a['label']) <= 100 for a in legal)
    assert len({a['id'] for a in legal}) == len(legal)
    if isinstance(game, (Cuttle, Pazaak)):
        # Includes response phases, deck confirmation, and next-set acknowledgement.
        return game.bot_action()
    if isinstance(game, Platoon) and game.phase == 'formation':
        return game.bot_action()
    choices = [a for a in legal if a['id'] != 'concede'] or legal
    return randomizer.choice(choices)['id']


def drain_luigi(game):
    for _ in range(128):
        if game.finished or game.turn != 0:
            return
        action = game.bot_action()
        assert action in {a['id'] for a in game.legal_actions(0)}
        game.act(0, action)
    pytest.fail('Luigi failed to return control within the service action limit')


def assert_safe_projection(kind, projection, viewer):
    assert not {'deck', 'rng', 'rng_state', 'draws', 'game', 'trace'} & projection.keys()
    if kind in {'pazaak', 'platoon', 'red7', 'scopa'}:
        for player in projection['players']:
            if player != viewer:
                assert all(card is None for card in projection['hands'][str(player)])
    if kind == 'pazaak':
        assert set(projection['side_decks']) <= ({str(viewer)} if viewer is not None else set())
    if kind == 'platoon':
        if viewer is None:
            assert projection['assignments'] is None
        for player, formations in projection['formations'].items():
            if player != str(viewer):
                for formation in formations:
                    if not formation['spent']:
                        assert all(c is None for c in formation['cards'])


def check_views(service, saved):
    for viewer in (None, OWNER):
        assert_safe_projection(saved['kind'], service.projection(saved, viewer), viewer)
        for frame in service.frames(saved, viewer):
            assert_safe_projection(saved['kind'], frame, viewer)
    with pytest.raises(PermissionError):
        service.projection(saved, 99999)
    with pytest.raises(PermissionError):
        service.frames(saved, 99999)
    # All returned projections are disposable; editing them cannot corrupt the save.
    before = service.store.get(saved['id'])
    own = service.projection(saved, OWNER)
    own['hands'].clear()
    assert service.store.get(saved['id']) == before


@pytest.mark.parametrize('kind', ENGINES)
@pytest.mark.parametrize('seed', range(5))
def test_complete_luigi_game_survives_restart_each_move_and_records_once(tmp_path, kind, seed):
    path = tmp_path / 'practice.db'
    service = DuelService(SessionStore(path), ENGINES)
    saved = service.start(7, OWNER, kind, seed=seed)
    uninterrupted = ENGINES[kind](players=(OWNER, 0), seed=seed)
    drain_luigi(uninterrupted)
    randomizer = random.Random(seed + 300)
    for moves in range(300):
        assert canonical(service.engine(saved).to_dict()) == canonical(uninterrupted.to_dict())
        check_views(service, saved)
        if saved['status'] == 'finished':
            break
        assert saved['status'] == 'active'
        assert service.engine(saved).turn == OWNER
        action = choose(uninterrupted, randomizer)
        assert action in {a['id'] for a in service.actions(saved, OWNER)}
        previous = saved
        uninterrupted.act(OWNER, action)
        drain_luigi(uninterrupted)
        saved, applied = service.change(saved['id'], saved['revision'], OWNER,
                                        'play', guild=7, choice=action)
        assert applied
        # A retry of the original button cannot redraw, rerun a bot, or score twice.
        duplicate, applied = service.change(previous['id'], previous['revision'], OWNER,
                                            'play', guild=7, choice=action)
        assert not applied and canonical(duplicate) == canonical(saved)
        service = DuelService(SessionStore(path), ENGINES)
        saved = service.get(saved['id'], 7, actor=OWNER)
    else:
        pytest.fail(f'{kind} seed {seed} did not finish in 300 human decisions')
    assert uninterrupted.finished
    assert service.projection(saved)['result'] == uninterrupted.result
    records = service.store.records(7, OWNER, kind)
    assert len(records) == 1 and records[0]['reason'] == 'completed'
    assert records[0]['score'] == int(uninterrupted.result['winner'] == OWNER)
    assert service.actions(saved, OWNER) == []


@pytest.mark.parametrize('kind', [k for k in ENGINES if k != 'casino_war'])
def test_invited_humans_finish_same_game_without_automatic_bot_moves(tmp_path, kind):
    service = DuelService(SessionStore(tmp_path / 'human.db'), ENGINES)
    saved = service.start(7, OWNER, kind, opponent=54321, seed=42)
    assert saved['state']['game'] is None
    assert service.actions(saved, OWNER) == []
    with pytest.raises(ValueError):
        service.change(saved['id'], saved['revision'], OWNER, 'accept', guild=7)
    saved, applied = service.change(saved['id'], saved['revision'], 54321, 'accept', guild=7)
    assert applied
    randomizer = random.Random(99)
    for _ in range(500):
        game = service.engine(saved)
        if game.finished:
            break
        actor = game.turn
        action = choose(game, randomizer)
        before = service.store.get(saved['id'])
        with pytest.raises(ValueError):
            service.change(saved['id'], saved['revision'], actor, 'play', guild=7, choice='forged:action')
        assert service.store.get(saved['id']) == before
        saved, applied = service.change(saved['id'], saved['revision'], actor, 'play', guild=7, choice=action)
        assert applied
        check_views(service, saved)
    else:
        pytest.fail(f'{kind} human match failed to finish')
    assert saved['status'] == 'finished'
    assert service.projection(saved)['result']['winner'] in (OWNER, 54321, None)
    assert len(service.store.records(7, OWNER, kind)) == 1


@pytest.mark.parametrize('kind', ENGINES)
def test_private_initial_deal_and_pause_resume_are_lossless(tmp_path, kind):
    service = DuelService(SessionStore(tmp_path / 'pause.db'), ENGINES)
    # Find a live War tie naturally; other modes always have human controls.
    for seed in range(200):
        saved = service.start(7, OWNER, kind, seed=seed)
        if saved['status'] != 'finished':
            break
    else:
        pytest.fail('No playable initial deal')
    check_views(service, saved)
    public = service.projection(saved)
    if kind in {'cuttle', 'pazaak', 'platoon', 'red7', 'scopa'}:
        assert all(c is None for cards in public['hands'].values() for c in cards)
    before = canonical(service.engine(saved).to_dict())
    paused, _ = service.change(saved['id'], saved['revision'], OWNER, 'pause', guild=7)
    assert paused['status'] == 'paused' and service.actions(paused, OWNER) == []
    resumed, _ = service.change(paused['id'], paused['revision'], OWNER, 'resume', guild=7)
    assert resumed['status'] == 'active'
    assert canonical(service.engine(resumed).to_dict()) == before


@pytest.mark.parametrize('choice', ['war', 'surrender'])
def test_casino_war_tie_decision_is_saved_and_settled_once(tmp_path, choice):
    seed = next(s for s in range(200) if not CasinoWar((OWNER, 0), seed=s).finished)
    service = DuelService(SessionStore(tmp_path / 'war-tie.db'), ENGINES)
    saved = service.start(7, OWNER, 'casino_war', seed=seed)
    expected = CasinoWar((OWNER, 0), seed=seed)
    expected.act(OWNER, choice)
    final, applied = service.change(saved['id'], saved['revision'], OWNER, 'play', guild=7, choice=choice)
    assert applied and final['status'] == 'finished'
    assert service.projection(final)['result'] == expected.result
    result = expected.result
    assert result['gross'] - result['committed'] == result['net']
    assert result['committed'] == (40 if choice == 'war' else 20)
    retry, applied = service.change(saved['id'], saved['revision'], OWNER, 'play', guild=7, choice=choice)
    assert not applied and retry['state'] == canonical(final['state'])
    assert len(service.store.records(7, OWNER, 'casino_war')) == 1

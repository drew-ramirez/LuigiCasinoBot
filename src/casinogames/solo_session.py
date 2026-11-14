"""Rules for persisted solo challenge transitions and record finalization."""
from casinogames.challenges import MemoryMaster, EndlessPairs
from casinogames.fortune_tower import FortuneTower

ENGINES = {'memory_master': MemoryMaster, 'pairagone_endless': EndlessPairs,
           'fortune_tower': FortuneTower}


def engine_for(snapshot):
    return ENGINES[snapshot['kind']].from_dict(snapshot['state']['game'])


def finalize_solo(snapshot, game=None):
    game = game or engine_for(snapshot)
    if not game.finished:
        return
    snapshot['status'] = 'finished'
    if snapshot['kind'] == 'fortune_tower':
        score, reason = game.result['score'], game.result['outcome']
    else:
        score, reason = game.score, getattr(game, 'reason', 'voluntary')
    snapshot['record'] = {'score': score, 'reason': reason}


def update_solo(snapshot, action, value=None):
    """Apply a transition within the session store transaction."""
    game = engine_for(snapshot)
    if snapshot['status'] == 'paused' and action not in ('resume', 'finish'):
        raise ValueError('Resume this saved run before playing.')
    if action == 'pause':
        snapshot['status'] = 'paused'
    elif action == 'resume':
        snapshot['status'] = 'active'
    elif action == 'choose':
        game.choose(value)
    elif action == 'next':
        game.next_board()
    elif action == 'finish':
        game.finish()
    elif action == 'continue':
        game.deal_next()
    elif action in ('bank', 'timeout') and snapshot['kind'] == 'fortune_tower':
        game.bank()
    else:
        raise ValueError('That action is not available.')
    snapshot['state']['game'] = game.to_dict()
    finalize_solo(snapshot, game)

"""Saved two-seat practice tables, reusing the existing transaction boundary."""
from copy import deepcopy


class DuelService:
    BOT_LIMIT = 128

    def __init__(self, store, engines):
        self.store, self.engines = store, engines

    def engine(self, snapshot):
        data = snapshot['state']['game']
        return self.engines[snapshot['kind']].from_dict(data) if data is not None else None

    def get(self, table_id, guild, *, actor=None):
        saved = self.store.get(table_id)
        if saved is None or saved['kind'] not in self.engines or saved['guild'] != str(guild):
            raise ValueError('No matching practice table exists in this server.')
        if actor is not None and actor not in saved['state']['players']:
            raise PermissionError('This is another player\'s table.')
        return saved

    def start(self, guild, owner, kind, opponent=0, *, seed=None):
        if kind not in self.engines or type(owner) is not int or owner <= 0:
            raise ValueError('Unknown game or player.')
        if type(opponent) is not int or opponent < 0 or opponent == owner:
            raise ValueError('Choose another human or Luigi.')
        if kind == 'casino_war' and opponent:
            raise ValueError('Casino War is a solo dealer table.')
        state = {'players': [owner, opponent], 'ready': [owner], 'game': None,
                 'phase': 'invited' if opponent else 'playing', 'seed': seed,
                 'trace': [], 'result': None, 'message_id': None, 'channel_id': None}
        # Store creation is itself atomic: concurrent commands reuse the same run.
        saved = self.store.create(guild, owner, kind, state)
        if saved['state']['game'] is None and not saved['state']['players'][1]:
            saved, _ = self.store.apply(saved['id'], saved['revision'], owner, self._deal)
        return saved

    def _deal(self, saved):
        state = saved['state']
        game = self.engines[saved['kind']](players=tuple(state['players']), seed=state.pop('seed', None))
        state['phase'] = 'playing'
        state['trace'] = [game.to_dict()]
        self._bots(saved, game)
        self._save_game(saved, game)

    def _bots(self, saved, game):
        for _ in range(self.BOT_LIMIT):
            if game.finished or game.turn != 0:
                return
            game.act(0, game.bot_action())
            # Keep the last few complete actions. Every projection is filtered later.
            saved['state']['trace'].append(game.to_dict())
            saved['state']['trace'] = saved['state']['trace'][-16:]
        if not game.finished and game.turn == 0:
            saved['status'] = 'paused'

    def _save_game(self, saved, game):
        saved['state']['game'] = game.to_dict()
        if game.finished:
            saved['state']['result'] = deepcopy(game.result)
            self._finish(saved, 'completed')

    def _finish(self, saved, reason):
        state = saved['state']
        saved['status'], state['phase'] = 'finished', 'finished'
        if state['game'] is not None:
            result = state.get('result') or {}
            saved['record'] = {'score': int(result.get('winner') == int(saved['owner'])), 'reason': reason}

    def change(self, table_id, revision, actor, action, *, guild, choice=None):
        self.get(table_id, guild, actor=actor)
        def update(saved):
            state = saved['state']
            if action == 'accept':
                if state['phase'] != 'invited' or actor == int(saved['owner']):
                    raise ValueError('Only the invited opponent can accept this lobby.')
                state['ready'].append(actor)
                self._deal(saved)
                return
            if action in ('decline', 'cancel'):
                if state['phase'] != 'invited':
                    raise ValueError('This table has already been dealt.')
                self._finish(saved, 'cancelled')
                return
            if action == 'pause':
                saved['status'] = 'paused'
                return
            if action == 'resume':
                saved['status'] = 'active'
                game = self.engine(saved)
                if game:
                    state['trace'] = [game.to_dict()]
                    self._bots(saved, game)
                    self._save_game(saved, game)
                return
            if action == 'concede':
                if state['game'] is None:
                    self._finish(saved, 'cancelled')
                else:
                    winner = next(p for p in state['players'] if p != actor)
                    state['result'] = {'winner': winner, 'reason': 'conceded', 'conceded': actor}
                    self._finish(saved, 'conceded')
                return
            if action != 'play' or saved['status'] != 'active' or state['phase'] != 'playing':
                raise ValueError('Resume this table before playing.')
            game = self.engine(saved)
            state['trace'] = [game.to_dict()]
            game.act(actor, choice)
            state['trace'].append(game.to_dict())
            self._bots(saved, game)
            self._save_game(saved, game)
        return self.store.apply(table_id, revision, actor, update,
                                authorize=lambda s, a: int(a) in s['state']['players'] and int(a) != 0)

    def projection(self, saved, viewer=None):
        game = self.engine(saved)
        if viewer is not None and viewer not in saved['state']['players']:
            raise PermissionError('Only seated players can inspect a private hand.')
        state = game.view(viewer) if game else {
            'kind': saved['kind'], 'players': list(saved['state']['players']), 'turn': None,
            'hands': {}, 'table': [], 'scores': {}, 'log': [], 'result': None,
        }
        state = deepcopy(state)
        state['viewer_id'] = viewer
        state['session_status'] = saved['status']
        state['phase'] = saved['state']['phase'] if game is None else state.get('phase', 'playing')
        if saved['status']=='finished':
            state['phase'], state['turn'] = 'finished', None
        if saved['state'].get('result'):
            state['result'] = deepcopy(saved['state']['result'])
        return state

    def actions(self, saved, actor):
        if actor == 0 or actor not in saved['state']['players'] or saved['status'] != 'active':
            return []
        game = self.engine(saved)
        return game.legal_actions(actor) if game and not game.finished else []

    def frames(self, saved, viewer=None):
        if viewer is not None and viewer not in saved['state']['players']:
            raise PermissionError('Only seated players can inspect a private hand.')
        cls = self.engines[saved['kind']]
        frames = [cls.from_dict(frame).view(viewer) for frame in saved['state']['trace']]
        for frame in frames:
            frame['viewer_id'] = viewer
        final = self.projection(saved, viewer)
        if frames:
            frames[-1] = final
        else:
            frames.append(final)
        return frames

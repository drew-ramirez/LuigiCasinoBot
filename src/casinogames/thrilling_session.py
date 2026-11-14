"""Transactional rules and safe projections for Thrilling Cards tables."""
from casinogames.thrilling_cards import ThrillingMatch

KIND = 'thrilling_cards'


def projection(snapshot, viewer=None):
    state = snapshot['state']
    if viewer is not None and viewer not in state['players']:
        raise PermissionError('Only seated players can inspect a private table.')
    if state.get('match'):
        match = ThrillingMatch.from_dict(state['match'])
        result = match.hand.view(viewer)
        result['standings'] = match.standings()
        result['hand_number'] = min(5, len(match.hands) + (match.hand not in match.hands))
    else:
        result = {'game': KIND, 'seats': [dict(player_id=p, card=None, committed=0,
                  folded=False, ready=p in state['ready']) for p in state['players']],
                  'pot': 0, 'target': 0, 'turn': None, 'result': None, 'actions': ()}
    result['phase'] = state['phase']
    return result


def clock_token(snapshot):
    if snapshot['status'] != 'active':
        return None
    if snapshot['state']['phase'] == 'lobby':
        return ('lobby',)
    if snapshot['state']['phase'] == 'playing':
        match = ThrillingMatch.from_dict(snapshot['state']['match'])
        if match.hand.result is None:
            return ('turn', len(match.hands), match.hand.turn)
    return None


class ThrillingSession:
    def __init__(self, store, boot_id):
        self.store, self.boot_id = store, boot_id

    def get(self, table_id, guild, actor=None):
        saved = self.store.get(table_id)
        if saved is None or saved['kind'] != KIND or saved['guild'] != str(guild):
            raise ValueError('No Thrilling Cards table with that ID exists in this server.')
        if actor is not None and actor not in saved['state']['players']:
            raise PermissionError('Only a seated player can resume this table. Use Join on its public lobby.')
        return saved

    def create(self, guild, owner, channel):
        state = {'phase': 'lobby', 'players': [owner], 'ready': [], 'match': None,
                 'boot': self.boot_id, 'channel_id': channel, 'message_id': None}
        return self.store.create(guild, owner, KIND, state)

    def resume(self, snapshot, actor):
        if snapshot['status'] == 'finished' or (snapshot['state']['boot'] == self.boot_id and snapshot['status'] != 'paused'):
            return snapshot
        def update(saved):
            saved['state']['boot'] = self.boot_id
            saved['status'] = 'active'
        return self.store.apply(snapshot['id'], snapshot['revision'], actor, update,
                                authorize=lambda s, a: int(a) in s['state']['players'])[0]

    def change(self, table_id, revision, actor, action, amount=None):
        return self.store.apply(table_id, revision, actor,
            lambda saved: self._change(saved, actor, action, amount),
            authorize=lambda saved, a: (action == 'join' and saved['state']['phase'] == 'lobby')
                or int(a) in saved['state']['players'])

    def bind(self, snapshot, channel, message):
        def update(saved):
            saved['state']['channel_id'], saved['state']['message_id'] = channel, message
        return self.store.apply(snapshot['id'], snapshot['revision'], snapshot['owner'], update)[0]

    def pause(self, snapshot):
        def update(saved):
            saved['status'] = 'paused'
        return self.store.apply(snapshot['id'], snapshot['revision'], snapshot['owner'], update)

    def expire(self, snapshot, token):
        if snapshot['state']['boot'] != self.boot_id or clock_token(snapshot) != token:
            return snapshot, False
        def update(saved):
            if token[0] == 'lobby':
                saved['state']['phase'], saved['status'] = 'expired', 'finished'
            else:
                match = ThrillingMatch.from_dict(saved['state']['match'])
                match.hand.fold(match.hand.turn)
                self._save_match(saved, match)
        return self.store.apply(snapshot['id'], snapshot['revision'], snapshot['owner'], update)

    def _change(self, saved, actor, action, amount=None):
        state = saved['state']
        if state['boot'] != self.boot_id or saved['status'] == 'paused':
            raise ValueError('This table is paused. Use /casino_thrilling with its ID to resume.')
        if action in ('join', 'ready', 'cancel', 'start'):
            self._lobby_change(saved, actor, action)
        elif action == 'leave':
            self._leave(saved, actor)
        else:
            self._play(saved, actor, action, amount)

    def _lobby_change(self, saved, actor, action):
        state = saved['state']
        owner = int(saved['owner'])
        if action == 'join':
            if state['phase'] != 'lobby' or actor in state['players'] or len(state['players']) >= 4:
                raise ValueError('Join requires an open lobby with a free seat.')
            state['players'].append(actor)
        elif action == 'ready':
            if state['phase'] != 'lobby' or actor not in state['players']:
                raise ValueError('Join this lobby before confirming readiness.')
            if actor in state['ready']:
                raise ValueError('You are already ready.')
            state['ready'].append(actor)
        elif action == 'cancel':
            if actor != owner or state['phase'] != 'lobby':
                raise ValueError('Only the owner can cancel an undealt lobby.')
            state['phase'], saved['status'] = 'cancelled', 'finished'
        elif action == 'start':
            self._start(saved, actor)

    def _start(self, saved, actor):
        state = saved['state']
        owner = int(saved['owner'])
        if actor != owner or state['phase'] != 'lobby':
            raise ValueError('Only the owner can start this lobby.')
        if len(state['players']) < 2 or set(state['ready']) != set(state['players']):
            raise ValueError('Start needs 2–4 players, all ready for the 15-chip maximum.')
        match = ThrillingMatch(state['players'])
        match.next_hand()
        state['match'], state['phase'] = match.to_dict(), 'playing'

    def _leave(self, saved, actor):
        state = saved['state']
        owner = int(saved['owner'])
        if actor not in state['players']:
            raise ValueError('You are not seated at this table.')
        if state['phase'] == 'lobby':
            if actor == owner:
                raise ValueError('The owner can cancel this lobby instead.')
            state['players'].remove(actor)
            state['ready'] = [p for p in state['ready'] if p != actor]
        else:
            match = ThrillingMatch.from_dict(state['match'])
            match.leave(actor)
            self._save_match(saved, match)

    def _play(self, saved, actor, action, amount):
        state = saved['state']
        if state['phase'] != 'playing' or actor not in state['players']:
            raise ValueError('You are not playing in this table.')
        match = ThrillingMatch.from_dict(state['match'])
        if action == 'next':
            host = next((p for p in match.players if p not in match.departed), None)
            if actor != host:
                raise ValueError('Only the first remaining seat can deal the next hand.')
            match.next_hand()
        else:
            match.hand.act(actor, action, amount)
        self._save_match(saved, match)

    @staticmethod
    def _save_match(saved, match):
        if match.hand.result is not None:
            match.settle_hand()
        if match.finished:
            saved['status'] = 'finished'
            saved['state']['phase'] = 'finished'
        saved['state']['match'] = match.to_dict()

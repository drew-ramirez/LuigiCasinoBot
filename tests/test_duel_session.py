from copy import deepcopy
import pytest
from casinogames.session_store import SessionStore
from casinogames.duel_session import DuelService


class SmallGame:
    def __init__(self, players, seed=None):
        self.players = list(players)
        self.turn = players[0]
        self.finished = False
        self.result = None
        self.moves = []
    def legal_actions(self, actor):
        return [{'id':'move','label':'Move'}] if actor == self.turn and not self.finished else []
    def act(self, actor, action):
        if action != 'move' or not self.legal_actions(actor):
            raise ValueError('illegal')
        self.moves.append(actor)
        self.turn = self.players[1] if actor == self.players[0] else self.players[0]
        if len(self.moves) == 4:
            self.finished = True
            self.result = {'winner': self.players[0]}
    def bot_action(self):
        return 'move'
    def view(self, viewer=None):
        return {'kind':'small', 'players':list(self.players), 'turn':self.turn, 'phase':'playing',
                'hands':{str(p):['AS' if viewer == p else None] for p in self.players},
                'table':[], 'scores':{}, 'log':[], 'result':deepcopy(self.result)}
    def to_dict(self):
        return deepcopy(self.__dict__)
    @classmethod
    def from_dict(cls, data):
        obj=cls.__new__(cls);obj.__dict__.update(deepcopy(data));return obj


@pytest.fixture
def service(tmp_path):
    return DuelService(SessionStore(tmp_path/'duels.db'), {'small':SmallGame})


def test_solo_saved_bot_reply_duplicate_and_exactly_one_record(service):
    first=service.start(1,10,'small')
    assert service.start(1,10,'small') == first
    saved,applied=service.change(first['id'],first['revision'],10,'play',guild=1,choice='move')
    assert applied and saved['state']['game']['moves']==[10,0]
    retry,applied=service.change(first['id'],first['revision'],10,'play',guild=1,choice='move')
    assert not applied and retry==saved
    end,_=service.change(saved['id'],saved['revision'],10,'play',guild=1,choice='move')
    assert end['status']=='finished'
    assert len(service.store.records(1,10,'small'))==1
    assert service.store.get(end['id'])==end


def test_invitation_has_no_deal_before_opponent_consent(service):
    first=service.start(1,10,'small',20)
    assert first['state']['game'] is None
    with pytest.raises(ValueError):
        service.change(first['id'],0,10,'accept',guild=1)
    ready,_=service.change(first['id'],0,20,'accept',guild=1)
    assert ready['state']['game']['players']==[10,20]
    with pytest.raises(ValueError):
        service.change(ready['id'],ready['revision'],20,'play',guild=1,choice='move')
    assert service.store.get(first['id'])==ready


def test_auth_pause_resume_and_concession(service):
    s=service.start(1,10,'small',20)
    for guild,actor in [(2,10),(1,30)]:
        with pytest.raises((ValueError,PermissionError)):
            service.change(s['id'],0,actor,'accept',guild=guild)
    s,_=service.change(s['id'],0,20,'accept',guild=1)
    s,_=service.change(s['id'],s['revision'],10,'pause',guild=1)
    with pytest.raises(ValueError):
        service.change(s['id'],s['revision'],10,'play',guild=1,choice='move')
    before=s['state']['game']
    s,_=service.change(s['id'],s['revision'],20,'resume',guild=1)
    assert s['state']['game']==before
    s,_=service.change(s['id'],s['revision'],20,'concede',guild=1)
    assert service.projection(s)['result']['winner']==10
    assert s['status']=='finished'


def test_private_hands_and_trace_filtered_for_each_viewer(service):
    s=service.start(1,10,'small')
    s,_=service.change(s['id'],s['revision'],10,'play',guild=1,choice='move')
    assert service.projection(s)['hands']=={'10':[None],'0':[None]}
    assert service.projection(s,10)['hands']=={'10':['AS'],'0':[None]}
    assert all(frame['hands']['0']==[None] for frame in service.frames(s,10))
    with pytest.raises(PermissionError):service.frames(s,999)
    assert service.actions(s,999)==[]

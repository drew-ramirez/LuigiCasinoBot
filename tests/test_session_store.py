import pytest
from casinogames.session_store import SessionStore


def test_restart_duplicate_and_finalization(tmp_path):
    path = tmp_path / 'sessions.sqlite3'
    store = SessionStore(path)
    first = store.create(1, 2, 'endless', {'board': [1, 2], 'deck': [3, 4]})
    assert store.create(1, 2, 'endless', {'board': []}) == first
    def finish(s):
        s['state']['deck'].pop()
        s['status'] = 'finished'
        s['record'] = {'score': 2, 'reason': 'voluntary'}
    saved, applied = store.apply(first['id'], 0, 2, finish)
    assert applied
    resumed = SessionStore(path)
    assert resumed.get(first['id']) == saved
    assert resumed.apply(first['id'], 0, 2, finish) == (saved, False)
    assert len(resumed.records(1, 2, 'endless')) == 1
    assert resumed.records(9, 2, 'endless') == []
    assert resumed.active(1, 2, 'endless') is None


def test_authorization_stale_and_rollback(tmp_path):
    store = SessionStore(tmp_path / 's.db')
    s = store.create(1, 2, 'memory', {'cards': [1, 2]})
    with pytest.raises(PermissionError):
        store.apply(s['id'], 0, 3, lambda s: None)
    def fail(s):
        s['state']['cards'].pop()
        raise ValueError('bad action')
    with pytest.raises(ValueError):
        store.apply(s['id'], 0, 2, fail)
    assert store.get(s['id']) == s
    saved, applied = store.apply(s['id'], 0, 2, lambda s: s.update(status='paused'))
    assert applied
    assert store.apply(s['id'], 0, 2, fail) == (saved, False)


def test_two_connections_accept_only_one_revision(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / 's.db'
    a, b = SessionStore(path), SessionStore(path)
    s = a.create(1, 2, 'memory', {'n': 0})
    def increment(store):
        return store.apply(s['id'], 0, 2, lambda s: s['state'].update(n=s['state']['n'] + 1))[1]
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(increment, [a, b])) == [False, True]
    assert a.get(s['id'])['state']['n'] == 1

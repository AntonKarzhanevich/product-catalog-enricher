from napolnenie.query import build_web_query, shorten_group


def test_shorten_group():
    g = shorten_group('BGA чип и микросхема для ноутбуков')
    assert "BGA" in g
    assert "для" not in g.split()


def test_build_web_query():
    q = build_web_query("ALC3248", "BGA чип и микросхема для ноутбуков")
    assert q.startswith("ALC3248")
    assert "BGA" in q

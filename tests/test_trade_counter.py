from state.trade_counter import TradeCounter

def test_daily_trade_counter_atomic(tmp_path):
    path = tmp_path / "trade_counter.json"
    c = TradeCounter(path)

    data = c.load()
    assert c.get_today(data) == 0

    c.increment_today(data, 1)
    c.persist_atomic(data)

    data2 = c.load()
    assert c.get_today(data2) == 1

    # Check JSON content manually
    import json
    content = json.loads(path.read_text())
    assert content[c.today_key()] == 1

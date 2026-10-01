from xau_detective.timeframes import Timeframe, TimeframeMap, expected_interval


def test_timeframe_map_matches_strategy_layers():
    mapping = TimeframeMap()
    assert mapping.values() == (
        Timeframe.D1,
        Timeframe.H4,
        Timeframe.H1,
        Timeframe.M15,
        Timeframe.M5,
    )


def test_expected_interval_covers_all_strategy_layers():
    assert expected_interval(Timeframe.D1).total_seconds() == 86400
    assert expected_interval(Timeframe.H4).total_seconds() == 14400
    assert expected_interval(Timeframe.M15).total_seconds() == 900

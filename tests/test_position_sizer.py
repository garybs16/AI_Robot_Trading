from risk.position_sizer import PositionSizer


def test_risk_based_position_is_capped_by_max_position_size():
    sizer = PositionSizer(max_position_fraction=0.2, default_risk_fraction=0.01)
    qty = sizer.risk_based(equity=100_000, entry_price=100, stop_price=95)
    assert qty == 200


def test_kelly_fraction_is_aggressively_capped():
    sizer = PositionSizer(kelly_cap=0.05)
    assert sizer.kelly_fraction(win_rate=0.9, win_loss_ratio=3.0) == 0.05


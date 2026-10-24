import pytest

from napolnenie.normalize import (
    is_verified,
    normalize_g_head,
    split_series_head,
    strip_1c_tail,
)


def test_strip_1c_tail():
    assert strip_1c_tail("ALC3248, 00087376") == "ALC3248"
    assert split_series_head("88E8042 88E8042 02, 00087568") == "88E8042 88E8042 02"


def test_b_join_3tok():
    q, fb, rule = normalize_g_head("NB669 AEVD NB669AEVD")
    assert q == "NB669AEVD"
    assert fb == ["NB669"]
    assert rule == "B_join_3tok"


def test_c_join_2tok():
    q, fb, rule = normalize_g_head("SY8033 bdbc")
    assert q == "SY8033BDBC"
    assert fb == ["SY8033"]
    assert rule == "C_join_2tok"


def test_ltc_like():
    q, fb, rule = normalize_g_head("LTC2978   Ltc2978up")
    assert q == "LTC2978UP"
    assert fb == ["LTC2978"]
    assert rule == "LTC_like"


def test_dash_2tok():
    q, fb, rule = normalize_g_head("NСT6776D  F")  # кириллическая С
    assert q == "NCT6776D-F"
    assert rule == "dash_2tok"


def test_d_cyr_noise():
    q, _, rule = normalize_g_head("LM27402S Шим контроллер")
    assert q == "LM27402S"
    assert rule == "D_cyr_noise"


def test_verified():
    assert is_verified("88E8042", "88E8042 88E8042 02")
    assert is_verified("ALC3248", "ALC3248")
    assert not is_verified("347 CU236", "SMB347")

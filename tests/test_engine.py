# -*- coding: utf-8 -*-
"""回歸測試：720 課的四課與三傳。
fixtures_720.json 已與 wlhyl/dalurenpython 逐課比對（三傳 720/720 一致），
四課、天將亦與 kinliuren、wlhyl/dalurenpython 比對一致。
執行：python3 -m pytest tests  或  python3 tests/test_engine.py
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "da-liu-ren", "scripts"))
from liuren import build_chart, calendar_info  # noqa: E402
from datetime import datetime  # noqa: E402


def test_720():
    fx = json.load(open(os.path.join(HERE, "fixtures_720.json"), encoding="utf-8"))
    bad = []
    for key, exp in fx.items():
        d, gen, hour = key.split("|")
        c = build_chart(d, hour, gen)
        got = {"四課": [k.upper + k.lower for k in c.sike], "三傳": "".join(c.sanchuan), "九宗門": c.method}
        if got != exp:
            bad.append((key, exp, got))
    assert not bad, bad[:5]


def test_calendar():
    cal = calendar_info(datetime(2026, 10, 27, 13, 44))
    assert cal["day_gz"] == "甲戌" and cal["hour_zhi"] == "未"
    assert cal["zhongqi"] == "霜降" and cal["general"] == "卯"
    # 霜降前一刻仍為辰將（秋分後）
    cal2 = calendar_info(datetime(2026, 10, 23, 17, 0))
    assert cal2["general"] == "辰"


def test_sample_chart():
    c = build_chart("甲戌", "未", "卯")
    assert [k.upper for k in c.sike] == ["戌", "午", "午", "寅"]
    assert c.sanchuan == ["戌", "午", "寅"] and c.ke_name == "重審"
    assert c.guiren == "丑" and c.guiren_direction == "逆"


if __name__ == "__main__":
    test_720(); test_calendar(); test_sample_chart()
    print("all tests passed")

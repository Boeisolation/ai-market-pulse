from __future__ import annotations

import pytest

from ai_market_pulse import market_data

# normalize_cn_code consults the East Money fund directory for every bare
# 6-digit code, so tests must never hit the network: pin a tiny directory by
# default. Tests that need richer entries overwrite _FUND_DIRECTORY themselves.
_TEST_DIRECTORY = {
    "005051": ("摩根标普港股通低波红利指数A", "指数型-股票"),
    "539002": ("建信新兴市场优选混合(QDII)A", "QDII"),
    "000001": ("华夏成长混合", "混合型-偏股"),
    "005827": ("易方达蓝筹精选混合", "混合型-偏股"),
    "161725": ("招商中证白酒指数(LOF)A", "指数型-股票"),
}


@pytest.fixture(autouse=True)
def _offline_fund_directory(monkeypatch):
    monkeypatch.setattr(market_data, "_FUND_DIRECTORY", dict(_TEST_DIRECTORY))

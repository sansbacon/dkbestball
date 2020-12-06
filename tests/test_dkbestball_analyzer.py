# test_dkbestball_analyzer.py
# SET DK_BESTBALL_USERNAME env variable if not exist

import os

import pandas as pd
import pytest

from dkbestball import Analyzer


@pytest.fixture
def a(test_directory):
    return Analyzer(username=os.getenv('DK_BESTBALL_USERNAME'),
                    datadir=test_directory)


def test_init(test_directory):
    obj = Analyzer(username=os.getenv('DK_BESTBALL_USERNAME'),
                   datadir=test_directory)
    assert obj
    assert obj.username is not None
    assert obj.datadir.is_dir()


def test_mydata_path(a):
    assert a.mydata_path.is_file()


def test_contest_type(a):
    """Tests contest_type"""
    assert a.contest_type('Big Tournament') == 'Tournament'
    assert a.contest_type('zzzaAZ') == 'Unknown'


def test_financial_summary(a, tprint):
    """Tests financial summary"""
    df = a.financial_summary()
    assert set(df.columns) == set(a.FINANCIAL_COLUMNS)


def test_my_rosters(a):
    df = a.myrosters()
    assert set(df.columns) == set(a.ROSTER_COLUMNS)


def test_ownership(a, tprint):
    """Tests ownership"""
    df = a.ownership()
    assert set(df.columns) == set(a.OWNERSHIP_COLUMNS)

    # pass dataframe
    r = a.myrosters().query("position == 'QB'")
    df = a.ownership(df=r)
    assert set(df.columns) == set(a.OWNERSHIP_COLUMNS)


def test_positional_ownership(a, tprint):
    """Tests positional ownership"""
    o = a.positional_ownership(pos='QB')
    assert set(o.columns) == set(a.OWNERSHIP_COLUMNS)


def test_standings(a, tprint):
    """Tests standings"""
    df = a.standings()
    assert set(df.columns) == set(a.STANDINGS_COLUMNS)


def test_standings_summary(a, tprint):
    """Tests standings summary"""
    df = a.standings_summary('t')
    assert set(df.columns) == {'place', 'n_teams', 'pct'}


def test_tournament_contests(a, tprint):
    """Test tournament_contests"""
    tc = a.tournament_contests()
    assert isinstance(tc, pd.core.api.Series)
    assert tc.dtype == 'object'


def test_tournament_entries(a, tprint):
    """Test tournament_entries"""
    te = a.tournament_entries()
    assert isinstance(te, pd.core.api.Series)
    assert te.dtype == 'object'


def test_tournament_rosters(a, tprint):
    """Test tournament_rosters"""
    df = a.tournament_rosters()
    assert set(df.columns) == set(a.ROSTER_COLUMNS)


def test_tournament_ownership(a, tprint):
    """Test tournament_ownership"""
    df = a.tournament_ownership()
    assert set(df.columns) == set(a.OWNERSHIP_COLUMNS)

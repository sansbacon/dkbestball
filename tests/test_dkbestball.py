# -*- coding: utf-8 -*-
# test_dkbestball.py
# SET DK_BESTBALL_USERNAME env variable if not exist

import json
import os
import random

import pandas as pd
import pytest

from dkbestball import Parser


@pytest.fixture
def contestfile(test_directory):
    return test_directory / 'contest.json'


@pytest.fixture
def datadir(root_directory):
    return root_directory / 'dkbestball' / 'data'


@pytest.fixture
def dfscontest():
    return json.loads(
        '''{"ContestId":93852148,"MegaContestId":null,"MegaContestRoundNumber":null,"ContestName":"LOL 2020 by abitbedlam #5","BuyInAmount":0.0,"Sport":1,"SportName":"NFL","TotalPrizePool":0.0,"PositionsPaid":0,"PaidPositionThresholdPoints":0.0,"ContestStartDateEdt":"2020-10-11T13:00:00","ContestStartDate":"2020-10-11T17:00:00Z","ContestEndDateEdt":"2020-10-11T16:25:00","ContestEndDate":"2020-10-11T20:25:00Z","ContestStatus":1,"ContestType":{"ContestTypeId":21,"SportId":1,"Sport":"NFL","RequiresTeam":true,"SalaryCap":50000,"DefaultTimeRemaining":540.0,"DefaultPlayerTimeRemaining":60,"AllowLateSwap":true,"AutomaticPayouts":false,"IsActive":true},"CreatorUserId":null,"NumberOfEntrants":5,"MaxNumberPlayers":14,"SalariesAvailable":true,"DraftGroupId":40304,"GameTypeId":1,"GameType":{"gameTypeId":1,"name":"Classic","description":"Create a 9-player lineup while staying under the $50,000 salary cap","tag":"","sportId":1,"draftType":"SalaryCap","gameStyle":{"gameStyleId":1,"sportId":1,"sortOrder":1,"name":"Classic","abbreviation":"CLA","description":"Create a 9-player lineup while staying under the $50,000 salary cap","isEnabled":true}},"IsDirectChallenge":false,"IsGuaranteed":true,"IsFreeroll":false,"TopPayout":0.0,"MaxNumberEntries":1,"UserContestId":2271705961,"LineupId":2668129485,"ResultsRank":0,"TimeRemainingOpp":0,"TotalPointsOpp":0.0,"UsernameOpp":null,"TeamName":"","PlayerPoints":0.0,"TimeRemaining":0,"UserEntries":1,"TokensWon":0.0,"TicketWinnings":0.0,"PrizesWon":0,"AbandonedDirectChallenge":false,"DefaultTimeRemaining":540,"LateDraftEligible":false}'''
    )


@pytest.fixture
def leaderboardfile(test_directory):
    return test_directory / 'contest_leaderboard.json'


@pytest.fixture
def mycontestfile(test_directory):
    return test_directory / 'mycontests.html'


@pytest.fixture
def p():
    return Parser()


@pytest.fixture
def player_name():
    players = ('Alvin Kamara', 'Michael Thomas', 'Ezekiel Elliott')
    return random.choice(players)


@pytest.fixture
def rosterfile(test_directory):
    return test_directory / 'contest_roster.json'


@pytest.fixture
def username():
    try:
        return MY_USERNAME
    except NameError:
        return os.getenv('DK_BESTBALL_USERNAME')


def test_pctcol(p):
    """Tests pctcol"""
    v = .0512
    assert p._pctcol(v) == '5.12%'


def test_contest_type(p, dfscontest):
    """Tests _contest_type"""
    assert p._contest_type(dfscontest) == 'sit_and_go'


def test_draftablesfn(p):
    """Tests _draftablesfn"""
    id = 37604
    assert p._draftablesfn(id).is_file()


def test_to_dataframe(p):
    """Tests to_dataframe"""
    c = {'a': [1, 2, 3], 'b': [4, 5, 6]}
    df = p._to_dataframe(c)
    assert df.iloc[0, 0] == 1


def test_to_obj(p):
    """Tests to_obj"""
    pth = p._draftablesfn(37604)
    obj = p._to_obj(pth)
    assert isinstance(obj, dict)


def test_contest_details(p, contestfile):
    """Tests contest_roster"""
    c = p.contest_details(p._to_obj(contestfile))
    fields = {
        'ContestId', 'ContestName', 'BuyInAmount', 'MaxNumberPlayers',
        'DraftGroupId', 'GameTypeId', 'TopPayout', 'UserContestId',
        'ResultsRank', 'TotalPointsOpp', 'UsernameOpp', 'PlayerPoints',
        'ContestType', 'ClockType'
    }
    assert set(c.keys()) == fields


def test_contest_leaderboard(p, leaderboardfile):
    """Tests contest_leaderboard"""
    lb = p.contest_leaderboard(json.loads(leaderboardfile.read_text()))
    assert isinstance(lb, list)
    assert isinstance(random.choice(lb), dict)
    fields = {'UserName', 'UserKey', 'Rank', 'FantasyPoints', 'ContestKey'}
    for item in lb:
        assert fields == set(item.keys())


def test_contest_roster(p, rosterfile):
    """Tests contest_roster"""
    roster = p.contest_roster(json.loads(rosterfile.read_text()))
    assert isinstance(roster, list)
    assert isinstance(random.choice(roster), dict)


def test_filter_contests_by_size(p, mycontestfile):
    """Tests filter_contests_by_size"""
    contests = p.mycontests(mycontestfile)
    for size in (3, 6, 12):
        filtered = p.filter_contests_by_size(contests, size=size)
        contest = random.choice(filtered)
        assert f'{size}-Player' in contest['ContestName']


def test_is_bestball_contest(p, contestfile, dfscontest):
    """Tests is_bestball_contest"""
    contest = json.loads(contestfile.read_text())
    assert p.is_bestball_contest(contest)
    assert not p.is_bestball_contest(dfscontest)


def test_mycontests(p, mycontestfile, tprint):
    """Tests mycontests"""
    contests = p.mycontests(mycontestfile)
    assert isinstance(contests, list)
    assert isinstance(random.choice(contests), dict)
    tprint(set([item['ContestName'] for item in contests]))


def test_ownership(p, player_name, username):
    """Tests ownership"""
    # rosters is a list of lists
    rosterfiles = list(p.ROSTER_DIR.glob('*.json'))
    rosters = [
        p.contest_roster(p._to_obj(f)) for f in random.sample(rosterfiles, 3)
    ]
    rosterdf = p._to_dataframe(
        [item for sublist in rosters for item in sublist])
    df = p.ownership(rosterdf, username=username)
    assert not df.loc[player_name, :].empty


def test_player_pool(p, tprint):
    id = random.choice((37604, 37605))
    pool = p.player_pool(id=id)
    assert isinstance(pool, list)
    player = random.choice(pool)
    assert isinstance(player, dict)
    fields = {
        'draftableId', 'playerId', 'playerDkId', 'displayName', 'position',
        'teamAbbreviation'
    }
    assert fields == set(player.keys())


def test_player_pool_dict(p):
    id = random.choice((37604, 37605))
    playerd = p.player_pool_dict(id=id)
    assert isinstance(playerd, dict)
    key = random.choice(list(playerd.keys()))
    assert isinstance(key, int)
    player = playerd[key]
    assert isinstance(player, dict)
    fields = {
        'playerId', 'playerDkId', 'displayName', 'position', 'teamAbbreviation'
    }
    assert fields == set(player.keys())


def test_standings(p, datadir, username, tprint):
    """Tests standings"""
    # get random sampling of leaderboards
    leaderboards = []
    paths = random.sample(list(p.LEADERBOARD_DIR.glob('*.json')), 10)
    for pth in paths:
        leaderboards += p.contest_leaderboard(p._to_obj(pth))
    assert isinstance(leaderboards, list)

    # test standings df
    df = p.standings(leaderboards, username)
    fields = {'UserName', 'UserKey', 'Rank', 'FantasyPoints', 'MegaContestKey'}
    assert set(df.columns) == fields

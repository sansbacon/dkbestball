import json
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
    return json.loads('''{"ContestId":93852148,"MegaContestId":null,"MegaContestRoundNumber":null,"ContestName":"LOL 2020 by abitbedlam #5","BuyInAmount":0.0,"Sport":1,"SportName":"NFL","TotalPrizePool":0.0,"PositionsPaid":0,"PaidPositionThresholdPoints":0.0,"ContestStartDateEdt":"2020-10-11T13:00:00","ContestStartDate":"2020-10-11T17:00:00Z","ContestEndDateEdt":"2020-10-11T16:25:00","ContestEndDate":"2020-10-11T20:25:00Z","ContestStatus":1,"ContestType":{"ContestTypeId":21,"SportId":1,"Sport":"NFL","RequiresTeam":true,"SalaryCap":50000,"DefaultTimeRemaining":540.0,"DefaultPlayerTimeRemaining":60,"AllowLateSwap":true,"AutomaticPayouts":false,"IsActive":true},"CreatorUserId":null,"NumberOfEntrants":5,"MaxNumberPlayers":14,"SalariesAvailable":true,"DraftGroupId":40304,"GameTypeId":1,"GameType":{"gameTypeId":1,"name":"Classic","description":"Create a 9-player lineup while staying under the $50,000 salary cap","tag":"","sportId":1,"draftType":"SalaryCap","gameStyle":{"gameStyleId":1,"sportId":1,"sortOrder":1,"name":"Classic","abbreviation":"CLA","description":"Create a 9-player lineup while staying under the $50,000 salary cap","isEnabled":true}},"IsDirectChallenge":false,"IsGuaranteed":true,"IsFreeroll":false,"TopPayout":0.0,"MaxNumberEntries":1,"UserContestId":2271705961,"LineupId":2668129485,"ResultsRank":0,"TimeRemainingOpp":0,"TotalPointsOpp":0.0,"UsernameOpp":null,"TeamName":"","PlayerPoints":0.0,"TimeRemaining":0,"UserEntries":1,"TokensWon":0.0,"TicketWinnings":0.0,"PrizesWon":0,"AbandonedDirectChallenge":false,"DefaultTimeRemaining":540,"LateDraftEligible":false}''')


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
def rosterfile(test_directory):
    return test_directory / 'contest_roster.json'


def test_mycontests(p, mycontestfile, tprint):
    """Tests mycontests"""
    contests = p.mycontests(mycontestfile)
    assert isinstance(contests, list)
    assert isinstance(random.choice(contests), dict)
    tprint(set([item['ContestName'] for item in contests]))


def test_is_bestball_contest(p, contestfile, dfscontest):
    """Tests is_bestball_contest"""
    contest = json.loads(contestfile.read_text())
    assert p.is_bestball_contest(contest)
    assert not p.is_bestball_contest(dfscontest)


def test_contest_details(p, contestfile, tprint):
    """Tests contest_roster"""
    c = p.contest_details(p._to_obj(contestfile))
    fields = {'ContestId', 'ContestName', 'BuyInAmount', 'MaxNumberPlayers', 'DraftGroupId', 'GameTypeId', 'TopPayout',
              'UserContestId', 'ResultsRank', 'TotalPointsOpp', 'UsernameOpp', 'PlayerPoints'}
    tprint(c)
    assert set(c.keys()) == fields
    

def test_contest_leaderboard(p, leaderboardfile):
    """Tests contest_leaderboard"""
    lb = p.contest_leaderboard(json.loads(leaderboardfile.read_text()))
    assert isinstance(lb, list)
    assert isinstance(random.choice(lb), dict)
    fields = {'userName', 'userKey', 'rank', 'fantasyPoints'}
    for item in lb:
        assert fields == set(item.keys())


def test_contest_roster(p, rosterfile, tprint):
    """Tests contest_roster"""
    roster = p.contest_roster(json.loads(rosterfile.read_text()))
    tprint(p._to_dataframe(roster))    
    assert isinstance(roster, list)
    assert isinstance(random.choice(roster), dict)


def test_filter_contests_by_size(p, mycontestfile):
    """Tests filter_contests_by_size"""
    contests = p.mycontests(mycontestfile)
    for size in (3, 6, 12):
        filtered = p.filter_contests_by_size(contests, size=size)
        contest = random.choice(filtered)
        assert f'{size}-Player' in contest['ContestName']
    

def test_ownership(p, datadir, tprint):
    """Tests ownership"""
    rosterdir = datadir / 'dkdrafts'

    # rosters is a list of lists
    rosters = [p.contest_roster(p._to_obj(f))
               for f in random.sample(list(rosterdir.glob('*.json')), 3)]
    df = p.ownership(rosters)
    assert not df.empty


def test_standings(p, datadir, tprint):
    """Tests standings"""
    lbdir = datadir / 'dkleagues'
        
    # leaderboards is a list of lists
    leaderboards = [p.contest_leaderboard(p._to_obj(f))
                   for f in random.sample(list(lbdir.glob('*.json')), 10)]
    df = p.standings(leaderboards, 'sansbacon')
    tprint(df)
    assert not df.empty

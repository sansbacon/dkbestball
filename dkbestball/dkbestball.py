# %%
import datetime
import json
import logging
import os
from pathlib import Path
import re

import numpy as np
import pandas as pd

"""
Log:
* 10/9/2020: 
next step is ownership method
right now reads files rather than list of dict. Can get more code from ipython session 528. 
select * from history where session = 528

"""

class Parser:
    """
    >>> p = Parser()

    STEP ONE: get list of bestball contests (mycontests)
    https://www.draftkings.com/mycontests

    var contests has the contest information under 'live' (in-season at least)
    view source and then copy to file mycontests.html - can't save directly
    can also just copy and paste variable and then load file directly
    the variable isn't true json, as the keys are not quoted properly
    have maxentrantsperpage, live, upcoming, history
    
    >>> mycontestsfile = Path.home() / 'workspace' / 'dkbestball' / 'tests' / 'mycontests.html'
    >>> mycontests = p.mycontests(mycontestsfile)

    STEP TWO: extract relevant data from mycontests
    so for each contest in mycontests, call contest_details
    create dict of dicts with key = ContestId

    >>> contest_details_dict = {c['ContestId']: p.contest_details(c) for c in mycontests}
     
    STEP THREE: get playerpool
    for 2020, have draftgroup of 37604 or 37605
    can get playerpool for both to match up with contests

    >>> pool = {id: p.player_pool(id=id) for id in (37604, 37605)}

    STEP FOUR: get contest standings (DK calls these leaderboards)
    >>> lb = []
    ... for pth in p.LEADERBOARD_DIR.glob('*.json'):
    ...     data = p._to_obj(pth)
    ...     lb += p.contest_leaderboard(data)

    STEP FIVE: get contest rosters
    >>> rosters = []
    ... for pth in p.ROSTER_DIR.glob('*.json'):
    ...     data = p._to_obj(pth)
    ...     playerd = p.player_pool_dict(id=data['entries'][0]['draftGroupId'])
    ...     rosters += p.contest_roster(data, playerd)

    STEP SIX: match contest details to rosters
    Create a dict of contestkey: contest size
    >>> sized = {item['ContestId']: item['MaxNumberPlayers'] for item in contest_details_dict.values()}
    ... for roster in rosters:
    ...     contest_key = int(roster['contestKey'])
    ...     roster['MaxNumberPlayers'] = sized.get(contest_key)    
    """
    DATADIR = Path(__file__).parent / 'data'
    LEADERBOARD_DIR = DATADIR / 'leaderboards'
    ROSTER_DIR = DATADIR / 'rosters'

    def __init__(self):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.bestball_gametype_id = 145

    @staticmethod
    def _pctcol(val):
        return f'{round(val * 100, 2)}%'
        
    def _contest_type(self, contest):
        """Determines if tournament or sit_and_go"""
        return 'tournament' if 'Tournament' in contest['ContestName'] else 'sit_and_go'

    def _draftablesfn(self, id):
            return self.DATADIR / f'draftables_{id}.json'

    def _to_dataframe(self, container):
        """Converts container to dataframe"""
        return pd.DataFrame(container)

    def _to_obj(self, pth):
        """Reads json text in pth and creates python object"""
        if isinstance(pth, str):
            pth = Path(pth)
        return json.loads(pth.read_text())

    def contest_details(self, contest):
        """Parses contest dict for relevant details
           Some overlap with leaderboards re: contest leader (UsernameOpp, TotalPointsOpp) 
           and your entry (UserContestId, ResultsRank, PlayerPoints)

        Args:
            content (dict): single contest dict

        Returns:
            dict with keys from wanted, values from content
        """
        wanted = [
            'ContestId',
            'ContestName',
            'BuyInAmount',
            'MaxNumberPlayers',
            'DraftGroupId',
            'GameTypeId',
            'TopPayout',
            'UserContestId',
            'ResultsRank',
            'TotalPointsOpp',
            'UsernameOpp',
            'PlayerPoints'
        ]

        d = {k:contest.get(k) for k in wanted}
        d['ContestType'] = self._contest_type(contest)
        d['ClockType'] = 'slow' if 'Slow Draft' in contest['ContestName'] else 'fast'
        return d

    def contest_leaderboard(self, content):
        """Parses contest leaderboard

        Args:
            content (dict): leaderboard dict

        Returns:
            list: of dict
        """
        vals = []
        wanted = ['userName', 'userKey', 'rank', 'fantasyPoints']
        for item in content['leaderBoard']:
            d = {k:item.get(k) for k in wanted}
            d['contestKey'] = content['contestKey']
            vals.append(d)
        return vals

    def contest_roster(self, content, playerd=None):
        """Parses roster from single contest. DK doesn't seem to have saved draft order.

        Args:
            content (dict): parsed draft resource
            playerd (dict): additional player data
        
        Returns:
            list: of dict
        
        TODO: add stats and utilizations
        """
        entry = content['entries'][0]
        wanted_metadata = ['draftGroupId', 'contestKey', 'entryKey', 'lineupId', 'userName', 'userKey']
        wanted_scorecard = ['displayName', 'draftableId']
        draft_metadata = {k:entry.get(k) for k in wanted_metadata}
        try:
            vals = []
            for player in entry['roster']['scorecards']:
                d = {k: player[k] for k in wanted_scorecard}
                if playerd:
                    d = dict(**d, **playerd.get(d['draftableId'], {}))
                vals.append(dict(**draft_metadata, **d))
            return vals

        except KeyError:
            logging.exception(entry)
            return []

    def filter_contests_by_size(self, data, size=None):
        """Filters mycontests for specific type, say 3-Player"""
        return [c for c in data if f'{size}-Player' in c['ContestName']]

    def is_bestball_contest(self, content):
        """Tests if it is a bestball contest
        
        Args:
            content (dict): contest dict

        Returns:
            bool
        """
        return content.get('GameTypeId') == self.bestball_gametype_id

    def mycontests(self, htmlfn=None, jsonfn=None):
        """Parses mycontests.html page / contests javascript variable
        
        Args:
            htmlfn (Path or str): path of html file
            jsonfn (Path or str): path of json file

        Returns:
            list: of contest dict
        """
        if htmlfn:
            # read text of file into content variable
            try:
                content = htmlfn.read_text()
            except:
                content = Path(htmlfn).read_text()

            # now extract the contests variable and return parsed JSON
            # RIGHT NOW IS LIVE ONLY
            patt = re.compile(r'var contests = \{.*?live\: (\[.*?\]),', re.MULTILINE | re.DOTALL)
            match = re.search(patt, content)
            if match:
                return json.loads(match.group(1))
            return None
        elif jsonfn:
            # TO IMPLEMENT
            pass
        else:
            raise ValueError('htmlfn or jsonfn cannot both be None')

    def ownership(self, rosterdf, username, contest_size=None):
        """Calculates ownership across rosters

        Args:
            rosterdf (DataFrame): of rosters
            username (str): the username to get ownership for

        Returns:
            DataFrame with columns
            displayName, n_contests, n_own, vs_field
        """
        # first determine overall ownership
        # will be some players I don't own that 
        # are excluded if start with my ownership
        n_contests = len(rosterdf['contestKey'].unique())
        overall_ownership = (
            rosterdf
            .groupby('displayName')
            .agg(tot_drafted=('contestKey', 'count')) 
            .assign(tot_drafted_pct=lambda df_: df_.tot_drafted/n_contests*100)
        )

        summ = (
            rosterdf
            .query(f"userName == '{username}'")
            .groupby('displayName')
            .agg(user_drafted=('contestKey', 'count'))
            .assign(user_drafted_pct=lambda df_: df_.user_drafted/n_contests*100)
        )

        df = overall_ownership.loc[:, ['tot_drafted_pct']].join(summ, how='left').fillna(0)
        df['user_drafted'] = df['user_drafted'].astype(int)

        if contest_size:
            df['vs_field'] = df['user_drafted_pct'] - (df['tot_drafted_pct'] / contest_size)

        df.insert(0, 'n_contests', n_contests)
        return df    

    def player_pool(self, draftables=None, id=None):
        """Takes parsed draftables (from file or request) and creates player pool
           Can also pass id and will read draftables file from data directory

        Args:
            draftables (dict): parsed JSON resource 
            id (int): draftables Id

        Returns:
            list: of dict with keys
            'draftableId', 'displayName', 'playerId', 'playerDkId', 'position', 'teamAbbreviation'
        """
        if id:
            fn = self._draftablesfn(id)
            draftables = self._to_obj(fn)
        if not isinstance(draftables, dict):
            raise ValueError('Did not properly load draftables')
        wanted = ('draftableId', 'playerId', 'playerDkId', 'teamId',
                'displayName', 'position', 'teamAbbreviation')
        return [{k: item[k] for k in wanted} for item in draftables['draftables']]
    
    def player_pool_dict(self, draftables=None, id=None):
        """Takes parsed draftables (from file or request) and creates player pool dict with key of draftableId
           Can also pass id and will read draftables file from data directory

        Args:
            draftables (dict): parsed JSON resource 
            id (int): draftables Id

        Returns:
            dict of dict: key is draftableId, 
            value is dict with keys 'displayName', 'playerId', 'playerDkId', 'position', 'teamAbbreviation'
        """
        wanted = ('displayName', 'playerId', 'playerDkId', 'position', 'teamAbbreviation')
        return {item['draftableId']: {k:item[k] for k in wanted}
                for item in self.player_pool(draftables=draftables, id=id)}
    
    def standings(self, leaderboards, username):
        """Calculates overall standings for user by contest type
        
        Args:
            leaderboards (list): of dict
            username (str): the user to track standings for

        Returns:
            DataFrame
        """
        return pd.DataFrame(leaderboards).query(f"userName == '{username}'")


# %%
if __name__ == '__main__':
    pass
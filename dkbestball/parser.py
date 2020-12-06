from collections import ChainMap
import json
import logging
from pathlib import Path
import re

import pandas as pd


class Parser:
    """Parses DK bestball contest files"""

    PLAYERPOOL_FIELDS = [
        'draftableId', 'playerId', 'playerDkId', 'displayName', 'position',
        'teamAbbreviation'
    ]

    def __init__(self, bestball_gametype_id=145):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.bestball_gametype_id = bestball_gametype_id

    @staticmethod
    def _pctcol(val):
        return f'{round(val * 100, 2)}%'

    @staticmethod
    def _to_dataframe(container):
        """Converts container to dataframe"""
        return pd.DataFrame(container)

    @staticmethod
    def _to_obj(pth):
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
            'ContestId', 'ContestName', 'BuyInAmount', 'MaxNumberPlayers',
            'DraftGroupId', 'GameTypeId', 'TopPayout', 'UserContestId',
            'ResultsRank', 'TotalPointsOpp', 'UsernameOpp', 'PlayerPoints'
        ]

        d = {k: contest.get(k) for k in wanted}
        d['ClockType'] = 'slow' if 'Slow Draft' in contest[
            'ContestName'] else 'fast'
        return d

    def contest_leaderboard(self, content):
        """Parses contest leaderboard

        Args:
            content (dict): leaderboard dict

        Returns:
            list: of dict

        """
        vals = []
        wanted = ['UserName', 'UserKey', 'Rank', 'FantasyPoints']
        lbkey = 'Leaderboard'
        ckey = 'MegaContestKey'
        ekey = 'MegaEntryKey'
        for item in content[lbkey]:
            d = {k: item.get(k) for k in wanted}
            d[ckey] = item[ckey]
            d[ekey] = item[ekey]
            vals.append(d)
        return vals

    def contest_roster(self, content, playerd=None):
        """Parses roster from single contest.
           DK doesn't seem to have saved draft order.

        Args:
            content (dict): parsed draft resource
            playerd (dict): additional player data

        Returns:
            list: of dict

        """
        entry = content['entries'][0]
        wanted_metadata = [
            'draftGroupId', 'contestKey', 'entryKey', 'lineupId', 'userName',
            'userKey'
        ]
        wanted_scorecard = ['displayName', 'draftableId']
        draft_metadata = {k: entry.get(k) for k in wanted_metadata}
        vals = []
        for player in entry['roster']['scorecards']:
            d = {k: player[k] for k in wanted_scorecard}
            if playerd:
                d = dict(ChainMap(d, playerd.get(d['draftableId'], {})))
            vals.append(dict(**draft_metadata, **d))
        return vals

    def get_entry_key(self, leaderboard, username):
        """Gets entry key from leaderboard"""
        return [
            lbd['MegaEntryKey']
            for lbd in leaderboard['Leaderboard']
            if lbd['UserName'] == username
        ][0]

    def is_bestball_contest(self, content):
        """Tests if it is a bestball contest

        Args:
            content (dict): contest dict

        Returns:
            bool
        """
        return content.get('GameTypeId') == self.bestball_gametype_id

    def mycontests(self, htmlfn):
        """Parses mycontests.html page / contests javascript variable

        Args:
            htmlfn (Path or str): path of html file

        Returns:
            list: of contest dict
        """
        # read text of file into content variable
        try:
            content = htmlfn.read_text()
        except AttributeError:
            content = Path(htmlfn).read_text()

        # now extract the contests variable and return parsed JSON
        # RIGHT NOW IS LIVE ONLY
        patt = re.compile(r'var contests = \{.*?live\: (\[.*?\]),',
                          re.MULTILINE | re.DOTALL)
        match = re.search(patt, content)
        if match:
            return json.loads(match.group(1))
        return None

    def player_pool(self, draftables_fn=None, draftables=None):
        """Takes parsed draftables (from file or request) and creates player pool
           Can also pass path and will read draftables file

        Args:
            draftables_fn (Path): draftables path
            draftables (dict): parsed JSON resource

        Returns:
            list: of dict with keys
            'draftableId', 'displayName', 'playerId', 'playerDkId',
            'position', 'teamAbbreviation'
        """
        if draftables_fn:
            draftables = self._to_obj(draftables_fn)
        if not isinstance(draftables, dict):
            raise ValueError('Did not properly load draftables')
        return [{k: item[k]
                 for k in self.PLAYERPOOL_FIELDS}
                for item in draftables['draftables']]

    def player_pool_dict(self, draftables_fn=None, draftables=None):
        """Takes parsed draftables (from file or request) and
           creates player pool dict with key of draftableId
           Can also pass id and will read draftables file from data directory

        Args:
            draftables_fn (Path): draftables path
            draftables (dict): parsed JSON resource

        Returns:
            dict of dict: key is draftableId,
            value is dict with keys 'displayName', 'playerId', 'playerDkId',
                                    'position', 'teamAbbreviation'
        """
        wanted = self.PLAYERPOOL_FIELDS.copy()
        key = wanted.pop(0)
        pool = self.player_pool(draftables_fn=draftables_fn,
                                draftables=draftables)
        return {item[key]: {k: item[k] for k in wanted} for item in pool}


if __name__ == '__main__':
    pass

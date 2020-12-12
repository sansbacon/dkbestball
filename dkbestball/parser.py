from collections import ChainMap
from dateutil import tz
import json
import logging
from pathlib import Path
import re

import dateparser
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

    def _lckeys(self, x):
        if isinstance(x, list):
            return [self._lckeys(v) for v in x]
        elif isinstance(x, dict):
            return dict((k.lower(), self._lckeys(v)) for k, v in x.items())
        else:
            return x

    def _pctcol(self, val):
        return f'{round(val * 100, 2)}%'

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

        # keys differ based on the contest type
        # this is a preliminary approach to getting the right key
        wanted = ['UserName', 'UserKey', 'Rank', 'FantasyPoints']
        lbkey = 'Leaderboard' if 'Leaderboard' in content else 'leaderBoard'
        ckey = 'MegaContestKey' if 'MegaContestKey' in content else 'contestKey'
        ekey = 'MegaEntryKey' if 'MegaEntryKey' in content[lbkey][
            0] else 'entryKey'

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

    def megacontest_entered(self, content):
        """Parses megacontest data (including associated weekly contests)

        Args:
            content (dict): leaderboard dict

        Returns:
            list: of dict

        Example:
    
            "LiveContestsEntries", 
            "FinalizedContestsEntries", 
            "Contests"
        
            {
                "DraftGroupId": 37605,
                "DraftGroupState": "Historical",
                "ContestName": "NFL Best Ball $1 12-Player (Sit + Go)",
                "ContestId": 89460375,
                "ContestTypeId": 145,
                "SortOrder": 40030,
                "EndDate": "2020-09-15T02:20:00.0000000Z",
                "StartDate": "2020-09-11T00:20:00.0000000Z",
                "EntryCount": 12,
                "UserEntryCount": 1,
                "MaxEntries": 12,
                "MaxEntryLimit": 1,
                "Sport": "NFL",
                "EntryFee": 1,
                "PayoutTotal": 0,
                "PositionsPaid": 0,
                "Attributes": {}
            }
        """
        vals = []
        wanted = {'DraftGroupId', 'ContestId', 'StartDate'}
        from_zone = tz.tzutc()
        to_zone = tz.tzlocal()
        for item in content['Contests']:
            d = {k: item.get(k) for k in wanted}
            utc = dateparser.parse(item['StartDate'])
            utc = utc.replace(tzinfo=from_zone)
            d['StartDate'] = utc.astimezone(to_zone)
            vals.append(d)
        return vals

    def mycontests(self, htmlfn=None, html=None):
        """Parses mycontests.html page / contests javascript variable

        Args:
            htmlfn (Path or str): path of html file
            html (str): html from contests page

        Returns:
            dict: keys maxentrantsperpage, live, upcoming, history

        """
        # read text of file into content variable
        if not html:
            try:
                html = htmlfn.read_text()
            except AttributeError:
                html = Path(htmlfn).read_text()

        # now extract the contests variable and return parsed JSON
        # RIGHT NOW IS LIVE ONLY
        patt = re.compile(r'var contests = (\{.*?\})\;',
                          re.MULTILINE | re.DOTALL)
        match = re.search(patt, html)
        if match:
            jsvar = match.group(1)
            mapping = {
                'maxentrantsperpage :': '"maxentrantsperpage": ',
                'live:': '"live":',
                'upcoming:': '"upcoming":',
                'history:': '"history":'
            }

            for original, replacement in mapping.items():
                jsvar = jsvar.replace(original, replacement)
            jsvar = jsvar.replace('// no pre-load', '')
            return json.loads(jsvar)
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

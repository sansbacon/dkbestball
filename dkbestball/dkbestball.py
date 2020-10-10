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
    STEP ONE: get list of bestball contests
    https://www.draftkings.com/mycontests

    var contests has the contest information under 'live' (in-season at least)
    view source and then copy to file mycontests.html - can't save directly
    can also just copy and paste variable and then load file directly
    the variable isn't true json, as the keys are not quoted properly
    have maxentrantsperpage, live, upcoming, history


    STEP TWO:

    """
    
    def __init__(self):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.bestball_gametype_id = 145

    def _to_dataframe(self, container):
        """Converts container to dataframe"""
        return pd.DataFrame(container)

    def _to_obj(self, pth):
        """Reads json text in pth and creates python object"""
        return json.loads(pth.read_text())

    def contest(self, content):
        """Parses contest dict
        
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

        return {k:content.get(k) for k in wanted}

    def contest_leaderboard(self, content):
        """Parses contest leaderboard

        Args:
            content (dict): leaderboard dict

        Returns:
            list: of dict
        """
        lb = content['leaderBoard']
        wanted = ['userName', 'userKey', 'rank', 'fantasyPoints']
        return [{k:item.get(k) for k in wanted} for item in lb]

    def contest_roster(self, content):
        """Parses roster from single contest. DK doesn't seem to have saved draft order.

        Args:
            content (dict): parsed draft resource

        Returns:
            list: of dict
        """
        # TODO: add stats and utilizations
        entry = content['entries'][0]
        wanted_metadata = ['draftGroupId', 'contestKey', 'entryKey', 'lineupId', 'userName', 'userKey']
        wanted_scorecard = ['displayName', 'draftableId']
        draft_metadata = {k:entry.get(k) for k in wanted_metadata}
        try:
            roster = entry['roster']
            return [dict(**draft_metadata, **{k: player[k] for k in wanted_scorecard})
                    for player in roster['scorecards']]       
        except KeyError:
            logging.exception(entry)
            return None

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

    def ownership(self, rosters):
        """Calculates ownership across rosters

        Args:
            rosters (list): of list of dict

        Returns:
            DataFrame
        """
        # TODO: add player positions
        flattened = [item for sublist in rosters for item in sublist]
        df = pd.concat([self._to_dataframe(flattened).displayName.value_counts(),
                        self._to_dataframe(flattened).displayName.value_counts(normalize=True)],
                        axis=1).reset_index()
        df.columns = ['player', 'n', 'pct']
        return df


    def standings(self, leaderboards, username):
        """Calculates overall standings for user by contest type
        
        Args:
            leaderboards (list): of list of dict
            username (str): the user to track standings for

        Returns:
            DataFrame
        """
        items = []
        for lb in leaderboards:
            match = [item for item in lb if item['userName'] == username]
            if match:
                match = match[0]
                match['contest_size'] = len(lb)
                items.append(match)
        return pd.DataFrame(items)


if __name__ == '__main__':
    pass
import datetime
import json
import logging
import os
from pathlib import Path
import pytz
import re
import time

import numpy as np
import pandas as pd

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

class Parser:
    
    def __init__(self):
        logging.getLogger(__name__).addHandler(logging.NullHandler())
        self.bestball_gametype_id = 145

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
        return {k:lb.get(k) for k in wanted}

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
        wanted_scorecard = ['diplayName', 'draftableId']
        draft_metadata = {k:entry.get(k) for k in wanted_metadata}
        roster = entry['roster']
        draft_metadata['rosterKey'] = roster['rosterKey']
        return [dict(**draft_metadata, **{k: player[k] for k in wanted_scorecard})
                for player in roster['scorecards']]       
                    
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


    def filter_contests(self, data):
        """Filters for specific type, say 3-Player"""
        pass
        #tm = [c for c in data if '3-Player' in c['ContestName']]
        #for t in tm:
        #    url = roster_url.format(t['DraftGroupId'], t['ContestEntryId'])
        #    print(url)


 


if __name__ == '__main__':
    pass
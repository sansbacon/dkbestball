# parse_files.py
# gets leaderboards and scoring from local directories
# run this after updating those files with get_files.py
# %%
import logging
from pathlib import Path
import pandas as pd

try:
    from dkbestball import Parser
except ModuleNotFoundError:
    import sys
    pth = Path(__file__).parent.parent
    sys.path.append(str(pth))
    from dkbestball import Parser

# %%
def run():
    """Main script
    
    TODO: need to adjust to TitleCase keys from draftkings
    """    
    p = Parser()
    
    # STEP ONE: get list of bestball contests (mycontests)
    # https://www.draftkings.com/mycontests

    mycontestsfile = Path(__file__).parent.parent / 'tests' / 'mycontests.html'
    mycontests = p.mycontests(mycontestsfile)

    # STEP TWO: extract relevant data from mycontests
    # so for each contest in mycontests, call contest_details
    # create dict of dicts with key = ContestId

    contest_details_dict = {c['ContestId']: p.contest_details(c) for c in mycontests}
     
    # STEP THREE: get playerpool
    # for 2020, have draftgroup of 37604 or 37605
    # can get playerpool for both to match up with contests
    pool = {id: p.player_pool(id=id) for id in (37604, 37605)}

    # STEP FOUR: get contest standings (DK calls these leaderboards)
    lb = []
    for pth in list(p.LEADERBOARD_DIR.glob('*.json'))[0:1]:
        data = p._to_obj(pth)
        lb += p.contest_leaderboard(data)

    # STEP FIVE: get contest rosters
    rosters = []
    for pth in p.ROSTER_DIR.glob('*.json'):
        data = p._to_obj(pth)
        playerd = p.player_pool_dict(id=data['entries'][0]['draftGroupId'])
        rosters += p.contest_roster(data, playerd)

    # STEP SIX: match contest details to rosters
    # Create a dict of contestkey: contest size
    sized = {item['ContestId']: item['MaxNumberPlayers'] for item in contest_details_dict.values()}
    for roster in rosters:
        contest_key = int(roster['contestKey'])
        roster['MaxNumberPlayers'] = sized.get(contest_key)    


# %%
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()
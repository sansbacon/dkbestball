from configparser import ConfigParser
from .dkbestball import *

ctx = ConfigParser()

# use custom and then default as fallback
configfile = Path.home() / '.dkbestball' / 'dkbestball.conf'
if not configfile.is_file():
    configfile = Path(__file__).parent / 'dkbestball.sample.conf'

# now read the configfile
ctx.read(configfile)

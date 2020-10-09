import json

from bs4 import BeautifulSoup
import pytest


def test_dkbestball(test_directory, tprint):
    html = (test_directory / 'mycontests.html').read_text()
    soup = BeautifulSoup(html, 'lxml')
    for s in soup.find_all('script'):
        tprint(s.text)
    assert soup is not None

import re
from bs4 import BeautifulSoup


def get_value(domType, classValue, x):
    # eample run
    dummy = '<i href="" src="" content="" data-listing-id ="" >'
    dummy = BeautifulSoup(dummy)
    dummy = dummy.findAll('i')[0]
    dummy.get_text()
    ##
    result = x.findAll(domType, classValue)
    if len(result) == 0:
        return(dummy)
    else:
        return(result[0])

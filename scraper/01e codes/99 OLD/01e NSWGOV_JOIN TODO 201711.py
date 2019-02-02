
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from urllib2 import urlopen
import re
import time
import os
import multiprocessing as mp
import matplotlib.pyplot as plt
import time
import datetime
import math

from bs4.element import Tag

#dateid = time.strftime("%Y%m%d")


## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
final_dir  = output_directory + '01c Property_DF'
master_dir = output_directory + '01e Master_DF'

## Get last filee
last_dateid = pd.Series(os.listdir(final_dir))
dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
last_dateid = last_dateid[~last_dateid.str.contains(dateid)]
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))



#######################################################################
# Get files

this_df = pd.read_csv(final_dir+'/'+dateid+'_domain.csv')
this_df = this_df.drop_duplicates('domainid',keep='first')

last_df = pd.read_csv(final_dir+'/'+last_dateid+'_domain.csv')
last_df = last_df.drop_duplicates('domainid',keep='first')


domain_df = pd.concat([this_df,last_df],axis=0,ignore_index=True)
domain_df = domain_df.drop_duplicates('domainid',keep='first')

domain_df.to_csv(master_dir+'/'+dateid+'_domain.csv',index=False)























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
print('This Data Scrape: %s' % (dateid))

###############
## Get Data

this_df = pd.read_csv(final_dir + '/' + dateid + '_realestate.csv')
this_df['realestateID'] = this_df['href'].str.extract('-(\d+)',expand=False)
print(this_df['realestateID'].value_counts().value_counts())
this_df= this_df.drop_duplicates('realestateID',keep='first')


last_df = pd.read_csv(final_dir + '/' + last_dateid + '_realestate.csv')
last_df['realestateID'] = last_df['href'].str.extract('-(\d+)',expand=False)
print(last_df['realestateID'].value_counts().value_counts())
last_df= last_df.drop_duplicates('realestateID',keep='first')


realestate_df = pd.concat([this_df,last_df],axis=0)
realestate_df = realestate_df.drop(['Unnamed: 0','filename'],axis=1)

print(realestate_df['realestateID'].value_counts().value_counts())
realestate_df= realestate_df.drop_duplicates('realestateID',keep='first')


realestate_df.to_csv(master_dir+'/'+dateid + "_realestate.csv",index=False)











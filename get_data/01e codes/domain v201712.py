
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
dateid = str(20171231)
print (dateid)

last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float)
last_dateid = last_dateid[last_dateid.fillna(99999999)< int(dateid)].max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))


#######################################################################
# Get files

this_df = pd.read_csv(final_dir+'/'+dateid+'_domain.csv')
this_df = this_df.drop_duplicates('domainid',keep='first')

lnglat= ['latitude','longitude']
this_df[lnglat] = this_df[lnglat].apply(lambda y: y.apply(lambda x: np.NaN if x=='missing' else x),axis=0)
print('THIS missing values')
print(this_df.isnull().sum(axis=0)/this_df.shape[0])

last_df = pd.read_csv(final_dir+'/'+last_dateid+'_domain.csv')
last_df = last_df.drop_duplicates('domainid',keep='first')

lnglat= ['latitude','longitude']
last_df[lnglat] = last_df[lnglat].apply(lambda y: y.apply(lambda x: np.NaN if x=='missing' else x),axis=0)
print('LAST missing values')
print(last_df.isnull().sum(axis=0)/last_df.shape[0])


domain_df = pd.concat([this_df,last_df],axis=0,ignore_index=True)
domain_df = domain_df.drop_duplicates('domainid',keep='first')

print(domain_df['domainid'].value_counts()).value_counts()


domain_df.to_csv(master_dir+'/'+dateid+'_domain.csv',index=False)























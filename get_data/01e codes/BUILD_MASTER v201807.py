
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
dateid = '20180722'
sourceid = ['domain','REA','auhouse_rent'][1]

print('Iterating through: %s' % sourceid)

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
final_dir  = output_directory + '01c Property_DF'
master_dir = output_directory + '01e Master_DF'

last_dateid = pd.Series(os.listdir(master_dir))
last_dateid = last_dateid[~last_dateid.str.contains(dateid)]
last_dateid = last_dateid[last_dateid.str.contains(sourceid)]
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

#######################################################################
# Get files
old_master_df = pd.read_csv(master_dir +'/'+ last_dateid +'_'+sourceid+'.csv')
print('Size of existings dataset: %d ' % old_master_df.shape[0])

update_files = pd.Series(os.listdir(final_dir))
update_files = update_files[update_files.str.contains(dateid +'_'+sourceid)]
if update_files.shape[0]<>1:
    update_files = update_files[update_files.str.contains('_cut')]
update_df = pd.read_csv(final_dir+'/'+update_files.iloc[0])
print('Size of UPDATE dataset: %d ' % update_df.shape[0])

#Concat
master_df = pd.concat([old_master_df,update_df],axis=0,ignore_index=True)
# auhouse_rent FIX
master_df = master_df.rename(columns={'ID':sourceid+'id'})


master_df = master_df.drop_duplicates(sourceid+'id',keep='first')

print(master_df[sourceid+'id'].value_counts()).value_counts()
print(master_df.shape)

master_df.to_csv(master_dir+'/'+dateid+'_'+sourceid+'.csv',index=False)

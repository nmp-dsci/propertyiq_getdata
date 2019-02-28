
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

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

## Get data
dateid =  pd.Series(os.listdir(output_directory + '01a Region href property')).str.extract('(\d{8})_').max()
dateid = '20171231'
print (dateid)

final_dir  = output_directory + '01c Property_DF'

scrape_area_dir =  output_directory + '01a Region href property/' + dateid +'_domain.com'
suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_domain.com'


#######################################################################
# Build Master

suburb_files = pd.DataFrame({'suburb':os.listdir(suburb_dir)})
suburb_files['size'] = suburb_files['suburb'].apply(lambda x: os.stat(suburb_dir+'/'+x).st_size)
# filters
suburb_files = suburb_files.query('suburb <> ".DS_Store"  and size > 100')

print('STEP 1: BUILD MASTER SET OF UPDATE')
master_df = pd.DataFrame()
for suburb in suburb_files['suburb'].values:         # suburb = suburb_files.values[0]
    print(suburb)
    suburb_df = pd.read_csv(suburb_dir +'/'+ suburb)
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)

print('Run some checks on the aggregated data')
print(master_df.head())
print('Check1: size')
print(master_df.shape)
print('Check2: ID row FReqy')
print(master_df['domainid'].value_counts().value_counts())
print('Check3: Check penetration of different "variable" typs')
print(master_df.query('value == value').groupby(['key','variable']).size()/master_df.domainid.nunique())


master_df.query('variable=="landSize" and value == value').head()


# 20180304 1,767,729 rows 
master_df.to_csv(final_dir  + '/'+dateid+'_domain_all.csv',index=False)
# master_df = pd.read_csv(final_dir  + '/'+dateid+'_domain_all.csv')

#####################
### format all column
print(master_df.groupby('key').size())
print(master_df.groupby(['key','variable']).size())


keep_keys = ['address','features','price','price','tags']

master_df.query('key=="details"').head()
master_df.query('variable=="tagText"').head()
master_df.query('key=="tags"')['value'].value_counts()
master_df.query('variable=="priceFromApm"')['value'].value_counts()
master_df.query('domainid ==2007093114')

# subset to keys of interest
master_df = master_df.query('key in '+str(keep_keys))

# rename the keys
master_df.groupby('key').size()
#key_rename = {
#        'constructionStatus':'buildType'
#    ,   'features_general':'attr'
#    }
#for k in key_rename.keys():
#    print(k)
#    master_df['key'] = master_df['key'].apply(lambda x: key_rename[k] if x == k else x)
#master_df.groupby('key').size()

## master column
master_df['column'] = master_df['key'] + '__' + master_df['variable']

## values only
master_df = master_df.query('value==value')

###
master_df['rn'] = master_df.groupby(['domainid','column']).cumcount()
master_df = master_df.query('rn==0')

# 201712: 81646
# 201803: 67114
master_df = master_df.pivot(index='domainid',columns='column', values='value').reset_index()


#####################
## TO CSV
master_df.to_csv(final_dir  + '/'+dateid+'_domain_cut.csv',index=False)



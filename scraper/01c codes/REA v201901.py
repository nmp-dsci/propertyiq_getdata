
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
os.listdir(os.path.dirname(output_directory))

## Get data
sourceid = 'REA'
dateid =  pd.Series(os.listdir(output_directory + '01b Suburb_Files')).str.extract('(\d{8})_').max().iloc[0].astype(int).astype(str)
print (dateid)

final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid[~last_dateid.str.contains(dateid)]
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_'+sourceid
suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_'+sourceid

#######################################################################
# Build Master

suburb_files = pd.DataFrame({'suburb':os.listdir(suburb_dir)})
suburb_files['size'] = suburb_files['suburb'].apply(lambda x: os.stat(suburb_dir+'/'+x).st_size)
# filters
suburb_files = suburb_files.query('suburb <> ".DS_Store"  and size > 100')


master_df = pd.DataFrame()
for suburb in suburb_files['suburb'].values:         # suburb = suburb_files.values[0]
    print(suburb)
    suburb_df = pd.read_csv(suburb_dir +'/'+ suburb)
    suburb_df['filename'] = suburb
    #suburb_df = suburb_df.query('details==details')
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)

print('Run some checks on the aggregated data')
print('Check1: size')
print(master_df.shape)
print('Check2: ID row FReqy')
print(master_df[sourceid+'id'].value_counts().value_counts().describe())
print('Check3: Check penetration of different "variable" ')
print(master_df.query('value == value').groupby(['key','variable']).size()/master_df.REAid.nunique())

# 7.6m
master_df.to_csv(final_dir  + '/'+dateid+'_'+sourceid+'_all.csv',index=False)
# master_df = pd.read_csv(final_dir  + '/'+dateid+'_REA_all.csv')
#####################
### format all column
print(master_df.groupby('key').size())
print(master_df.groupby(['key','variable']).size())

master_df.query('variable=="price_img" and value <> "missing"')


keep_keys = ['HTML','address','constructionStatus','dateSold','features_general','price','propertyType','status']

# subset to keys of interest
master_df = master_df.query('key in '+str(keep_keys))

# rename the keys
master_df.groupby('key').size()
key_rename = {
        'constructionStatus':'buildType'
    ,   'features_general':'attr'
    }

for k in key_rename.keys():
    print(k)
    master_df['key'] = master_df['key'].apply(lambda x: key_rename[k] if x == k else x)

master_df.groupby('key').size()

## master column
master_df['column'] = master_df['key'] + '__' + master_df['variable']

## values only
master_df = master_df.query('value==value')

###
master_df['rn'] = master_df.groupby([sourceid+'id','column']).cumcount()
master_df = master_df.query('rn==0')

# 84.7k
master_df = master_df.pivot(index=sourceid+'id',columns='column', values='value').reset_index()

########### FORMATING For stacking
### RENAME FIELDS
#master_df = pd.read_csv(master_dir+'/'+dateid+'_'+source+'.csv')
rename_map = {
        "HTML__bathrooms":"baths"
    ,   "HTML__beds":"beds"
    ,   "HTML__parking":"parking"
#    ,   "HTML__price_img":"price_img"
    ,   "HTML__price_str":"sale_price"
    ,   "HTML__property_type":"propertyType"
    ,   "dateSold__value":"dateID"
    ,   "address__latitude":"latitude"
    ,   "address__locality":"suburb"
    ,   "address__longitude":"longitude"
    ,   "address__postCode":"postcode"
    ,   "address__state":"state"
    ,   "address__streetAddress":"street"
    ,   "buildType__constructionStatus":"constructionStatus"
    ,   "price__abbreviated":"price_override"
    ,   "status__label":"source"
    }
print('CHECK No new columns not renamed')
print(np.setdiff1d(master_df.columns , rename_map.keys()+['domainid']))

master_df = master_df.rename(columns=rename_map)

master_df = master_df[rename_map.values() + ['REAid']]

#### fix price
master_df['price_override'] = master_df['price_override'].str.lower()
def pull_price(price = '1.02m'):
    if 'm' in price:
        return float(re.sub('[a-z]','',price)) * 1000000
    if 'k' in price:
        return float(re.sub('[a-z]','',price)) * 1000

master_df['price_override'] = master_df['price_override'].apply(lambda x: pull_price(price=x) if pd.notnull(x) else x)
master_df['sale_price'] = master_df['sale_price'].fillna(master_df['price_override'])


master_df['sale_price'] = master_df['sale_price'].apply(lambda x: np.NaN if x=="Contact agent" else x)
master_df['sale_price'] = master_df['sale_price'].str.replace('[$,]','')

## Take the average on ranges
def range_mean(prange = "Range: 375000 - 445000"):
    find_vars = pd.Series(re.split('\D',prange))
    find_vars = find_vars[find_vars<>'']
    mean_var = find_vars.astype(int).mean()
    return mean_var

master_df['sale_price'] = master_df['sale_price'].apply(lambda x: range_mean(prange=x) if '-' in str(x) else x)
master_df['sale_price'] = master_df['sale_price'].astype(float)

master_df = master_df.drop(['price_override'],axis=1)

## format property type
master_df['propertyType'] = master_df['propertyType'].str.lower()
master_df['propertyType'].value_counts()

apartment_vars = ['apartment','unit','studio','flat']
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'apartment' if x in apartment_vars else x)

semi_vars = ['townhouse','villa','duplex/semi-detached','duplex semi-detached','terrace']
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'semi detached' if x in semi_vars else x)

land_vars = ['residential land']
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'land' if x in land_vars else x)

keep_vars = ['house','apartment','semi detached','land']
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: x if x in keep_vars else 'other' )

#####################
## TO CSV
master_df.to_csv(final_dir  + '/'+dateid+'_'+sourceid+'_cut.csv',index=False)

########
# does floor plan exis
# master_df = pd.read_csv(final_dir  + '/'+dateid+'_REA_all.csv')
#print(master_df.groupby(['key','variable']).size())
#master_df.query('value=="floorplan"')









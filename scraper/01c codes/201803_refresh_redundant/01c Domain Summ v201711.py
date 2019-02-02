
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
dateid = str(20171104)
print (dateid)


## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid +'_domain.com'
suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_domain.com'


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
    suburb_df = suburb_df.query('details==details')
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)

####################
pd.options.display.max_columns = 28

master_df['index'] = master_df.index.values

# get attributes out of details
detail_df = master_df['details'].copy().str.lower()
detail_df = detail_df.str.replace('0 parkings','0|parking|')
detail_df = detail_df.str.replace('0 beds','0|bed|')
detail_df = detail_df.str.replace('0 baths','0|bath|')
detail_df = detail_df.str.replace('parkings','parking|')
detail_df = detail_df.str.replace('beds','bed|')
detail_df = detail_df.str.replace('baths','bath|')
detail_df = detail_df.str.split('|',expand=True)

# step 1: Pull out Date and Sold Type
master_df['DateID'] = pd.to_datetime(detail_df[0].apply(lambda x: x[(len(x)-11):]),format='%d %b %Y',errors='coerce')
master_df['DateID'].isnull().value_counts()

detail_df['datestr'] = master_df['DateID'].dt.strftime('%d %b %Y').fillna('')
master_df['SoldType'] = detail_df.apply(lambda x: x[0].replace(x['datestr'],''),axis=1).str.strip()
detail_df = detail_df.drop([0,'datestr'],axis=1)

# price
price_col = detail_df.apply(lambda x: x.str.contains('[$]|Price'),axis=0).sum(axis=0)
master_df['price'] = detail_df[price_col[price_col==price_col.max()].index.values]
detail_df = detail_df.drop(price_col[price_col==price_col.max()].index.values,axis=1)

## get street
master_df['street'] = detail_df.apply(lambda x: x[5] if 'price from' in x[3] else x[3],axis=1)
## Override for suburb
master_df['street'][master_df['street'].str.contains('[0-9]')==False] = np.NaN

#### Check how much of Street is null
master_df['street'].isnull().value_counts()

detail_df.loc[master_df.query('street <> street').index.values,[2,3,4,5]]


street_dup = master_df.groupby('street').size().reset_index().rename(columns={0:'n'})
street_dup['n'].value_counts()
street_dup.query('n==12')

##### GET ATTRIBUTES
detail_df = detail_df.reset_index()
get_attr = pd.melt(detail_df, id_vars='index')
get_attr = get_attr[get_attr['value'].str.replace('[^A-Za-z0-9]','').str.strip().str.len().fillna(0) > 0 ]
get_attr['value'] = get_attr['value'].str.replace('\s+',' ')

######
# street
get_attr['street'] = get_attr['value'].str.lower().str.contains('([0-9/abc]+) ([a-z]+)')


# bath/ bed/ parking
attr = ['bath','bed','parking']

get_attr['rowID'] = get_attr.index.values
get_attr['is_attr'] = get_attr['value'].apply(lambda x: 1 if x in attr else 0)
get_attr['is_attr'] = get_attr['is_attr'] * get_attr['rowID']
get_attr['is_attr'] = get_attr['is_attr'].apply(lambda x: np.NaN if x==0 else x)

print('check the values found for attr seeding')
print(get_attr.query('is_attr == is_attr and street == False')['value'].value_counts())
print(get_attr.query('street == True').shape)

### make bath/bed/parking count to position of attr
get_attr = get_attr.sort_values(['index','variable'])
get_attr['attrID'] = get_attr['is_attr'].fillna(method='bfill',limit=1)

print('This is all be 2s')
print(get_attr['attrID'].value_counts().value_counts())

### Attr only
attr_df = get_attr.query('attrID==attrID').copy()
attr_df['variable'] = attr_df['is_attr'].apply(lambda x: 'type' if x==x else 'value')
attr_df = attr_df.pivot(index='attrID',columns='variable',values='value' ).reset_index()
attr_df = pd.merge(
            attr_df
        ,   get_attr.groupby(['attrID','index']).size().reset_index().drop(0,axis=1)
        ,   on='attrID'
        ,   how='left'
        )
print('Check results')
print(attr_df.isnull().sum(axis=0))
### final mapping
attr_df = attr_df.pivot(index='index',columns='type',values='value')
attr_df = attr_df.reset_index()
### Apply mapping
master_df = pd.merge(
            master_df
        ,   attr_df
        ,   on='index'
        ,   how='left'
        )

##############################
### Final Delivery
##############################


## DomainID
master_df['domainid'] = master_df['domainid'].str.extract('([0-9]{10})')
# suburub and postcode
suburb_state = master_df['filename'].str.split('-nsw-',expand=True)
master_df['suburb'] = suburb_state[0]
master_df['postcode'] = suburb_state[1].str.extract('([0-9]{4})_b').astype(int)
## price
master_df['price'] = master_df['price'].str.replace('[$,]','')
master_df['price'] = master_df['price'].str.lower().apply(lambda x: np.NaN if x == 'price withheld' else x)
master_df['price'] = master_df['price'].astype(float)

### CHECKS

master_df.isnull().sum(axis=0)
master_df.query('DateID <> DateID')


master_df['details'].loc[269]

### OUTPUT
delivery_col = ['domainid','latitude','longitude','DateID',
                'SoldType','price','street','suburb','postcode',
                'bath','bed','parking']


master_df[delivery_col].to_csv(final_dir  + '/'+dateid+'_domain.csv',index=False)












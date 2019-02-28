
### IMPORT Libraries
import pandas as pd
import numpy as np
import re,os
import time,datetime

from config import * 
from utils import * 

## Get data
sourceid = 'domain'

scrape_area_dir =  output_directory + '01a Region href property/' + dateid +'_'+sourceid
suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_'+sourceid


#######################################################################
# Build Master

suburb_files = pd.DataFrame({'suburb':os.listdir(suburb_dir)})
suburb_files['size'] = suburb_files['suburb'].apply(lambda x: os.stat(suburb_dir+'/'+x).st_size)
# filters
suburb_files = suburb_files.query('suburb != ".DS_Store"  and size > 100')

print('STEP 1: BUILD MASTER SET OF UPDATE')
master_df = pd.DataFrame()
for suburb in suburb_files['suburb'].values:         # suburb = suburb_files.values[0]
    print(suburb)
    suburb_df = pd.read_csv(suburb_dir +'/'+ suburb)
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)

print('Run some checks on the aggregated data')
print('Check1: size')
print(master_df.shape)
print('Check2: ID row FReqy')
print(master_df[sourceid+'id'].value_counts().value_counts())
print('Check3: Check penetration of different "variable" typs')
master_df.query('value == value').groupby(['key','variable']).size()/master_df.domainid.nunique()


master_df.query('variable=="landSize" and value == value').head()


# 20180304 1,767,729 rows
master_df.to_csv(final_dir  + '/'+dateid+'_'+sourceid+'_all.csv',index=False)
# master_df = pd.read_csv(final_dir  + '/'+dateid+'_domain_all.csv')

#####################
### format all column
print(master_df.groupby('key').size())
print(master_df.groupby(['key','variable']).size())

master_df.query(sourceid+'id == 2007744352')

keep_keys = ['address','features','price','price','tags']

master_df.query('key=="details"').head()
master_df.query('variable=="tagText"').head()
master_df.query('key=="tags"')['value'].value_counts()
master_df.query('variable=="priceFromApm"')['value'].value_counts()
master_df.query(sourceid+'id ==2007093114')

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
master_df['rn'] = master_df.groupby([sourceid+'id','column']).cumcount()
master_df = master_df.query('rn==0')

# 201803: 67114
master_df = master_df.pivot(index=sourceid+'id',columns='column', values='value').reset_index()

#######################################
####### PREPARE for STACKING
### RENAME FIELDS
#master_df = pd.read_csv(master_dir+'/'+dateid+'_domain.csv')

rename_map = {
        "address__lat":"latitude"
    ,   "address__lng":"longitude"
    ,   "address__postcode":"postcode"
    ,   "address__state":"state"
    ,   "address__street":"street"
    ,   "address__suburb":"suburb"
    ,   "features__baths":"baths"
    ,   "features__beds":"beds"
    ,   "features__landSize":"landSize"
    ,   "features__parking":"parking"
    ,   "features__propertyType":"propertyType"
    ,   "features__isRural":"isRural"
    ,   "features__landUnit":"landUnit"
    ,   "price__price":"sale_price"
    ,   "tags__tagClassName":"source"
    ,   "tags__tagText":"dateID"
    }
print('CHECK No new columns not renamed')
print(np.setdiff1d(master_df.columns , list(rename_map.keys())+[sourceid+'id']))

master_df = master_df.rename(columns=rename_map)

### format PRICE
master_df['sale_price'] = master_df['sale_price'].apply(lambda x: np.NaN if x=="Price Withheld" else x)
master_df['sale_price'] = master_df['sale_price'].str.replace('[$,]','')

## formate DAt
master_df = pd.concat([
        master_df
    ,   master_df['dateID'].str.extract('(?P<Sale_type>.*) (?P<dateID2>\d{2} [a-zA-Z]{3} \d{4})')
    ]   ,axis=1)
master_df = master_df.drop('dateID',axis=1).rename(columns={'dateID2':'dateID'})

## Format Property Type
master_df['propertyType'] = master_df['propertyType'].str.lower()
master_df['propertyType'].value_counts()

apartment_vars = ['apartmentunitflat','studio','newapartments','penthouse']
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'apartment' if x in apartment_vars else x)

semi_vars = ['townhouse','villa','semidetached','duplex','terrace']
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'semi detached' if x in semi_vars else x)

land_vars = ['vacantland','newhouseland','newland','developmentsite']
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'land' if x in land_vars else x)

keep_vars = ['house','apartment','semi detached','land']
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: x if x in keep_vars else 'other' )

#####################
## TO CSV
master_df.to_csv(final_dir  + '/'+dateid+'_'+sourceid+'_cut.csv',index=False)

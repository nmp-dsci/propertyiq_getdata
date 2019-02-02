
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
dateid = '20180524'

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
final_dir  = output_directory + '01c Property_DF'
master_dir = output_directory + '01e Master_DF'


#######################################################################
# Get files

filesDF = pd.DataFrame({'f':os.listdir(final_dir)})
filesDF = filesDF[filesDF.f.str.contains('_domain_cut')]

domain_df = pd.DataFrame({})
for fi in filesDF.f.values:
    newDF = pd.read_csv(final_dir +'/'+ fi)
    domain_df = pd.concat([domain_df,newDF],axis=0)

domain_df = domain_df.drop_duplicates('domainid',keep='first')

print(domain_df['domainid'].value_counts()).value_counts()

### RENAME FIELDS
#domain_df = pd.read_csv(master_dir+'/'+dateid+'_domain.csv')
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
    ,   "price__price":"sale_price"
    ,   "tags__tagClassName":"source"
    ,   "tags__tagText":"dateID"
    }

print('CHECK No new columns not renamed')
print(np.setdiff1d(domain_df.columns , rename_map.keys()+['domainid']))

domain_df = domain_df.rename(columns=rename_map)


### format PRICE
domain_df['sale_price'] = domain_df['sale_price'].apply(lambda x: np.NaN if x=="Price Withheld" else x)
domain_df['sale_price'] = domain_df['sale_price'].str.replace('[$,]','')

## formate DAt
domain_df = pd.concat([
        domain_df
    ,   domain_df['dateID'].str.extract('(?P<Sale_type>.*) (?P<dateID2>\d{2} [a-zA-Z]{3} \d{4})')
    ]   ,axis=1)
domain_df = domain_df.drop('dateID',axis=1).rename(columns={'dateID2':'dateID'})

## Format Property Type
domain_df['propertyType'] = domain_df['propertyType'].str.lower()
domain_df['propertyType'].value_counts()

apartment_vars = ['apartmentunitflat','studio','newapartments','penthouse']
domain_df['propertyType'] = domain_df['propertyType'].apply(lambda x: 'apartment' if x in apartment_vars else x)

semi_vars = ['townhouse','villa','semidetached','duplex','terrace']
domain_df['propertyType'] = domain_df['propertyType'].apply(lambda x: 'semi detached' if x in semi_vars else x)

land_vars = ['vacantland','newhouseland','newland','developmentsite']
domain_df['propertyType'] = domain_df['propertyType'].apply(lambda x: 'land' if x in land_vars else x)

keep_vars = ['house','apartment','semi detached','land']
domain_df['propertyType'] = domain_df['propertyType'].apply(lambda x: x if x in keep_vars else 'other' )



domain_df.to_csv(master_dir+'/'+dateid+'_domain.csv',index=False)

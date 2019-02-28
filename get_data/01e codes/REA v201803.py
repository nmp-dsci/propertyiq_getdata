
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
dateid = '20180304'

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
final_dir  = output_directory + '01c Property_DF'
master_dir = output_directory + '01e Master_DF'

source ='realestate'

#######################################################################
# Get files

filesDF = pd.DataFrame({'f':os.listdir(final_dir)})
filesDF = filesDF[filesDF.f.str.contains('_'+source+'_cut')]

domain_df = pd.DataFrame({})
for fi in filesDF.f.values:
    newDF = pd.read_csv(final_dir +'/'+ fi)
    domain_df = pd.concat([domain_df,newDF],axis=0)

domain_df = domain_df.drop_duplicates('REAid',keep='first')

print(domain_df['REAid'].value_counts()).value_counts()

### RENAME FIELDS
#domain_df = pd.read_csv(master_dir+'/'+dateid+'_'+source+'.csv')
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
print(np.setdiff1d(domain_df.columns , rename_map.keys()+['domainid']))

domain_df = domain_df.rename(columns=rename_map)

domain_df = domain_df[rename_map.values() + ['REAid']]

#### fix price
domain_df['price_override'] = domain_df['price_override'].str.lower()
def pull_price(price = '1.02m'):
    if 'm' in price:
        return float(re.sub('[a-z]','',price)) * 1000000
    if 'k' in price:
        return float(re.sub('[a-z]','',price)) * 1000

domain_df['price_override'] = domain_df['price_override'].apply(lambda x: pull_price(price=x) if pd.notnull(x) else x)    
domain_df['sale_price'] = domain_df['sale_price'].fillna(domain_df['price_override'])


domain_df['sale_price'] = domain_df['sale_price'].apply(lambda x: np.NaN if x=="Contact agent" else x)
domain_df['sale_price'] = domain_df['sale_price'].str.replace('[$,]','')

## Take the average on ranges
def range_mean(prange = "Range: 375000 - 445000"):
    find_vars = pd.Series(re.split('\D',prange))
    find_vars = find_vars[find_vars<>'']
    mean_var = find_vars.astype(int).mean()
    return mean_var

domain_df['sale_price'] = domain_df['sale_price'].apply(lambda x: range_mean(prange=x) if '-' in str(x) else x)
domain_df['sale_price'] = domain_df['sale_price'].astype(float)

domain_df = domain_df.drop(['price_override'],axis=1)

## format property type
domain_df['propertyType'] = domain_df['propertyType'].str.lower()
domain_df['propertyType'].value_counts()

apartment_vars = ['apartment','unit','studio','flat']
domain_df['propertyType'] = domain_df['propertyType'].apply(lambda x: 'apartment' if x in apartment_vars else x)

semi_vars = ['townhouse','villa','duplex/semi-detached','duplex semi-detached','terrace']
domain_df['propertyType'] = domain_df['propertyType'].apply(lambda x: 'semi detached' if x in semi_vars else x)

land_vars = ['residential land']
domain_df['propertyType'] = domain_df['propertyType'].apply(lambda x: 'land' if x in land_vars else x)

keep_vars = ['house','apartment','semi detached','land']
domain_df['propertyType'] = domain_df['propertyType'].apply(lambda x: x if x in keep_vars else 'other' )



###
domain_df.to_csv(master_dir+'/'+dateid+'_'+source+'.csv',index=False)






















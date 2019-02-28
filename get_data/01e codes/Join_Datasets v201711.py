#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sun Oct  8 20:12:02 2017

@author: macmac
"""


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
print('this Data Scrape: %s' % (dateid))



#####################
## Get DATA
domain_df = pd.read_csv(master_dir  + '/'+dateid+'_domain.csv')
realestate_df = pd.read_csv(master_dir  + '/'+dateid+'_realestate.csv')
nswgov_df = pd.read_csv(master_dir  + '/'+dateid+'_nswgov.csv')

print('View Domain and Realestate Fields')
print(domain_df.isnull().sum(axis=0))
print(realestate_df.isnull().sum(axis=0))
print(nswgov_df.isnull().sum(axis=0))


nswgov_df = nswgov_df.rename(columns={'SALEDATE':'DateID','SALEPRICE':'price'})

######################
## Create date
realestate_df['DateID'] = pd.to_datetime(realestate_df['sale_date'].str.replace('Sold on ','')
                        ,format='%d %b %Y').dt.strftime('%Y-%m-%d')


domain_df[domain_df['street'].str.lower().str.contains('7 gouda close').fillna(False)].T
realestate_df[realestate_df['address'].str.lower().str.contains('7 gouda close').fillna(False)].T


print('view price coverage')
print(domain_df['price'].notnull().value_counts(normalize=True))
print(realestate_df['price'].notnull().value_counts(normalize=True))


#### View street
print("Domain Street is null")
print(domain_df['street'].isnull().value_counts())
print("Realestate.com.au Street is null")
print(realestate_df['address'].isnull().value_counts())


#### Format NSWGOV
nswgov_df = nswgov_df.rename(columns={'PROPERTYNUMBER':'nswgovID'})

nswgov_df = pd.concat([
            nswgov_df
        ,   nswgov_df['ADDRESS'].str.extract(',(.*?) NSW (\d{4})',expand=True).rename(columns={0:'suburb',1:'postcode'})
        ],  axis=1)

nswgov_df['street'] = nswgov_df['ADDRESS'].str.split(',',expand=True)[0]

#### Format RealEstate
realestate_df.index = realestate_df['realestateID']
realestate_df['address'] = realestate_df['address'].str.upper()
realestate_df['address'] = realestate_df['address'].apply(lambda x: np.NaN if "ADDRESS AVAILABLE ON REQUEST" in x else x)

re_street = realestate_df['address'].str.upper().str.split(',',expand=True).reset_index()
re_street = pd.melt(re_street,id_vars = 'realestateID').dropna(axis=0)

re_str_max = re_street.groupby(['realestateID'])['variable'].max()
re_street = pd.merge(
            re_street
        ,   re_str_max.reset_index()
        ,   on = 'realestateID'
        ,   how= 'left'
        )
re_street = re_street.query('variable_x<variable_y').drop('variable_y',axis=1).rename(columns={'variable_x':'variable'})
re_street2 = re_street.groupby('realestateID').agg({'value':lambda x: ' '.join(x)})
re_street2['value'] = re_street2['value'].str.strip()

realestate_df = pd.merge(
            realestate_df
        ,   re_street2.reset_index().rename(columns={'value':'street'})
        ,   on='realestateID'
        ,   how='left'
        )


## Format Dates
realestate_df['DateID'] = pd.to_datetime(realestate_df['DateID'])
domain_df['DateID'] = pd.to_datetime(domain_df['DateID'])
nswgov_df['DateID'] = pd.to_datetime(nswgov_df['DateID'])




##########################################
### Split address

#addr_DF = domain_df[['domainid','street','suburb','postcode']];idcol='domainid'
#addr_DF = realestate_df[['realestateID','street','suburb','postcode']];idcol='realestateID'
#addr_DF = nswgov_df[['nswgovID','street','suburb','postcode']];idcol='nswgovID'


def street_formater(addr_DF = domain_df[['domainid','street','suburb','postcode']],idcol='domainid'):
    drop_wrds = ['STREET','ROAD','AVENUE','DRIVE','PLACE','CRESCENT','CLOSE',
        'ST','PARADE','RD','AVE','WAY','GROVE','COURT','LANE','PARK','CIRCUIT',
        'HIGHWAY','CR','ST','DR','RD','AVE','AV','CL','CT','WAY']
    # aggregate to ID level
    addr_DF2 = addr_DF.groupby(list(addr_DF.columns.values)).size()
    addr_DF2 = addr_DF2.reset_index().drop(0,axis=1)
    addr_DF2.index = addr_DF2[idcol]
    ## pull out street
    street_addr = addr_DF2['street'].str.split('/',expand=True )
    street_addr = street_addr.reset_index()
    street_addr = pd.melt(street_addr, id_vars = idcol).dropna(axis=0)
    street_addr = pd.merge(
                street_addr
            ,   street_addr.groupby(idcol)['variable'].max().reset_index()
            ,   on=[idcol]
            ,   how='left'      )
    street_addr['max'] = (street_addr['variable_y']==street_addr['variable_x']).astype(int)
    street_addr = pd.pivot_table(
                    data = street_addr
                ,   index=[idcol]
                ,   columns=['max']
                ,   values = 'value'
                ,   aggfunc= lambda x: ''.join(x)
                ).rename(columns={0:'SubDwelling',1:'Street'})
    ##### now process
    street_df = street_addr['Street'].str.upper().str.split('[^0-9A-z]',expand=True).reset_index()
    street_df = pd.melt(street_df,id_vars = idcol ).dropna(axis=0)
    street_df = street_df[street_df['value'].str.len()>0]
    street_df = street_df[~street_df['value'].isin(drop_wrds)]
    street_df['strID'] = street_df['value'].str.replace('[0-9 ]','').str.len()
    street_df['numID'] = street_df['value'].str.replace('[^0-9]','').str.len()
    # num ID rule: street_df.groupby(['strID','numID']).size().unstack('numID')
    street_df['type_str'] = street_df['strID'].apply(lambda x: 1 if x==0 else 0)
    street_df['type_str'][street_df['numID']>0] = 1
    street_df = street_df.drop(['strID','numID'],axis=1)
    ### 
    street_ms = pd.merge(
        street_df
    ,   street_addr.reset_index()
    ,   on =idcol
    ,   how='inner'
    )
    street_ms = pd.merge(
       street_ms  
    ,   addr_DF2[[idcol,'suburb','postcode']]
    ,   on = idcol
    ,   how = 'inner'    
    )
    return street_ms

#### files
addr_domain = street_formater(domain_df[['domainid','street','suburb','postcode']],idcol='domainid')
addr_realestate = street_formater(realestate_df[['realestateID','street','suburb','postcode']],idcol='realestateID')
addr_nswgov = street_formater(nswgov_df[['nswgovID','street','suburb','postcode']],idcol='nswgovID')

# put in override
addr_domain['SubDwelling'] = addr_domain['SubDwelling'].fillna('999999')
addr_realestate['SubDwelling'] = addr_realestate['SubDwelling'].fillna('999999')
addr_nswgov['SubDwelling'] =addr_nswgov['SubDwelling'].fillna('999999')

# adhoc fixes
domain_df = domain_df.rename(columns={'domainid':'domainID'})
addr_domain = addr_domain.rename(columns={'domainid':'domainID'})
addr_nswgov['postcode'] = addr_nswgov['postcode'].astype(int)

### join all files

join_cols = ['value','type_str','SubDwelling','postcode']
sourceDF = pd.DataFrame({'source':['domain','realestate','nswgov'],'dummy':1})
matches = pd.merge(sourceDF,sourceDF,on='dummy',how='inner').query('source_x<>source_y ')
matches = matches.query('source_x < source_y')


merge_df = pd.DataFrame()
for row in range(matches.shape[0]): # row=2
    print(row)
    sx = matches['source_x'].iloc[row]
    sy = matches['source_y'].iloc[row]
    merge_dfs = pd.merge(
        globals()['addr_'+sx][[sx+'ID']+join_cols]
    ,   globals()['addr_'+sy][[sy+'ID']+join_cols]
    ,   on = join_cols
    ,   how='inner'
    )    
    ## Get match rate
    merge_match = merge_dfs.groupby([sx+'ID',sy+'ID','type_str']).size().unstack('type_str')
    merge_match['match'] = merge_match.isnull().sum(axis=1)
    merge_match = merge_match.query('match==0')
    merge_match = merge_match.reset_index()
    ## remove dups
    x_dups = merge_match.groupby(sx+'ID').size().reset_index().rename(columns={0:'n'})
    y_dups = merge_match.groupby(sy+'ID').size().reset_index().rename(columns={0:'n'})
    #  Drop X class dups
    merge_match = pd.merge(
            merge_match
        ,   x_dups.query('n>4')
        ,   on= sx+'ID'
        ,   how='left'
        ).query('n<>n').drop('n',axis=1)
    #  Drop Y class dups
    merge_match = pd.merge(
            merge_match
        ,   y_dups.query('n>4')
        ,   on= sy+'ID'
        ,   how='left'
        ).query('n<>n').drop('n',axis=1)
    ## Date Filter
    for ss in [sx,sy]:
        merge_match = pd.merge(
                merge_match
            ,   globals()[ss+'_df'][[ss+'ID','DateID']].rename(columns={'DateID':ss+'_DateID'})
            ,   on = ss+'ID'
            ,   how='left'
            )
    merge_match = merge_match.drop([0,1,'match'],axis=1)
    merge_match['DateDiff'] = (merge_match[sx+'_DateID'] - merge_match[sy+'_DateID']).apply(lambda x: abs(x.days) if pd.notnull(x) else 0 )
    merge_match = merge_match.query('DateDiff < 60')
    ##
    if merge_df.shape[0]==0:
        merge_df = merge_match[[sx+'ID',sy+'ID']]
    else:
        merge_df = pd.merge(merge_df
                ,   merge_match[[sx+'ID',sy+'ID']]
                ,   on = list(np.intersect1d(list(merge_df.columns),[sx+'ID',sy+'ID']))
                ,   how='outer')

### FINAL MAtchfile
merge_df.isnull().sum(axis=1).value_counts()

## Add on the ZERO match between files
domain_1s = pd.DataFrame({
        'domainID':np.setdiff1d(domain_df['domainID'], merge_df['domainID'].dropna().unique())
    ,   'realestateID':np.NaN
    ,   'nswgovID':np.NaN
    })
realestate_1s = pd.DataFrame({
        'domainID':np.NaN
    ,   'realestateID':np.setdiff1d(realestate_df['realestateID'], merge_df['realestateID'].dropna().unique())
    ,   'nswgovID':np.NaN
    })
nswgov_1s = pd.DataFrame({
        'domainID':np.NaN
    ,   'realestateID':np.NaN
    ,   'nswgovID':np.setdiff1d(nswgov_df['nswgovID'], merge_df['nswgovID'].dropna().unique())
    })
merge_df = pd.concat([
            merge_df
        ,   domain_1s
        ,   realestate_1s
        ,   nswgov_1s
        ],axis=0)
#should be a lift in singles now aka isnull==2
merge_df.isnull().sum(axis=1).value_counts()


###### JOIN  columns
domain_cols = ['latitude','longitude','DateID',
               'SoldType','price','bath','bed','parking',
               'street','postcode','suburb']
realestate_cols = ['DateID','property_type',
                   'price','bathrooms','beds','parking',
                   'street','postcode','suburb']
nswgov_cols = ['STRATANONSTRATA','price','DateID',
               'street','postcode','suburb']

domain_rename = dict(zip(domain_cols,['D_'+x for x in domain_cols]))
realestate_rename = dict(zip(realestate_cols,['R_'+x for x in realestate_cols]))
nswgov_rename = dict(zip(nswgov_cols,['N_'+x for x in nswgov_cols]))


# 20170820:   877,252   
# 20171104: 1,006,768
# 20171116: 1,504,503       (reworked for nswgov and 3 joins)

fulljoin_df = merge_df
for source in sourceDF['source']:       # source = sourceDF['source'].iloc[2]
    print(source)
    fulljoin_df = pd.merge(
        fulljoin_df
    ,   globals()[source+'_df'][[source+'ID']+globals()[source+'_cols']].rename(columns=globals()[source+'_rename'])
    ,   on = source+'ID'
    ,   how='left'
    )

### make sure dates are close
colid= ['domainID','realestateID','nswgovID']
fulljoin_df['match_rate'] = fulljoin_df[colid].notnull().sum(axis=1)
fulljoin_df['match_rate'].value_counts()

###
fulljoin_df['DateID'] = fulljoin_df['R_DateID'].fillna(fulljoin_df['D_DateID']).fillna(fulljoin_df['N_DateID'])
fulljoin_df['price'] = fulljoin_df['R_price'].fillna(fulljoin_df['D_price']).fillna(fulljoin_df['N_price'])
fulljoin_df['street'] = fulljoin_df['R_street'].fillna(fulljoin_df['D_street']).fillna(fulljoin_df['N_street'])
fulljoin_df['postcode'] = fulljoin_df['R_postcode'].fillna(fulljoin_df['D_postcode']).fillna(fulljoin_df['N_postcode'])
fulljoin_df['suburb'] = fulljoin_df['R_suburb'].fillna(fulljoin_df['D_suburb']).fillna(fulljoin_df['N_suburb'])


fulljoin_df = fulljoin_df.query('DateID==DateID')

## Set Price
## 
fulljoin_df['bath_C'] = fulljoin_df['D_bath'].fillna(fulljoin_df['R_bathrooms'])
fulljoin_df['beds_C'] = fulljoin_df['D_bed'].fillna(fulljoin_df['R_beds'])
fulljoin_df['parking_C'] = fulljoin_df['D_parking'].fillna(fulljoin_df['R_parking'])
## time factors
fulljoin_df['YYYYMM'] = fulljoin_df['DateID'].dt.strftime('%Y%m')
fulljoin_df['YYYYQ'] = fulljoin_df['DateID'].dt.strftime('%Y').astype(int)*10 + np.ceil(fulljoin_df['DateID'].dt.strftime('%m').astype(float)/3).astype(int)
fulljoin_df['YYYYQ'] = fulljoin_df['YYYYQ'].astype(str)


fulljoin_df.to_csv(master_dir + '/'+dateid+ '_final_df.csv',index=False)



















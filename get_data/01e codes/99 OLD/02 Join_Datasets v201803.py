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
REA_df = pd.read_csv(master_dir  + '/'+dateid+'_realestate.csv')
nswgov_df = pd.read_csv(final_dir  + '/'+'20171231'+'_nswgov.csv')

print('View Domain and Realestate Fields')
print(domain_df.isnull().sum(axis=0)/domain_df.shape[0]*1.0)
print(REA_df.isnull().sum(axis=0)/domain_df.shape[0]*1.0)
print(nswgov_df.isnull().sum(axis=0)/domain_df.shape[0]*1.0)

#### Format NSWGOV
nswgov_df = nswgov_df.rename(columns={'SALEDATE':'dateID','SALEPRICE':'sale_price','PROPERTYNUMBER':'nswgovid'})


######################
## Create dateID
REA_df['dateID'] = pd.to_datetime(REA_df['dateID']).dt.strftime('%Y-%m-%d')
domain_df['dateID'] = pd.to_datetime(domain_df['dateID'],format='%d %b %Y').dt.strftime('%Y-%m-%d')
nswgov_df['dateID'] = pd.to_datetime(nswgov_df['dateID']).dt.strftime('%Y-%m-%d')

####
print('view price coverage')
print(domain_df['sale_price'].notnull().value_counts(normalize=True))
print(REA_df['sale_price'].notnull().value_counts(normalize=True))


#### View street
print("Domain Street is null")
print(domain_df['street'].isnull().value_counts())
print("Realestate.com.au Street is null")
REA_df['street'] = REA_df['street'].apply(lambda x: np.NaN if x=="Address available on request" else x)
print(REA_df['street'].isnull().value_counts())

## split out the address STRING
nswgov_df = pd.concat([
            nswgov_df
        ,   nswgov_df['ADDRESS'].str.extract('(?P<street>.*),(?P<suburb>.*) NSW (?P<postcode>\d{4})',expand=True)
        ],  axis=1)

#### Format RealEstate
REA_df['street'] = REA_df['street'].str.upper()
domain_df['street'] = domain_df['street'].str.upper()





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
addr_REA = street_formater(REA_df[['REAid','street','suburb','postcode']],idcol='REAid')
addr_nswgov = street_formater(nswgov_df[['nswgovid','street','suburb','postcode']],idcol='nswgovid')

# put in override
addr_domain['SubDwelling'] = addr_domain['SubDwelling'].fillna('999999')
addr_REA['SubDwelling'] = addr_REA['SubDwelling'].fillna('999999')
addr_nswgov['SubDwelling'] =addr_nswgov['SubDwelling'].fillna('999999')

# adhoc fixes
addr_nswgov['postcode'] = addr_nswgov['postcode'].astype(int)

### join all files
join_cols = ['value','type_str','SubDwelling','postcode']
sourceDF = pd.DataFrame({'source':['domain','REA','nswgov'],'dummy':1})
matches = pd.merge(sourceDF,sourceDF,on='dummy',how='inner').query('source_x<>source_y ')
matches = matches.query('source_x < source_y')


REA_df['dateID'] = pd.to_datetime(REA_df['dateID'])
domain_df['dateID'] = pd.to_datetime(domain_df['dateID'])
nswgov_df['dateID'] = pd.to_datetime(nswgov_df['dateID'])


merge_df = pd.DataFrame()
for row in range(matches.shape[0]): # row=0
    print(row)
    sx = matches['source_x'].iloc[row]
    sy = matches['source_y'].iloc[row]
    print('Matching: %s + %s' %(sx,sy))
    merge_dfs = pd.merge(
        globals()['addr_'+sx][[sx+'id']+join_cols]
    ,   globals()['addr_'+sy][[sy+'id']+join_cols]
    ,   on = join_cols
    ,   how='inner'
    )    
    ## Get match rate
    merge_match = merge_dfs.groupby([sx+'id',sy+'id','type_str']).size().unstack('type_str')
    merge_match['match'] = merge_match.isnull().sum(axis=1)
    merge_match = merge_match.query('match==0')
    merge_match = merge_match.reset_index()
    ## remove dups
    x_dups = merge_match.groupby(sx+'id').size().reset_index().rename(columns={0:'n'})
    y_dups = merge_match.groupby(sy+'id').size().reset_index().rename(columns={0:'n'})
    #  Drop X class dups
    merge_match = pd.merge(
            merge_match
        ,   x_dups.query('n>4')
        ,   on= sx+'id'
        ,   how='left'
        ).query('n<>n').drop('n',axis=1)
    #  Drop Y class dups
    merge_match = pd.merge(
            merge_match
        ,   y_dups.query('n>4')
        ,   on= sy+'id'
        ,   how='left'
        ).query('n<>n').drop('n',axis=1)
    ## Date Filter
    for ss in [sx,sy]:
        merge_match = pd.merge(
                merge_match
            ,   globals()[ss+'_df'][[ss+'id','dateID']].rename(columns={'dateID':ss+'_dateID'})
            ,   on = ss+'id'
            ,   how='left'
            )
    merge_match = merge_match.drop([0,1,'match'],axis=1)
    merge_match['DateDiff'] = (merge_match[sx+'_dateID'] - merge_match[sy+'_dateID']).apply(lambda x: abs(x.days) if pd.notnull(x) else 0 )
    merge_match = merge_match.query('DateDiff < 60')
    ##
    ## remove dups
    x_dups = merge_match.groupby(sx+'id').size().reset_index().rename(columns={0:'n'})
    y_dups = merge_match.groupby(sy+'id').size().reset_index().rename(columns={0:'n'})
    #  Drop X class dups
    merge_match = pd.merge(
            merge_match
        ,   x_dups.query('n==1')
        ,   on= sx+'id'
        ,   how='left'
        ).drop('n',axis=1)
    #  Drop Y class dups
    merge_match = pd.merge(
            merge_match
        ,   y_dups.query('n==1')
        ,   on= sy+'id'
        ,   how='left'
        ).drop('n',axis=1)    
    ##
    if merge_df.shape[0]==0:
        merge_df = merge_match[[sx+'id',sy+'id']]
    else:
        merge_df = pd.merge(merge_df
                ,   merge_match[[sx+'id',sy+'id']]
                ,   on = list(np.intersect1d(list(merge_df.columns),[sx+'id',sy+'id']))
                ,   how='outer')
    print('number of row %d' % merge_df.shape[0])



### FINAL MAtchfile
merge_df.isnull().sum(axis=1).value_counts()

## Add on the ZERO match between files
domain_1s = pd.DataFrame({
        'domainid':np.setdiff1d(domain_df['domainid'], merge_df['domainid'].dropna().unique())
    ,   'REAid':np.NaN
    ,   'nswgovid':np.NaN
    })
REA_1s = pd.DataFrame({
        'domainid':np.NaN
    ,   'REAid':np.setdiff1d(REA_df['REAid'], merge_df['REAid'].dropna().unique())
    ,   'nswgovid':np.NaN
    })
nswgov_1s = pd.DataFrame({
        'domainid':np.NaN
    ,   'REAid':np.NaN
    ,   'nswgovid':np.setdiff1d(nswgov_df['nswgovid'], merge_df['nswgovid'].dropna().unique())
    })
merge_df = pd.concat([
            merge_df
        ,   domain_1s
        ,   REA_1s
        ,   nswgov_1s
        ],axis=0
    )
print('number of row %d' % merge_df.shape[0])


#should be a lift in singles now aka isnull==2
merge_df.isnull().sum(axis=1).value_counts()

###### JOIN  columns
domain_cols = ['latitude','longitude','dateID','source',
               'Sale_type','sale_price',
               'baths','beds','parking','landSize','propertyType',
               'street','postcode','suburb','state']
REA_cols = ['latitude','longitude','dateID','source',
            'propertyType','constructionStatus',
            'sale_price','baths','beds','parking',
               'street','postcode','suburb','state']

nswgov_cols = ['STRATANONSTRATA','sale_price','dateID',
               'street','postcode','suburb']

domain_rename = dict(zip(domain_cols,['D_'+x for x in domain_cols]))
REA_rename = dict(zip(REA_cols,['R_'+x for x in REA_cols]))
nswgov_rename = dict(zip(nswgov_cols,['N_'+x for x in nswgov_cols]))


# 20170820:   877,252   
# 20171104: 1,006,768
# 20171116: 1,504,503       (reworked for nswgov and 3 joins)

fulljoin_df = merge_df
for source in sourceDF['source']:       # source = sourceDF['source'].iloc[2]
    print(source)
    fulljoin_df = pd.merge(
        fulljoin_df
    ,   globals()[source+'_df'][[source+'id']+globals()[source+'_cols']].rename(columns=globals()[source+'_rename'])
    ,   on = source+'id'
    ,   how='left'
    )
    # np.setdiff1d(globals()[source+'_df'].columns.values,globals()[source+'_cols'] )
    # np.setdiff1d(globals()[source+'_cols'],globals()[source+'_df'].columns.values )

### make sure dates are close
colid= ['domainid','REAid','nswgovid']
fulljoin_df['match_rate'] = fulljoin_df[colid].notnull().sum(axis=1)
fulljoin_df['match_rate'].value_counts()

###
col_df = pd.Series(fulljoin_df.columns)
col_mapping = col_df.str.split('[D|R|N]_',expand=True)
remap_df = col_mapping[1].value_counts().reset_index().rename(columns={1:'n'})
remap_col = remap_df.query('n > 1')['index']

for value in remap_col:
    print(value)
    chg_df = col_df[col_df.str.contains('[D|R|N]_'+value)]
    for idx,chg_col  in enumerate(chg_df):
        print(chg_col)
        if idx == 0:
            fulljoin_df[value] = fulljoin_df[chg_col]
        else:
            fulljoin_df[value] = fulljoin_df[value].fillna(fulljoin_df[chg_col])
    # drop columns
    fulljoin_df = fulljoin_df.drop(chg_df,axis=1)
##
## 20171231: 1455949
fulljoin_df.shape

fulljoin_df.isnull().sum(axis=0)/fulljoin_df.shape[0]

## clean
fulljoin_df = fulljoin_df.query('dateID==dateID')
## time factors
fulljoin_df['YYYYMM'] = fulljoin_df['dateID'].dt.strftime('%Y%m')
fulljoin_df['YYYYQ'] = fulljoin_df['dateID'].dt.strftime('%Y').astype(int)*10 + np.ceil(fulljoin_df['dateID'].dt.strftime('%m').astype(float)/3).astype(int)
fulljoin_df['YYYYQ'] = fulljoin_df['YYYYQ'].astype(str)

##
fulljoin_df.to_csv(master_dir + '/'+dateid+ '_final_df.csv',index=False)












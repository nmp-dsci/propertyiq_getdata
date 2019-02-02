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
auhouse_df = pd.read_csv(master_dir  + '/'+'20171231'+'_Auhouseprice.csv')
domain_df = pd.read_csv(master_dir  + '/'+dateid+'_domain.csv')
REA_df = pd.read_csv(master_dir  + '/'+dateid+'_realestate.csv')
nswgov_df = pd.read_csv("/Users/macmac/Documents/Property/20180116 NSWGOV_data/03 output_data/nswgovDF.csv" )



print('View Domain and Realestate Fields')
print(domain_df.isnull().sum(axis=0)/domain_df.shape[0]*1.0)
print(REA_df.isnull().sum(axis=0)/domain_df.shape[0]*1.0)
print(nswgov_df.isnull().sum(axis=0)/domain_df.shape[0]*1.0)

#### Format NSWGOV
nswgov_df = nswgov_df.rename(columns={'contract_date':'dateID'
                                      ,'property_ID':'nswgovid'
                                      ,'area_size':'landSize'
                                      })

nswgov_df = nswgov_df.drop(['Unnamed: 0','download_date'],axis=1,errors='ignore')


## AUHOUSE
auhouse_df = auhouse_df.rename(columns={
        'bedrooms':'beds'
    ,   'bathrooms':'baths'
    ,   'carpark':'parking'
    })

######################
## Create dateID
REA_df['dateID'] = pd.to_datetime(REA_df['dateID']).dt.strftime('%Y-%m-%d')
domain_df['dateID'] = pd.to_datetime(domain_df['dateID'],format='%d %b %Y').dt.strftime('%Y-%m-%d')
nswgov_df['dateID'] = pd.to_datetime(nswgov_df['dateID'])

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
        'HIGHWAY','CR','ST','DR','RD','AVE','AV','CL','CT','WAY','LOT']
    # aggregate to ID level
    addr_DF2 = addr_DF.groupby(list(addr_DF.columns.values)).size()
    addr_DF2 = addr_DF2.reset_index().drop(0,axis=1)
    addr_DF2.index = addr_DF2[idcol]
    ## pull out street
    street_addr = addr_DF2['street'].str.upper().str.split('/',expand=True )
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
# manually create this for NSWGOV
nswgov_df['street'] = nswgov_df['subdwelling_no'].apply(lambda x: str(x)+'/' if pd.notnull(x) else ''
         ) + nswgov_df['street_no'].str.replace(' ','') + ' ' + nswgov_df['street_name']
nswgov_df = nswgov_df.query('street==street')
addr_nswgov = street_formater(nswgov_df[['nswgovid','street','suburb','postcode']],idcol='nswgovid')
# AU HOUSE PRICE
auhouse_df = auhouse_df.rename(columns={'ID':'auhouseid','DateID','dateID'})
auhouse_df['subdwelling_no'] = auhouse_df['sub0'].fillna('') +' '+ auhouse_df['sub1'].fillna('')
auhouse_df['subdwelling_no'] = auhouse_df['subdwelling_no'].str.strip()
auhouse_df['subdwelling_no'] = auhouse_df['subdwelling_no'].apply(lambda x: x+'/' if len(x) > 0 else x)
auhouse_df['street'] = auhouse_df['subdwelling_no']+auhouse_df['streetNo']+' '+auhouse_df['street']
auhouse_df['street'] = auhouse_df['street'].str.upper()
auhouse_df['suburb'] = auhouse_df['suburb'].str.upper()
auhouse_df = auhouse_df.drop_duplicates('ID',keep='first')
addr_auhouse = street_formater(auhouse_df[['auhouseid','street','suburb','postcode']],idcol='auhouseid')


# put in override
addr_domain['SubDwelling'] = addr_domain['SubDwelling'].fillna('999999')
addr_REA['SubDwelling'] = addr_REA['SubDwelling'].fillna('999999')
addr_nswgov['SubDwelling'] =addr_nswgov['SubDwelling'].fillna('999999')
addr_auhouse['SubDwelling'] =addr_auhouse['SubDwelling'].fillna('999999')

# adhoc fixes
addr_nswgov['postcode'] = addr_nswgov['postcode'].astype(int)


addr_REA['SubDwelling'].str.len().value_counts()
addr_domain['SubDwelling'].str.len().value_counts()
addr_nswgov['SubDwelling'].str.len().value_counts()
addr_auhouse['SubDwelling'].str.len().value_counts()

addr_REA['SubDwelling'] = addr_REA['SubDwelling'].apply(lambda x: '999999' if len(x)>6 else x)
addr_domain['SubDwelling'] = addr_domain['SubDwelling'].apply(lambda x: '999999' if len(x)>6 else x)
addr_nswgov['SubDwelling'] = addr_nswgov['SubDwelling'].apply(lambda x: '999999' if len(x)>6 else x)
addr_auhouse['SubDwelling'] = addr_auhouse['SubDwelling'].apply(lambda x: '999999' if len(x)>6 else x)

### join all files
join_cols = ['value','type_str','SubDwelling','postcode']
sourceDF = pd.DataFrame({'source':['domain','REA','nswgov','auhouse'],'dummy':1})
matches = pd.merge(sourceDF,sourceDF,on='dummy',how='inner').query('source_x<>source_y ')
matches = matches.query('source_x < source_y')


REA_df['dateID'] = pd.to_datetime(REA_df['dateID'])
domain_df['dateID'] = pd.to_datetime(domain_df['dateID'])
nswgov_df['dateID'] = pd.to_datetime(nswgov_df['dateID'])
auhouse_df['dateID'] = pd.to_datetime(auhouse_df['dateID'])


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
    # merge_dfs.query('nswgovid == 4089597')
    ## test4089597
    #aa = globals()['addr_'+sx][[sx+'id']+join_cols]
    #bb = globals()['addr_'+sy][[sy+'id']+join_cols]
    ## Get match rate
    merge_match = merge_dfs.groupby([sx+'id',sy+'id','type_str']).size().unstack('type_str')
    merge_match['match'] = merge_match.isnull().sum(axis=1)
    merge_match = merge_match.query('match==0')
    merge_match = merge_match.reset_index()
    ## Date Filter
    for ss in [sx,sy]:
        merge_match = pd.merge(
                merge_match
            ,   globals()[ss+'_df'][[ss+'id','dateID']].rename(columns={'dateID':ss+'_dateID'})
            ,   on = ss+'id'
            ,   how='left'
            )
    merge_match = merge_match.drop([0,1,'match'],axis=1)
    merge_match['DateDiff'] = (merge_match[sx+'_dateID'] - merge_match[sy+'_dateID']).apply(lambda x: abs(x.days) if pd.notnull(x) else 999999 )
    if 'auhouse' not in [sx,sy]:
        merge_match = merge_match.query('DateDiff < 60')
    # dedup via min date
    merge_match = pd.merge(
            merge_match
        ,   merge_match.groupby(sx+'id')['DateDiff'].min().reset_index()
        ,   on=[sx+'id','DateDiff']
        ,   how ='inner'
        ).drop('DateDiff',axis=1)
    print('number of row %d' % merge_match.shape[0])
    # merge_match[sx+'id'].value_counts().value_counts()
    ##
    ## remove dups
    ##
    if merge_df.shape[0]==0:
        merge_df = merge_match
    else:
        merge_df = pd.merge(merge_df
                ,   merge_match
                ,   on = list(np.intersect1d(list(merge_df.columns),list(merge_match.columns)))
                ,   how='outer')
    print('number of row %d' % merge_df.shape[0])



### FINAL MAtchfile
merge_df.isnull().sum(axis=1).value_counts()

## subset postcodes
keep_poa = pd.read_csv(output_directory+'99 oztam_mapping.csv')

## Add on the ZERO match between files
domain_1s = pd.DataFrame({
        'domainid':np.setdiff1d(
          domain_df.query('postcode in  '+ str(list(keep_poa['postcode'])))['domainid']
        , merge_df['domainid'].dropna().unique())
    ,   'REAid':np.NaN
    ,   'nswgovid':np.NaN
    })
REA_1s = pd.DataFrame({
        'domainid':np.NaN
    ,   'REAid':np.setdiff1d(
        REA_df.query('postcode in  '+ str(list(keep_poa['postcode'])))['REAid']
        , merge_df['REAid'].dropna().unique())
    ,   'nswgovid':np.NaN
    })
nswgov_1s = pd.DataFrame({
        'domainid':np.NaN
    ,   'REAid':np.NaN
    ,   'nswgovid':np.setdiff1d(
            nswgov_df.query('postcode in  '+ str(list(keep_poa['postcode'])))['nswgovid']
        ,   merge_df['nswgovid'].dropna().unique()
        )
    })
single_df = pd.concat([
           domain_1s
        ,   REA_1s
        ,   nswgov_1s
        ],axis=0
    )

print('number of row %d' % single_df.shape[0])
for source in sourceDF.query('source<>"auhouse"')['source']:       # source = sourceDF['source'].iloc[2]
    print(source)
    print(globals()[source+'_df'][[source+'id','dateID']
        ].query('dateID==dateID and '+source+'id=='+source+'id').isnull().sum(axis=1).value_counts())
    single_df = pd.merge(single_df
        ,   globals()[source+'_df'][[source+'id','dateID']
        ].query('dateID==dateID and '+source+'id=='+source+'id').rename(columns={'dateID':source+'_dateID'})
        ,   on=source+'id'
        ,   how='left'
        )
print('Check for Missing values is Single Match DF')
print(single_df.isnull().sum(axis=1).value_counts())
single_df =single_df[single_df.isnull().sum(axis=1) == 4]


print('number of row %d' % single_df.shape[0])

merge_df = pd.concat([merge_df,single_df],axis=0)

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
nswgov_cols = ['district_code','landSize','zoning',
               'sale_price','dateID',
               'postcode','suburb']
auhouse_cols = ['baths','beds','parking',
                'latitude','longitude'
                ]


domain_rename = dict(zip(domain_cols,['domain_'+x for x in domain_cols]))
REA_rename = dict(zip(REA_cols,['REA_'+x for x in REA_cols]))
nswgov_rename = dict(zip(nswgov_cols,['nswgov_'+x for x in nswgov_cols]))
auhouse_rename = dict(zip(auhouse_cols,['auhouse_'+x for x in auhouse_cols]))

# 20170820:   877,252   
# 20171104: 1,006,768
# 20171116: 1,504,503       (reworked for nswgov and 3 joins)
# 20180304: 1,043,076       (enhanced all extraction and Full JOIN DATEID * SOURCE)

fulljoin_df = merge_df
for source in sourceDF['source']:       # source = sourceDF['source'].iloc[2]
    print(source)
    fulljoin_df = pd.merge(
        fulljoin_df
    ,   globals()[source+'_df'][[source+'id']+globals()[source+'_cols']].rename(columns=globals()[source+'_rename'])
    ,   on = [source+'id',source+'_dateID'] if source <> 'auhouse' else [source+'id']
    ,   how='left'
    )
    # np.setdiff1d(globals()[source+'_df'].columns.values,globals()[source+'_cols'] )
    # np.setdiff1d(globals()[source+'_cols'],globals()[source+'_df'].columns.values )

### make sure dates are close
    
colid= list(sourceDF.source+'id')
fulljoin_df['match_rate'] = fulljoin_df[colid].notnull().sum(axis=1)
print('FULL JOIN Match Rates')
print(fulljoin_df['match_rate'].value_counts())

###
col_df = pd.Series(fulljoin_df.columns)
col_mapping = col_df.str.replace(''+'|'.join(sourceDF.source),'').str.strip('_')
remap_df = col_mapping.value_counts().reset_index().rename(columns={0:'n'}).query('index<>"id"')
remap_col = remap_df.query('n > 1')['index']

for value in remap_col:
    print(value)
    chg_df = col_df[col_df.str.contains('['+'|'.join(sourceDF.source)+']_'+value)]
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
## 20180304: 1857064 reworked now = 1,065,253
fulljoin_df.shape

print('missing Rates for FULL JOIN')
print(fulljoin_df.isnull().sum(axis=0)/fulljoin_df.shape[0])

## clean
## time factors
fulljoin_df['YYYYMM'] = fulljoin_df['dateID'].dt.strftime('%Y%m')
fulljoin_df['YYYYQ'] = fulljoin_df['dateID'].dt.strftime('%Y').astype(int)*10 + np.ceil(fulljoin_df['dateID'].dt.strftime('%m').astype(float)/3).astype(int)
fulljoin_df['YYYYQ'] = fulljoin_df['YYYYQ'].astype(str)

fulljoin_df['domainid'].value_counts().value_counts()
fulljoin_df['REAid'].value_counts().value_counts()
fulljoin_df['nswgovid'].value_counts().value_counts()
fulljoin_df['auhouseid'].value_counts().value_counts()

##
fulljoin_df.to_csv(master_dir + '/'+dateid+ '_final_df.csv',index=False)





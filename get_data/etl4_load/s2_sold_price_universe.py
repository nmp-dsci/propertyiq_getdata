#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sun Oct  8 20:12:02 2017

@author: macmac

Pre-requisites: 
    (1) run all the code for Sydney Property Scrap 01a-01c
    (2) NSW_Gov scrpe


"""

### IMPORT Libraries
import pandas as pd
import numpy as np
import re,time,os
import multiprocessing as mp
import time,datetime,math

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
print('Pull in DATA')
sourceDF = pd.DataFrame({'source':[
    'domain'
,   'REA'
,   'nswgov'
,   'auhouse_rent'
,   'auhouse_auction'
],'dummy':1})

for source in sourceDF.query('source != "nswgov"').source:
    print(source)
    globals()[source+'_df'] = pd.read_csv(master_dir+ '/'+dateid+'_'+source+'.csv')
    print(globals()[source+'_df'].shape)
    print(globals()[source+'_df'].isnull().sum(axis=0)/globals()[source+'_df'].shape[0]*1.0)
    for col in list(globals()[source+'_df'].columns):
        print(col)
        if globals()[source+'_df'][col].dtype == object:
            globals()[source+'_df'][col] = globals()[source+'_df'][col].astype(str).str.strip('b').str.strip("'")
            globals()[source+'_df'][col] = globals()[source+'_df'][col].str.replace('nan','')
            globals()[source+'_df'][col] = globals()[source+'_df'][col].str.replace(',','').str.strip()
            globals()[source+'_df'][col] = globals()[source+'_df'][col].apply(lambda x: np.NaN if x=='' else x)


###################################
# nsw is different
nswgov_df = pd.read_csv("/Users/macmac/Documents/Property/20180116 NSWGOV_data/03 output_data/nswgovDF.csv" )

#### Format NSWGOV
nswgov_df = nswgov_df.rename(columns={'contract_date':'dateID'
                                      ,'property_ID':'nswgovid'
                                      ,'area_size':'landSize'
                                      })

nswgov_df = nswgov_df.drop(['Unnamed: 0','download_date'],axis=1,errors='ignore')

# manually create this for NSWGOV
nswgov_df['street'] = nswgov_df['subdwelling_no'].apply(lambda x: str(x)+'/' if pd.notnull(x) else ''
         ) + nswgov_df['street_no'].str.replace(' ','') + ' ' + nswgov_df['street_name']
nswgov_df = nswgov_df.query('street==street')



###################################
## AUHOUSE_RENT formatting

auhouse_rent_df = auhouse_rent_df.rename(columns={
        'bedrooms':'beds'
    ,   'bathrooms':'baths'
    ,   'carpark':'parking'
    ,   'ID':'auhouse_rentid'
    ,   'DateID':'dateID'
    })

# for address matching

auhouse_rent_df['subdwelling_no'] = auhouse_rent_df['sub0'].fillna('') +' '+ auhouse_rent_df['sub1'].fillna('')
auhouse_rent_df['subdwelling_no'] = auhouse_rent_df['subdwelling_no'].str.strip()
auhouse_rent_df['subdwelling_no'] = auhouse_rent_df['subdwelling_no'].apply(lambda x: x+'/' if len(x) > 0 else x)
auhouse_rent_df['street'] = auhouse_rent_df['subdwelling_no']+auhouse_rent_df['streetNo']+' '+auhouse_rent_df['street']
auhouse_rent_df['street'] = auhouse_rent_df['street'].str.upper()
auhouse_rent_df['suburb'] = auhouse_rent_df['suburb'].str.upper()
auhouse_rent_df = auhouse_rent_df.drop_duplicates('auhouse_rentid',keep='first')


####################################
### auhouse_auction_df formatting
auhouse_auction_df = auhouse_auction_df.rename(columns = {'href_street':'street'})

auhouse_auction_df['auhouse_auctionid'] = auhouse_auction_df['href_addr'].str.extract('/(\d+)/')
auhouse_auction_df['auhouse_auctionid'].value_counts().value_counts()

auhouse_auction_df.groupby(['auhouse_auctionid','dateID']).size().value_counts()
auhouse_auction_df.groupby(['auhouse_auctionid']).size().value_counts()

auhouse_auction_df= auhouse_auction_df.drop_duplicates('auhouse_auctionid',keep='first')

######################
## Create dateID

REA_df['dateID'] = pd.to_datetime(pd.to_datetime(REA_df['dateID']).dt.strftime('%Y-%m-%d'))
domain_df['dateID'] = pd.to_datetime(pd.to_datetime(domain_df['dateID'],format='%d %b %Y').dt.strftime('%Y-%m-%d'))
nswgov_df['dateID'] = pd.to_datetime(nswgov_df['dateID'])
auhouse_rent_df['dateID'] = pd.to_datetime(auhouse_rent_df['dateID'])
auhouse_auction_df['dateID'] = pd.to_datetime(auhouse_auction_df['dateID'])

## 

domain_df.sale_price = domain_df.sale_price.apply(lambda x: np.NaN if x in ['Price Withheld'] else x)

domain_df.sale_price = domain_df.sale_price.str.replace('SOLD - ','')

domain_df.sale_price = domain_df.sale_price.astype(float)

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

#### Format for street formatter
for source in sourceDF.source:
    print('Checking Address Standardisation: %s_df' % source)
    globals()[source+'_df']['street'] = globals()[source+'_df']['street'].str.upper()
    print(globals()[source+'_df']['street'].head())

##########################################
### Split address

# addr_DF = domain_df[['domainid','street','suburb','postcode']];idcol='domainid'
# addr_DF = realestate_df[['realestateID','street','suburb','postcode']];idcol='realestateID'
# addr_DF = nswgov_df[['nswgovID','street','suburb','postcode']];idcol='nswgovID'

def street_formater(addr_DF = domain_df[['domainid','street','suburb','postcode']],idcol='domainid'):
    ##
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
    street_addr = pd.merge(street_addr,street_addr.groupby(idcol)['variable'].max().reset_index(),on=[idcol],how='left')
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
    ,   how='inner')
    ##
    addr_DF2.index = [x for x in range(addr_DF2.shape[0])]
    street_ms = pd.merge(
        street_ms
    ,   addr_DF2[[idcol,'suburb','postcode']]
    ,   on = idcol
    ,   how = 'inner')
    return street_ms


#### files

addr_domain = street_formater(domain_df[['domainid','street','suburb','postcode']],idcol='domainid')
addr_REA = street_formater(REA_df[['REAid','street','suburb','postcode']],idcol='REAid')
addr_nswgov = street_formater(nswgov_df[['nswgovid','street','suburb','postcode']],idcol='nswgovid')
addr_auhouse_rent = street_formater(auhouse_rent_df[['auhouse_rentid','street','suburb','postcode']],idcol='auhouse_rentid')
addr_auhouse_auction = street_formater(auhouse_auction_df[['auhouse_auctionid','street','suburb','postcode']],idcol='auhouse_auctionid')

# put in override

addr_domain['SubDwelling'] = addr_domain['SubDwelling'].fillna('999999')
addr_REA['SubDwelling'] = addr_REA['SubDwelling'].fillna('999999')
addr_nswgov['SubDwelling'] =addr_nswgov['SubDwelling'].fillna('999999')
addr_auhouse_rent['SubDwelling'] =addr_auhouse_rent['SubDwelling'].fillna('999999')
addr_auhouse_auction['SubDwelling'] =addr_auhouse_auction['SubDwelling'].fillna('999999')


#### Format for street formatter

addr_formats = pd.DataFrame({'column':pd.Series([],dtype=str)})
for source in sourceDF.source:
    print('Addr_match TABLE format: addr_%s' % source)
    #fixes
    globals()['addr_'+source]['postcode'] = globals()['addr_'+source]['postcode'].astype(float)
    globals()['addr_'+source]['SubDwelling'] = globals()['addr_'+source]['SubDwelling'].str.strip()
    globals()['addr_'+source]['SubDwelling'] = globals()['addr_'+source]['SubDwelling'].fillna('999999')
    # final check for standardised formant
    df_fmt = globals()['addr_'+source].dtypes.reset_index(
            ).rename(columns={'index':'column',0:source})
    addr_formats = pd.merge(
            addr_formats
        ,   df_fmt
        ,   on='column'
        ,   how='outer'
        )


### join all files
join_cols = ['value','type_str','SubDwelling','postcode']
matches = pd.merge(sourceDF,sourceDF,on='dummy',how='inner').query('source_x!=source_y ')
matches = matches.query('source_x < source_y')


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
    if np.sum(['auhouse' in x for x  in [sx,sy]])>0:
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

merge_df.to_csv(master_dir+'/'+dateid+'_dataset_matchDF.csv')

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
        ]
    ,axis=0)

print('number of row %d' % single_df.shape[0])
for source in sourceDF.query('source not in  ["auhouse_rent","auhouse_auction"]')['source']:       # source = sourceDF['source'].iloc[2]
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
merge_df = pd.concat([merge_df,single_df],axis=0,sort=False)

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

auhouse_rent_df = auhouse_rent_df.rename(columns={'price_str':'rent_price'})
auhouse_rent_cols = ['baths','beds','parking',
                'latitude','longitude','rent_price']


domain_rename = dict(zip(domain_cols,['domain_'+x for x in domain_cols]))
REA_rename = dict(zip(REA_cols,['REA_'+x for x in REA_cols]))
nswgov_rename = dict(zip(nswgov_cols,['nswgov_'+x for x in nswgov_cols]))
auhouse_rent_rename = dict(zip(auhouse_rent_cols,['auhouse_rent_'+x for x in auhouse_rent_cols]))

# 20170820:   877,252
# 20171104: 1,006,768
# 20171116: 1,504,503       (reworked for nswgov and 3 joins)
# 20180304: 1,043,076       (enhanced all extraction and Full JOIN DATEID * SOURCE)
# 20190202:   856,550       ( didn't run auction listing related data)

fulljoin_df = merge_df
for source in sourceDF.query('source not in ["auhouse_auction"]')['source']:       # source = sourceDF['source'].iloc[2]
    print(source)
    fulljoin_df = pd.merge(
        fulljoin_df
    ,   globals()[source+'_df'][[source+'id']+globals()[source+'_cols']].rename(columns=globals()[source+'_rename'])
    ,   on = [source+'id',source+'_dateID'] if source != 'auhouse_rent' else [source+'id']
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
remap_df = col_mapping.value_counts().reset_index().rename(columns={0:'n'}).query('index!="id"')
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
## 20171231: 1,455,949
## 20180304: 1,857,064 reworked now = 1,065,253
## 20190202:   856,550
fulljoin_df.shape

print('missing Rates for FULL JOIN')
print(fulljoin_df.isnull().sum(axis=0)/fulljoin_df.shape[0])

## clean
## time factors
fulljoin_df['dateID'].isnull().value_counts()
fulljoin_df = fulljoin_df.query('dateID == dateID')


fulljoin_df['YYYYMM'] = fulljoin_df['dateID'].dt.strftime('%Y%m')
fulljoin_df['YYYYQ'] = fulljoin_df['dateID'].dt.strftime('%Y').astype(int)*10 + np.ceil(fulljoin_df['dateID'].dt.strftime('%m').astype(float)/3).astype(int)
fulljoin_df['YYYYQ'] = fulljoin_df['YYYYQ'].astype(str)

fulljoin_df['domainid'].value_counts().value_counts()
fulljoin_df['REAid'].value_counts().value_counts()
fulljoin_df['nswgovid'].value_counts().value_counts()
fulljoin_df['auhouse_rentid'].value_counts().value_counts()
# fulljoin_df['auhouse_auctionid'].value_counts().value_counts()

#### Ad work done from HA to clean up DF
fulljoin_df = fulljoin_df.rename(columns={'auhouse_rent_rent_price':'rent_price'})

##
fulljoin_df.to_csv(master_dir + '/'+dateid+ '_final_df.csv',index=False)



######################
## enhanced

## found information for auhouse_auction
# 1.0* merge_df['auhouse_auctionid'].nunique()/auhouse_auction_df['auhouse_auctionid'].nunique()

###### Columns to pull accross for Auction data

domain_cols = ['latitude','longitude',
               'baths','beds','parking','landSize','propertyType',
               'street','postcode','suburb','state']
REA_cols = ['latitude','longitude','propertyType',
                'baths','beds','parking']
nswgov_cols = ['landSize']
auhouse_rent_cols = ['baths','beds','parking','latitude','longitude']

auhouse_auction_match = merge_df.query('auhouse_auctionid==auhouse_auctionid')
drop_dateid = pd.Series(auhouse_auction_match.columns)
drop_dateid = drop_dateid[drop_dateid.str.contains('dateID')]
auhouse_auction_match = auhouse_auction_match.drop(drop_dateid,axis=1)

for source in sourceDF.query('source not in ["auhouse_auction"]')['source']:       # source = sourceDF['source'].iloc[2]
    print(source)
    auhouse_auction_match = pd.merge(
        auhouse_auction_match
    ,   globals()[source+'_df'][[source+'id']+globals()[source+'_cols']].rename(columns=globals()[source+'_rename'])
    ,   on = source+'id'
    ,   how='left'
    )

# ### column the factors
col_df = pd.Series(auhouse_auction_match.columns)
col_mapping = col_df.str.replace(''+'|'.join(sourceDF.source),'').str.strip('_')
remap_df = col_mapping.value_counts().reset_index().rename(columns={0:'n'}).query('index!="id"')
remap_col = remap_df.query('n > 1')['index']

for value in remap_col:
    print(value)
    chg_df = col_df[col_df.str.contains('['+'|'.join(sourceDF.source)+']_'+value)]
    for idx,chg_col  in enumerate(chg_df):
        print(chg_col)
        if idx == 0:
            auhouse_auction_match[value] = auhouse_auction_match[chg_col]
        else:
            auhouse_auction_match[value] = auhouse_auction_match[value].fillna(auhouse_auction_match[chg_col])
    # drop columns
    auhouse_auction_match = auhouse_auction_match.drop(chg_df,axis=1)



##
## Pull to auhouse_auctionid level (dedup)

auhouse_auction_match2 = auhouse_auction_match.groupby('auhouse_auctionid')[remap_col.values].max()
auhouse_auction_match2 = auhouse_auction_match2.reset_index()

auhouse_auction_df2 = pd.merge(
        auhouse_auction_df
    ,   auhouse_auction_match2
    ,   on='auhouse_auctionid'
    ,   how='left'
    )

auhouse_auction_df2['YYYYMM'] = auhouse_auction_df2['dateID'].dt.strftime('%Y%m')
auhouse_auction_df2['match'] = auhouse_auction_df2['propertyType'].notnull().astype(int)
# auhouse_auction_df2.groupby('YYYYMM')['match'].mean().plot(kind='line')
# auhouse_auction_df2.groupby('YYYYMM')['clearance_rate'].mean().plot(kind='line')
# auhouse_auction_df2.groupby(['YYYYMM','bedrooms'])['clearance_rate'].mean().unstack('bedrooms')[[0,1,2,3,4]].plot(kind='line')
# auhouse_auction_df2.groupby(['YYYYMM','property_type'])['clearance_rate'].mean().unstack('property_type').plot(kind='line',figsize=(12,12))


auhouse_auction_df2.to_csv(master_dir+'/'+dateid+'_auhouse_auction_enhanced.csv')

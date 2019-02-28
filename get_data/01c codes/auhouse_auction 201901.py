
### IMPORT Libraries
import pandas as pd
import numpy as np
import re,time,os, time,datetime, math

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
final_dir  = output_directory + '01c Property_DF'
master_dir = output_directory + '01e Master_DF'


poa_sub = pd.read_csv(output_directory+'00 POA_SUBURB.csv')
poa_sub['suburb'] = poa_sub['suburb'].str.lower()
poa_sub['type'] = poa_sub['type'].str.strip()
poa_sub = poa_sub.query('type=="Delivery Area"')


## Get data
dateid = '20190202'
sourceID = 'auhouse_auction'
versionID = '1'
scrape_area_dir = output_directory + '01a Region href property/'+ sourceID +'_v' + versionID
suburb_dir =  output_directory + '01b Suburb_Files/'+ sourceID +'_v' + versionID

#######################################################################
# Build Master

suburb_files = pd.DataFrame({'suburb':os.listdir(suburb_dir)})
suburb_files['size'] = suburb_files['suburb'].apply(lambda x: os.stat(suburb_dir+'/'+x).st_size)
suburb_files = suburb_files.query('suburb != ".DS_Store"  and size > 100')

print('STEP 1: BUILD MASTER SET OF UPDATE')
master_df = pd.DataFrame()
for suburb in suburb_files['suburb'].values:         # suburb = suburb_files.values[0]
    print(suburb)
    suburb_df = pd.read_csv(suburb_dir +'/'+ suburb)
    suburb_df['url'] = suburb
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)

master_df = master_df.drop('Unnamed: 0',axis=1)


print('MAX auction date in dataset:"{}"'.format(master_df.url.str.extract('NSW_(\d{4}-\d{2}-\d{2}).*',expand=False).max()))

print('Run some checks on the aggregated data')
print('Check1: size')
# 20180613: 122,923
print(master_df.shape)
print('Check2: ID row FReqy')
## Dups are okay, same house Passed in at Auction multiple times
print(master_df['href_addr'].value_counts().value_counts())
#master_df.query('href_addr=="https://www.auhouseprices.com/auction/result/NSW/36268539/5+Sunset+Bvd%2C+Tweed+Heads+West+NSW+2485/"')


### cleanup of RESULT_CODe
result_mapping = pd.Series({
        "S":"sold"
    ,   "SP":"property sold prior"
    ,   "SA":"sold after auction"
    ,   "SB":"sold before auction"
    ,   "SN":"sold not disclosed"
    ,   "SS":"sold after auction price not disclosed"
    ,   "PN":"sold prior not disclosed"
    ,   "Private":"private sale"
    ,   "PI":"property passed in"
    ,   "NB":"no bid"
    ,   "VB":"vendor bid"
    ,   "W":"withdrawn prior to auction"
    ,   "N/A":"price not available"
    ,   "Passed In":"property passed in"
    }).reset_index().rename(columns={'index':'result_code',0:'auction_result'})

master_df['result_code'] = master_df['result_code'].str.strip()
master_df = pd.merge(master_df,result_mapping,on='result_code',how='left' )
# cehck result , should be not missing
master_df['auction_result'].value_counts(dropna=False)
master_df.query('auction_result!=auction_result')['result_code']

### Clean up of Sale price
master_df['sold_price'].notnull().value_counts(normalize=True)
master_df['sold_price'] = master_df['sold_price'].str.replace('[$,]','').astype(float)

# Clearance rate
sold_vars = ['S','SP','SA','SB','SN','SS','PN','Private','N/A']
pass_vars = ['PI','NB','VB','W','Passed In']
master_df['clearance_rate'] = master_df['result_code'].apply(lambda x: 1 if x in sold_vars else 0 )

## Extract DATE
master_df['dateID'] = master_df['url'].str.extract('(\d{4}-\d{2}-\d{2})',expand=False)
#master_df['dateID'].str.extract('(.*) \d{4}-\d{2}-\d{2}').value_counts()

master_df['state'] = master_df['postcode'].str.extract('(.*)\d{4}',expand=False).str.strip()
master_df['postcode'] = master_df['postcode'].str.extract('(\d{4})',expand=False).str.strip()

## Fix for missing suburb
master_df['suburb'] = master_df['suburb'].str.lower().str.strip()

master_df.query('postcode!=postcode')['suburb'].value_counts()

missing_suburb = {  
    'bilgola plateau':'bilgola'
,   'avalon beach':'avalon'
,   'east beecroft':'beecroft'
}

for sub in missing_suburb.keys():
    master_df['suburb'] = master_df['suburb'].apply(lambda x: missing_suburb[sub] if x == sub else x)

master_df = pd.merge(
        master_df
    ,   poa_sub[['suburb','state','postcode']].rename(columns={'postcode':'postcode2','state':'state2'})
    ,   on='suburb'
    ,   how='left'
    )

print('Missing Postcode')
print(pd.crosstab(master_df['postcode2'].isnull(),master_df['postcode'].isnull()))
# map saved postcodes
master_df['postcode'] = master_df['postcode'].fillna(master_df['postcode2'])
master_df['state'] = master_df['state'].fillna(master_df['state2'])
# clean up
master_df = master_df.query('postcode==postcode').drop(['state2','postcode2'],axis=1)


master_df.isnull().sum(axis=0)


# 20180613:   rows: 171,317
# 20190202:   rows: 196,231
master_df.to_csv(final_dir  + '/'+sourceID+'_v'+versionID+'.csv',index=False)
# master_df = pd.read_csv(final_dir  + '/'+dateid+'_domain_all.csv')

## on master for merging
master_df.to_csv(master_dir+'/'+dateid+'_'+sourceID+'.csv',index=False)

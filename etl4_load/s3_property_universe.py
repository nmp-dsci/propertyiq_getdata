# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import numpy as np
import pandas as pd
import os,time
import geopy.distance

pd.options.display.max_columns= 40

# directory / Get data
property_dir = "/Users/macmac/Documents/Property/"
station_dir = property_dir + ""
home_dir = property_dir+"20151207 Scape Sydney/"
data_dir = home_dir + '01e Master_DF'
clean_dir = home_dir + '01f propertyIQ'
geocode_dir = property_dir+'20180811 geo_data/'

### Data Scrape DATE
vDateID = pd.Series(os.listdir(data_dir)).str.extract('(\d{8})',expand=False).dropna().max()

# SA4 mapping
poa_map = pd.read_csv(home_dir+'/03 HA_final_data/03 poa_sa4_mapping.csv')

### REGION of INTEREST
regions = [
        'Sydney - Sutherland'
    ,   'Central Coast'
    ,   'Sydney - North Sydney and Hornsby'
    ,   'Sydney - Inner South West'
    ,   'Sydney - Parramatta'
    ,   'Illawarra'
    ,   'Sydney - City and Inner South'
    ,   'Sydney - Outer West and Blue Mountains'
    ,   'Sydney - Eastern Suburbs'
    ,   'Sydney - Northern Beaches'
    ,   'Sydney - Outer South West'
    ,   'Sydney - Blacktown'
    ,   'Sydney - South West'
    ,   'Sydney - Baulkham Hills and Hawkesbury'
    ,   'Sydney - Inner West'
    ,   'Sydney - Ryde'
    ]
poa_map  = poa_map.query('SA4_NAME_2011 in ' + str(regions))

### pull data
data_topics = {
            'sale'      :   'final_df'
        ,   'rent'      :   'auhouse_rent'
        ,   'auction'   :   'auhouse_auction_enhanced'
    }

for k in data_topics.keys(): # k = 'rent'
    print('Pulling data for: "%s"' % k)
    globals()[k+'_data'] = pd.read_csv(data_dir+'/'+vDateID+'_'+data_topics[k]+'.csv')
    globals()[k+'_data'] = globals()[k+'_data'].merge(
       poa_map[['POSTCODE','SA4_NAME_2011']].rename(columns={'POSTCODE':'postcode'}),on='postcode',how ='inner')

"""
        SALE DATA PROCESSING
"""

date_range = {  'minDateID': pd.to_datetime('20120101',format = '%Y%m%d').strftime('%Y-%m-%d')
            ,   'maxDateID': pd.to_datetime('20190131',format = '%Y%m%d').strftime('%Y-%m-%d')}

sale_data = sale_data.query('street == street')
sale_data['street'] = sale_data['street'].str.lower()

###
# sale_data
# auction_data
# rent_data

### PROPERTY TYPE

auction_data.property_type = auction_data.property_type.str.lower()
sale_data.propertyType = sale_data.propertyType.str.lower()
rent_data.propertyType = rent_data.propertyType.str.lower()


pd.DataFrame({
    'sale':sale_data.propertyType.value_counts(dropna=False,normalize=True)
,   'auction':auction_data.property_type.value_counts(dropna=False,normalize=True)
,   'rent':rent_data.propertyType.value_counts(dropna=False,normalize=True)
})


property_types = { 
    'house':['house','terrace']
,   'apartment':['unit','apartment','studio','flat/unit/apartment']
,   'semi detached':['townhouse','villa','duplex','semi']
,   'land':['land']
}


for k in property_types.keys():
    print(k)
    auction_data.property_type = auction_data.property_type.apply(
            lambda x: k if x in property_types[k] else x)
    rent_data.propertyType = rent_data.propertyType.apply(
            lambda x: k if x in property_types[k] else x)

auction_data.property_type = auction_data.property_type.apply(lambda x: 'other' if x not in property_types.keys() else x)    
rent_data.propertyType = rent_data.propertyType.apply(lambda x: 'other' if x not in property_types.keys() else x)    


pd.DataFrame({
    'sale':sale_data.propertyType.value_counts(dropna=False,normalize=True)
,   'auction':auction_data.property_type.value_counts(dropna=False,normalize=True)
,   'rent':rent_data.propertyType.value_counts(dropna=False,normalize=True)
})

auction_data = auction_data.rename(columns={'property_type':'propertyType'})
    


######################3
## 2. Prepare SAles data
######################

#### unique Identifier
print('Dimentions of sale_data: ' + str(sale_data.shape) )         # (697170, 40)
# Get counts of contributing datasources
id_cols = ['domainid','nswgovid','REAid','auhouse_auctionid','auhouse_rentid']
sale_data[id_cols].notnull().mean(axis=0)

sale_data[id_cols].notnull().corr()

#### View Match rate
sale_data['match_rate'].value_counts(normalize= True)

## view unique count of variables match rate to videw skews
sale_data.groupby('match_rate')[id_cols].nunique()

####################
#   2. Pre Pencil
####################

#### A. Create any fields
# 1. Propertytype
sale_data['street'] = sale_data['street'].str.replace('\s+',' ')

### clean up street column
sale_data['street'].nunique()                                                # 1,012,695
sale_data['street'].str.upper().nunique()                                    #   989,764
sale_data['street'].str.upper().str.replace('[^A-Z0-9 ]','').nunique()       #   977,004
sale_data['street'] = sale_data['street'].str.upper().str.replace('[^A-Z0-9/ ]','')

# has Digit
sale_data['streetD'] = sale_data['street'].str.contains('[0-9]').astype(int)
sale_data = sale_data.query('streetD==1')

## Create StreetID for quicker aggregation calculation
streetID_map = sale_data.groupby('street').size().reset_index().drop(0,axis=1)
streetID_map['streetID'] = range(streetID_map.shape[0])

sale_data = pd.merge(sale_data, streetID_map, on='street',how='left')

##### Final columns to run with 

sale_data = sale_data.rename(columns={
        'domain_Sale_type':'Sale_type'
    ,   'landSize':'land_size'
    ,   'REA_constructionStatus':'construction_status'
    ,   'propertyType':'property_type'
    ,   'nswgov_district_code':'district_code'
    ,   'nswgov_zoning':'nswgov_zoning'
    })

#-1.60201
sale_data['land_size'] = sale_data['land_size'].fillna(-1.60201)

### format sale-type
sale_data['Sale_type'].value_counts(dropna=False)
sale_data['Sale_type'] = sale_data['Sale_type'].apply(lambda x: 'private treaty' if 'Sold by private treaty' == x else x)
sale_data['Sale_type'] = sale_data['Sale_type'].apply(lambda x: 'private treaty' if 'Sold prior to auction' == x else x)
sale_data['Sale_type'] = sale_data['Sale_type'].apply(lambda x: 'auction' if 'Sold at auction' == x else x)
sale_data['Sale_type'] = sale_data['Sale_type'].apply(lambda x: 'unknown' if pd.isnull(x) or x == 'Sold' else x)

### suburb
sale_data['suburb'] = sale_data['suburb'].str.lower()
sale_data['suburb'] = sale_data['suburb'].str.replace('[+-]',' ').str.lower()
sale_data['suburb'] = sale_data['suburb'].str.replace("'","")

print('check no weird stuff like commas in the suburb')
sale_data['suburb'][sale_data['suburb'].str.contains('[^a-z ]')].value_counts()

uniqID = ['SA4_NAME_2011','postcode','suburb','streetID','street','dateID','longitude','latitude']
print('NEED TO ADD the new factors here')
descID = ['baths','beds','parking','sale_price',
          'Sale_type','land_size','construction_status','property_type',
          'district_code','nswgov_zoning']

sale_data[uniqID].isnull().sum(axis=0)
sale_data[uniqID+descID].dtypes

## sale price only
#sale_data = sale_data.query('sale_price == sale_price')

## Properties with 0 bed  etc are LAND

sale_data.query('baths!=baths')['property_type'].value_counts()
sale_data[['baths','beds','parking']] = sale_data[['baths','beds','parking']].fillna(0.0)


sale_data[uniqID+descID].isnull().sum(axis=0)

print('there grouper fieldnames cannot be null')
sale_data[uniqID].isnull().sum(axis=0)

# create the summary 

s = time.time()
sale_data_summ = sale_data.groupby(uniqID)[descID].max()
e = time.time()
print('Time Taken %d seconds' % ( e-s))     


# 336 seconds with aggregation on 'street' as character string ... slow computer
# 336 seconds with aggregation on 'street' as numeric ID ... slow computer
# 20190215: time 704 seconds for 373,945 rows
## 

sale_data_summ = sale_data_summ.reset_index()
sale_data_summ = sale_data_summ.reset_index()

print('CHECK for missing values')
print(sale_data_summ.isnull().sum(axis=0))

print('CHECK column names and make then NLP FRIENDLY')
sale_data_summ = sale_data_summ.rename(columns={
        'baths':'bathrooms'
    ,   'beds':'bedrooms'
        })

sale_data_summ['postcode'] = sale_data_summ['postcode'].astype(int)

### 400k records
### 618k records 20180524
### 438269 records 20180722
### Subset for date range of interest! 241k 
### 20190215: 302,823

sale_data_summ['dateID'] = pd.to_datetime(sale_data_summ['dateID'])
sale_data_summ = sale_data_summ.query('dateID >= "'+date_range['minDateID']+'" and dateID < "'+date_range['maxDateID']+'"')

"""
    ############################################
            RENTAL DATA SUMMARY
    ############################################

"""

# 2. rename columns
rent_data = rent_data.rename(columns={
       'price_str':'rent'
    ,   'carpark':'parking'
    ,   'propertyType':'property_type'
    ,   'sale_date':'dateID'
    })  

# 5. subset for date range of interest   # 627.5k
rent_data.dateID = pd.to_datetime(rent_data.dateID,format='%d %b %Y')
rent_data = rent_data.query('dateID >= "'+date_range['minDateID']+'" and dateID <= "'+date_range['maxDateID']+'"')

# subset

rent_data = rent_data.query('street==street')

## Create StreetID for quicker aggregation calculation

streetID_map = rent_data.groupby('raw_addr').size().reset_index().drop(0,axis=1)
streetID_map['streetID'] = range(streetID_map.shape[0])
rent_data = pd.merge(rent_data, streetID_map, on='raw_addr',how='left')


# BUILD street
#rent_data['street'] = rent_data.apply(lambda x: 
#        '/'.join(pd.Series([
#            ''.join(pd.Series([x.sub0,x.sub1]).dropna().astype(str))
#            , '' if pd.isnull(x.streetNo) else str(x.streetNo)]).astype(str))+' '+ x.street_orig, axis=1)
#
#####

uniqID = ['SA4_NAME_2011','postcode','suburb','streetID','street',
          'dateID','longitude','latitude']
descID = ['property_type','bathrooms','bedrooms','parking','rent']

rent_data[uniqID+descID].isnull().sum(axis=0)
rent_data[uniqID+descID].dtypes

# create the summary 

s = time.time()
rent_data_summ = rent_data.groupby(uniqID)[descID].max()
e = time.time()
print('Time Taken %d seconds' % ( e-s)) 

### 20180700: for 623.5k rows this took = 311 seconds
### 20180700: for 935070 rows this took = 430 seconds
### 20190202: 540 seconds /783,440 rows

rent_data_summ = rent_data_summ.reset_index()
rent_data_summ = rent_data_summ.reset_index()

"""
    ############################################
            AUCTION DATA SUMMARY
    ############################################

"""

# 1. prepare dateid
auction_data.dateID = pd.to_datetime(auction_data.dateID,format='%Y-%m-%d')
# 2. rename columns
auction_data = auction_data.rename(columns={
       'ID':'streetID'  
   ,    'sold_price':'auction_price'
   ,   'carpark':'parking'
    ,   'propertyType':'property_type'
   ,   'sale_date':'dateID'
    })


# 3. put rent on an annual level so you can calulate yields
# 5. subset for date range of interest   # 627.5k
auction_data.dateID = pd.to_datetime(auction_data.dateID)
auction_data = auction_data.query('dateID >= "'+date_range['minDateID']+'" and dateID <= "'+date_range['maxDateID']+'"')
## map street id
## Create StreetID for quicker aggregation calculation
streetID_map = auction_data.groupby('href_addr').size().reset_index().drop(0,axis=1)
streetID_map['streetID'] = range(streetID_map.shape[0])
auction_data = pd.merge(auction_data, streetID_map, on='href_addr',how='left')


#####

uniqID = ['SA4_NAME_2011','postcode','suburb','streetID','dateID']
descID = ['property_type','bedrooms','clearance_rate','auction_price']

auction_data[uniqID+descID].isnull().sum(axis=0)
auction_data[uniqID+descID].dtypes

auction_data['propertyType'] = auction_data.property_type.iloc[:,0]
auction_data = auction_data.drop('property_type',axis=1).rename(columns={'propertyType':'property_type'})

s = time.time()
auction_data_summ = auction_data.groupby(uniqID)[descID].max()
e = time.time()
print('Time Taken %d seconds' % ( e-s))     


### for 623.5k rows this took = 311 seconds
### for 935070 rows this took = 430 seconds
auction_data_summ = auction_data_summ.reset_index()
auction_data_summ = auction_data_summ.reset_index()

"""
#########################################################
##          MERGE DATA SOURCES
#########################################################
"""

check_formats = pd.concat([
        sale_data_summ.dtypes
     ,  rent_data_summ.dtypes
     ,  auction_data_summ.dtypes
    ],axis=1,sort=False)

#check_formats.query('rent==rent and sale==sale and rent<> sale')
#check_formats.query('rent==rent and sale==sale')

## Identify SOURCE
rent_data_summ['source'] = 'R'
sale_data_summ['source'] = 'S'
auction_data_summ['source'] = 'A'

## STREET ID to different billion
rent_data_summ.streetID = rent_data_summ.streetID + 1000000000
sale_data_summ.streetID = sale_data_summ.streetID + 2000000000
auction_data_summ.streetID = auction_data_summ.streetID + 3000000000

## Index ID to different billion
rent_data_summ['index'] = rent_data_summ['index'] + 1000000000
sale_data_summ['index'] = sale_data_summ['index'] + 2000000000
auction_data_summ['index'] = auction_data_summ['index'] + 3000000000

# 20180304: 860k dataset
# 20180524: 1,390,670 dataset
# 20180722: ?,???,??? dataset
# 20190202: 1,239,700 
property_data = pd.concat([
        rent_data_summ
    ,   sale_data_summ
    ,   auction_data_summ
],axis=0,sort=False)
#

# property_data['dateID'] = pd.to_datetime(property_data['dateID'])
print('CHECK missing is only unique to RESPONSES (rent/ price)' )
print(property_data.isnull().sum(axis=0))


property_data['value'] = property_data['sale_price'].fillna(property_data['rent'])
property_data['land_size'] = property_data['land_size'].fillna(-1.60201)
property_data['rent'] = property_data['rent'].fillna(-1.60201)
property_data['sale_price'] = property_data['sale_price'].fillna(-1.60201)
property_data['value'] = property_data['value'].fillna(-1.60201)

property_data['Sale_type'] = property_data['Sale_type'].fillna('Unknown')
# property_data['construction_status'] = property_data['construction_status'].fillna('Unknown')
property_data['district_code'] = property_data['district_code'].fillna('Unknown')
# property_data['nswgov_zoning'] = property_data['nswgov_zoning'].fillna('Unknown')

property_data['sold_missing'] = property_data['sale_price'].apply(lambda x: 1 if x == -1.60201 else 0)

print('CHECK missing is only unique to RESPONSES (rent/ price)' )
print(property_data.isnull().sum(axis=0))


"""         WRITE TO FILE       """

property_data.to_csv(clean_dir+'/01 Property_Summary.csv',index=False)

property_data.head().to_csv(clean_dir+'/01 Property_Summary_Summary.csv',index=False)

"""
TAGGING CLOSEST STATION
"""


property_data = pd.read_csv(clean_dir+'/01 Property_Summary.csv')
poa_station_xy = pd.read_csv(geocode_dir+'postcode_station_xy.csv')

distance_cap = 5
poa_station_xy = poa_station_xy.query('distance < {}'.format(distance_cap)) # keep stations within 5km 
poa_station_xy.suburb = poa_station_xy.suburb.str.upper()


##

s = time.time()
property_station = property_data.merge(
        poa_station_xy[['postcode','station','station_lat','station_lng']]
    ,   on='postcode'   ,   how='left')
e = time.time()
print('Time Taken %d seconds' % ( e-s))  

# 20190215: 31 seconds

property_station.latitude.isnull().value_counts()

## calculate distince
# check missing
# pd.crosstab(property_station.latitude.isnull(),property_station.longitude.isnull())
# pd.crosstab(property_station.station_lng.isnull(),property_station.station_lat.isnull())


def geo_df(df=pd.DataFrame()):
    df.distance = df.apply(lambda x: geopy.distance.vincenty(
    (x['latitude'],x['longitude']),(x['station_lat'],x['station_lng'])).km\
    if x['latitude'] == x['latitude'] and x['station_lat'] == x['station_lat'] else np.NaN,axis=1)
    return df

property_station['distance'] = np.NaN

import multiprocessing as mp
cores = 4

s_time = time.time()
p = mp.Pool(cores)
pool_results = p.map(geo_df, np.array_split(property_station,cores))
p.close()
p.join()
response_ll = pd.DataFrame()
for result in pool_results:
    response_ll = pd.concat([response_ll,result],axis=0)
   
e_time = time.time()
print("step 1: time taken %s seconds" % (np.round(e_time-s_time,4)))


# 201700: time taken === 660 seconds (8 cores and 5km max)
# 20190202: time taken === 504 seconds  (4 cores and 5km max)


## Dedup closest station
response_ll.distance = response_ll.distance.apply(lambda x: distance_cap if x > distance_cap or x!=x else x)

response_ll['station_rank'] = response_ll.sort_values(
        ['distance'],ascending=True
        ).groupby('index').cumcount()

response_ll = response_ll.query('station_rank==0')


"""         WRITE TO FILE       """

response_ll.to_csv(clean_dir+'/01b Property_station.csv',index=False)

## write sample

response_ll.head().to_csv(clean_dir+'/01b Property_station_header.csv',index=False)



#
#
### Plot 1
#volume_df = property_data.groupby(['YYYY','source'])['streetID'].nunique().unstack('source')
#volume_df['rent%'] = 1.0 * volume_df.S / volume_df.R
#plt.figure()
#volume_df['rent%'].plot(kind='bar')
#plt.title('Volumes of Sydney property Rent and Sale listings')
#
### PLOT 2
#poa_yield = property_data.groupby(['postcode','YYYY','source'])['value'].mean().astype(int).unstack('source')
#poa_yield['yield'] = 1.0* poa_yield['R']/poa_yield['S']
#poa_yield = poa_yield.reset_index()
#
#poa_S_growth = poa_yield.groupby('postcode')['S'].describe()[['min','max']]
#(poa_S_growth['max'] / poa_S_growth['min']-1).sort_values(ascending=False)
#
#plt.figure()
#poa_yield['yield'].plot(kind='bar')
#plt.title('Volumes of Sydney property Rent and Sale listings')
#
#
#
#poa_yield.query('postcode==2092')
#
#
##### PULL OUT EXAMPLE
#poa_eg = data_summ.query('postcode == 2258')
#### Create YYYY + QQ
#poa_eg['YYYYQQ'] = pd.to_datetime(poa_eg['DateID'],format = '%Y-%m-%d').dt.strftime('%Y') + \
#np.ceil(pd.to_datetime(poa_eg['DateID'],format = '%Y-%m-%d').dt.strftime('%m').astype(int)/3.0).astype(int).astype(str)
#poa_eg['beds_C'] = poa_eg['beds_C'].apply(lambda x: 4 if x> 4 else x )
#
#
#grp_vars = ['YYYYQQ']
#poa_eg.query('YYYYQQ > "20120"').groupby(grp_vars)['price'].describe()['50%'].plot(kind = 'bar',stacked=True,figsize=(12,8))
#




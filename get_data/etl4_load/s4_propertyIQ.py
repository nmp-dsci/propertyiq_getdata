#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 24 09:47:15 2018

@author: nathanphillips
"""

import numpy as np
import pandas as pd
import os,time

pd.options.display.max_columns= 40

# directory / Get data
property_dir = "/Users/macmac/Documents/Property/"
station_dir = property_dir + ""
home_dir = property_dir+"20151207 Scape Sydney/"
data_dir = home_dir + '01e Master_DF'
clean_dir = home_dir + '01f propertyIQ'

### Data Scrape DATE
vDateID = pd.Series(os.listdir(data_dir)).str.extract('(\d{8})',expand=False).dropna().max()

#### CALL IN DATA
data = pd.read_csv('{a}/01b Property_station.csv'.format(a=clean_dir))

data = data.drop(['station_rank','station_lng','station_lat',
    'latitude','longitude'],axis=1)
data.suburb = data.suburb.str.lower()

### Cap bedrooms bathrooms and parking
print(' View bathrooms')
data.groupby(['source','bathrooms']).size().unstack('source')
data['bathrooms'] = data['bathrooms'].apply(lambda x: 9999 if x != x or x >100 else x)
data['bathrooms'] = data['bathrooms'].apply(lambda x: 4 if x > 4 and x < 100 else x)
data['bathrooms'] = data['bathrooms'].apply(lambda x: 0 if x < 0 else x)
data['bathrooms'] = data['bathrooms'].astype(float).astype(int).astype(str)
# data['bathrooms'] = data['bathrooms'].apply(lambda x:  x + ' bathrooms' if x!='9999' else 'Unknown')
data.bathrooms.value_counts()

print(' View bedrooms')
data.groupby(['source','bedrooms']).size().unstack('source')
data['bedrooms'] = data['bedrooms'].apply(lambda x: 9999 if x != x or x >100 else x)
data['bedrooms'] = data['bedrooms'].apply(lambda x: 4 if x > 4 and x < 100 else x)
data['bedrooms'] = data['bedrooms'].apply(lambda x: 0 if x < 0 else x)
data['bedrooms'] = data['bedrooms'].astype(float).astype(int).astype(str)
# data['bedrooms'] = data['bedrooms'].apply(lambda x:  x + ' bedrooms' if x!='9999' else 'Unknown')
data.bedrooms.value_counts()

print(' View parking')
data.groupby(['source','parking']).size().unstack('source')
data['parking'] = data['parking'].apply(lambda x: 9999 if x != x or x >100 else x)
data['parking'] = data['parking'].apply(lambda x: 3 if x > 3 and x < 100 else x)
data['parking'] = data['parking'].apply(lambda x: 0 if x < 0 else x)
data['parking'] = data['parking'].astype(float).astype(int).astype(str)
# data['parking'] = data['parking'].apply(lambda x:  x + ' parkings' if x!='9999' else 'Unknown')
data.parking.value_counts()

print('source of the data')
data['number_of_rentals'] = data['source'].apply(lambda x: 1 if x == 'R' else 0)
data['number_of_sold'] = data['source'].apply(lambda x: 1 if x == 'S' else 0)
data['number_of_auctions'] = data['source'].apply(lambda x: 1 if x == 'A' else 0)

print('Postcode Standardisation')
# data['postcode'] = data.postcode.astype(int).apply(lambda x: 'postcode %d' % x )

print('Sale_type')
data['Sale_type'].value_counts()
data['Sale_type'] = data['Sale_type'].apply(lambda x: 'Unknown' if x == 'unknown' else x)
data['Sale_type'].value_counts()

print('Sale_type')
data['property_type'].value_counts()

print('clearance rate')
data.clearance_rate = data.clearance_rate.fillna(-1.60201)
data.auction_price = data.auction_price.fillna(-1.60201)

"""
   $$$$$$$$$$$$$$$$$$$$$$
   $$$ REMOVE OUTLIERS
   $$$$$$$$$$$$$$$$$$$$$$
"""

data.dateID = pd.to_datetime(data.dateID)
data['YYYY'] = data.dateID.dt.strftime('%Y')

outlier_df = data.query('value > 0').groupby(['YYYY','postcode','source']).agg({'value':[np.std,np.mean]})
outlier_df = outlier_df.reset_index()
outlier_df.columns = pd.Series(['-'.join(x) for x in outlier_df.columns]).str.strip('-')

data = pd.merge(data,outlier_df,on=['YYYY','postcode','source'],how='left')
data['z_score'] = (data['value']-data['value-mean'])/data['value-std']

data['outlier'] = data['z_score'].apply(lambda x: 1 if x > 3 else 0 )
data['outlier'].value_counts()
data['outlier'] = data['outlier'] * data['value'].apply(lambda x: 1 if x>0 else 0)
data['outlier'].value_counts()

data = data.query('outlier == 0')
data = data.drop(['z_score','outlier','value-mean','value-std','YYYY'],axis=1)

"""
   $$$$$$$$$$$$$$$$$$$$$$$$
   $$$ Confirmations
   $$$$$$$$$$$$$$$$$$$$$$$$
"""

data= data.rename(columns = {
    #     'bathrooms':'number_of_bathrooms'
    # ,   'bedrooms':'number_of_bedrooms'
    # ,   'parking':'number_of_carspace'
       'rent': 'weekly_rent'
    ,   'value':'investment_yield'
    })

responses = ['sale_price','annual_rent','weekly_rent','number_of_rentals','number_of_sold','sold_missing','investment_yield']


"""
   $$$$$$$$$$$$$$$$$$$$$$$$
   $$$ External Dataset ... SOURCE
   $$$$$$$$$$$$$$$$$$$$$$$$
"""

data = data.rename(columns = {'SA4_NAME_2011':'region'})

data['region'] = data['region'].str.replace('Sydney - ','').str.strip()
print(data['region'].value_counts())

renameDF = pd.DataFrame.from_records({
        '1': {'region':"North Sydney and Hornsby", 'rename':"North Shore"}
    ,   '2': {'region':"Parramatta", 'rename':"City of Parramatta"}
    ,   '3': {'region':"Sutherland", 'rename':"The Shire"}
    ,   '4': {'region':"Baulkham Hills and Hawkesbury", 'rename':"The Hills"}
    ,   '5': {'region':"Blacktown", 'rename':" Western Sydney"}
    ,   '6': {'region':"Ryde", 'rename':"City of Ryde"}
    }).T


data = pd.merge(data, renameDF, on='region', how='left')
data['region'] = data['rename'].fillna(data['region']).str.strip()
print(data['region'].value_counts())


"""
   $$$$$$$$$$$$$$$$$$$$$$$$
   $$$ BUILD SEGMENTS
   $$$$$$$$$$$$$$$$$$$$$$$$
"""

segment_factors = ['property_type','bedrooms','bathrooms','parking']
segment_df = data.groupby(segment_factors).size().reset_index().rename(columns={0:'n'})
segment_df['p'] = 1.0 * segment_df['n']/segment_df.n.sum()
segment_df = segment_df.sort_values('p',ascending=False)
segment_df = segment_df.query('n> 20000')
segment_df['segment'] = segment_df[segment_factors].apply(lambda x: ' '.join(x) , axis=1)

segment_df['segment'] = segment_df['segment'].str.replace(' bedrooms ','-')
segment_df['segment'] = segment_df['segment'].str.replace(' bathrooms ','-')
segment_df['segment'] = segment_df['segment'].str.replace(' parkings','')

data = pd.merge(
        data
    ,   segment_df[segment_factors + ['segment']]
    ,   on=segment_factors
    ,   how='left'
    )
data['segment'] = data['segment'].fillna('Other')

print(data['segment'].value_counts())

print(pd.crosstab(data['segment'],data['source']))

print(
    pd.crosstab(
        data['segment']
    ,   data['land_size'].apply(lambda x: False if x == -1.60201 else True)
    ,   normalize = 'index'
    ))

print(
    pd.crosstab(
        data['segment']
    ,   data['land_size'].apply(lambda x: False if x == -1.60201 else True)
    ,   normalize = False
    ))


"""
   $$$$$$$$$$$$$$$$$$$$$$$$
   $$$ OUTPUT DATA
   $$$$$$$$$$$$$$$$$$$$$$$$
"""

sample_data = pd.concat([
        data.query('source == "Rental Listing"' ).sample(5)
    ,   data.query('source == "Sold Listing"' ).sample(5)
    ]   ,axis = 0)

print('MAKE SURE NO MISSING')
print(data.isnull().sum(axis=0))

data = data.drop(['streetID','rename'],axis=1,errors='ignore')

## system filter for sold 

data['value-missing'] = data['investment_yield'].apply(lambda x: 1 if x > 0 else 0)

data['source_sold'] = (data['source'].apply(lambda x: 1 if x=="Sold Listing" else 0) * data['sale_price'].apply(lambda x: 1 if x > 0 else 0)
    ).apply(lambda x: 'use_field' if x == 1 else 'exclude')

data.query('postcode =="postcode 2060" and dateID>="2018-03-01" and source_sold =="use_field"')['sale_price'].mean()


#sample_data.to_csv(project_dir + '/property_data_'+vDateID+'_header_v'+vID+'.csv',index=False)
data.to_csv( clean_dir+ '/propertyIQ_'+vDateID+'.csv',index=False)


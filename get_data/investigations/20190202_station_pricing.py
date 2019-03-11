#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 22 18:48:09 2018

@author: macmac
"""


import numpy as np
import pandas as pd
import os,time
import matplotlib.pyplot as plt


pd.options.display.max_columns= 40

# directory / Get data
property_dir = "/Users/macmac/Documents/Property/"
station_dir = property_dir + ""
home_dir = property_dir+"20151207 Scape Sydney/"
data_dir = home_dir + '01e Master_DF'
clean_dir = home_dir + '01f propertyIQ'

dateid = int(pd.Series(os.listdir(data_dir)).str.extract('(\d{8})_final_df').dropna().max().iloc[0])

property_df = pd.read_csv(clean_dir+'/propertyIQ_{}.csv'.format(dateid))


property_df.dateID = pd.to_datetime(property_df.dateID)

property_df['YYYYMM'] = property_df.dateID.dt.strftime('%Y%m')

property_df['YYYY'] = property_df.dateID.dt.strftime('%Y')

property_df['QQ'] = 'Q'+np.ceil(property_df.dateID.dt.strftime('%m').astype(float)/3).astype(int).astype(str)


property_df['YYYYQQ'] = property_df['YYYY'] + property_df['QQ']


##
property_df.groupby('YYYYQQ').size().plot(kind='bar')

### Distance

property_df['station_distance'] = np.ceil(property_df.distance*10).astype(int)
property_df.station_distance = property_df.station_distance.apply(lambda x: x if x in range(0,16) else 16)
property_df.station_distance = property_df.station_distance*100
property_df.station_distance = property_df.station_distance.apply(lambda x: 400 if x < 400 else x)
property_df.station_distance = property_df.station_distance.apply(lambda x: 1000 if x > 1000 else x)
property_df.station_distance = property_df.station_distance.apply(lambda x: 700 if x>400 and  x < 1000 else x)

#################
###

property_df.YYYYMM = property_df.YYYYMM.astype(int)
property_df.YYYY = property_df.YYYY.astype(int)
  
  
###################### 

response = 'weekly_rent'

poa_f = 'suburb in ["thornleigh","pennant hills","normanhurst","hornsby","asquith"]'
poa_f = 'suburb in ["thornleigh"]'
prop_f = 'property_type in ["house"]'
resp_f = '{} !=-1.602010 '.format(response)
fact_f = 'bedrooms >=3 and bedrooms <= 3'
time_f = 'YYYYMM >= 201401'
fitlers = [poa_f,prop_f,resp_f,time_f,fact_f]

time= ['YYYY']
nonFilter = ['station_distance']

##3 plot 1
property_df.query(' & '.join(fitlers)
    ).groupby(time+nonFilter
    )[response].mean(
    ).unstack(nonFilter
    ).plot(kind='line'
    ,figsize=(10,8)
    ,title= "THORNLEIGH Average Rental Price BY distance from station for 3 bedroom House"
    )

#####################

response = 'sale_price'

poa_f = 'suburb in ["thornleigh","pennant hills","normanhurst","hornsby","asquith"]'
poa_f = 'suburb in ["thornleigh"]'
prop_f = 'property_type in ["house"]'
resp_f = '{} !=-1.602010 '.format(response)
fact_f = 'bedrooms >=3 and bedrooms <= 3'
time_f = 'YYYYMM >= 201401'
fitlers = [poa_f,prop_f,resp_f,time_f,fact_f]

time= ['YYYY']
nonFilter = ['station_distance']

##3 plot 1

property_df.query(' & '.join(fitlers)
    ).groupby(time+nonFilter
    )[response].mean(
    ).unstack(nonFilter
    ).astype(int).plot(kind='line'
    ,figsize=(10,8)
    ,title= "THORNLEIGH: Average Sale Price BY distance from station for 3 bedroom House"
    ,table=True
    )
plt.tick_params(axis='x', pad=20)
plt.tight_layout()


secondary_y

####################### 
# investigate land size

response = 'sale_price'

poa_f = 'suburb in ["thornleigh","pennant hills","normanhurst","hornsby","asquith"]'
poa_f = 'suburb in ["thornleigh"]'
prop_f = 'property_type in ["house"]'
resp_f = '{} !=-1.602010 '.format(response)
fact_f = 'bedrooms >=3 and bedrooms <= 3'
time_f = 'YYYYMM >= 201401'
land_f = 'land_size != -1.60201'
fitlers = [poa_f,prop_f,resp_f,time_f,fact_f,land_f]


property_df.query(' & '.join(fitlers)).plot(kind='scatter',x='land_size',y='sale_price')










property_df.query(' & '.join(fitlers)
    ).groupby(time+nonFilter).head()




## plot 2

cols = ['dateID','beds','baths','parking','sale_price','street']
investigate = data.query(' & '.join(fitlers)
    ).groupby(cols).size().reset_index().sort_values('dateID')

investigate['yyyy'] = investigate.dateID.dt.strftime('%Y')
investigate.sale_price = investigate.sale_price.astype(float)
investigate.groupby('yyyy')['sale_price'].median().plot()

investigate.query('beds>=1 & beds<5').groupby(['yyyy','beds'])['sale_price'].median().unstack('beds').plot(kind='line')
investigate.query('beds>=1 & beds<5').groupby(['yyyy','beds'])['sale_price'].size().unstack('beds').plot(kind='line')

investigate.query('beds==1 and yyyy=="2017"')

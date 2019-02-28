#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 22 18:48:09 2018

@author: macmac
"""

### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from urllib2 import urlopen,HTTPError
from httplib import IncompleteRead
import re
import time
import os
import multiprocessing as mp
import matplotlib.pyplot as plt
import time
import datetime
import math

pd.options.display.max_columns= 30

home_dir =  "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
data_dir = home_dir + '01e Master_DF'


dateid = pd.Series(os.listdir(data_dir)).str.extract('(\d{8})_final_df').max()

data = pd.read_csv(data_dir+'/'+dateid+'_final_df.csv')
oztam_map = pd.read_csv(home_dir+'99 oztam_mapping.csv')

# tag region
data = data.merge(oztam_map,on='postcode',how ='left')

#####
time_fields = ['YYYYMM','YYYYQ']
for i in time_fields: # i = time_fields[0]
    t_map = data.query('YYYYMM >= 201001').groupby(i).size().reset_index().drop(0,axis=1)
    t_map[i+'_f'] = range(t_map.shape[0])
    data = data.merge(t_map,on=i,how='left')


### find property
data.street = data.street.str.replace(' +',' ')  
data[data.street.str.lower().str.contains('17 +victoria').fillna(False)]

data.query('postcode==2043 & YYYYQ=="20182" & propertyType=="house"')



#################
###
    
    
poa_f = 'postcode in [2010,2015]'
prop_f = 'propertyType in ["house","semi detached"]'
resp_f = 'sale_price==sale_price'
fact_f = 'beds >=0 and beds <= 3'
time_f = 'YYYYMM >= 201001'
fitlers = [poa_f,prop_f,resp_f,time_f,fact_f]

##3 plot 1
data.query(' & '.join(fitlers)
    ).groupby(['YYYYQ_f','beds'
    ]
    ).sale_price.mean(
    ).unstack('beds'
    ).plot(kind='line',figsize=(10,8))


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

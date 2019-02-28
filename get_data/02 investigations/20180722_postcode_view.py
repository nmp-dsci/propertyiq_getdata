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

### land size view
data.landSize.notnull().value_counts()
data.nswgov_zoning.notnull().value_counts()


#################
###
poa_f = 'suburb in ["NORMANHURST","THORNLEIGH","PENNANT HILLS"]'
#poa_f = ' postcode==2560'
#poa_f = ''
prop_f = 'propertyType in ["house"]'
#prop_f = ''
resp_f = 'sale_price==sale_price'
fact_f = 'beds >=2 and beds <= 5'
time_f = 'YYYYMM >= 201301'
land_f = 'landSize==landSize'
#zoning_f =  'nswgov_zoning in ["R2","A","R1","R3"]'
zoning_f = ''
fitlers = pd.Series([poa_f,prop_f,resp_f,time_f,fact_f,zoning_f,land_f])

data.YYYYQ = data.YYYYQ.astype(str)
data['YYYY'] = data.YYYYQ.str.slice(0,4)
data['landcut'] =data.landSize.apply(lambda x: 4 if x > 1400 else 3 if x > 1000 else 2 if x > 700 else 1 )

nonfilter = 'landcut'

data.query(' & '.join(fitlers[fitlers!=''])
    ).groupby(['YYYY',nonfilter]
    ).sale_price.mean(
    ).unstack(nonfilter
    ).plot(kind='line',figsize=(10,8))




















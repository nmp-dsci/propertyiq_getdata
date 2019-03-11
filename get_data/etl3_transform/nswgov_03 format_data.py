#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Fri May 18 06:52:25 2018

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

home_dir = "/Users/macmac/Documents/Property/20180116 NSWGOV_data/"
os.listdir(home_dir)

input_dir = home_dir + '02 output_data'
os.listdir(input_dir)

output_dir = home_dir + '03 output_data'
os.listdir(output_dir)

dateid = '20180517'



## PULL in records and do analysis
rtype = 'B'
recordDF = pd.read_csv(input_dir+'/record_'+rtype+'_'+dateid+'.csv')

recordDF.notnull().sum(axis=0)/recordDF.shape[0]
recordDF.head()
recordDF['sale_code'].value_counts()
recordDF['sale_pctn'].describe()
recordDF.dtypes

keep_cols = pd.Series({
    ## additional information
        'area_size':[]
    ,   'area_type':[]
    ,   'zoning':[]
    ,   'property_purpose':[]
    ,   'property_nature':[]
    # property information
    ,   'dealing_no':[]
    ,   'district_code':[]
    ,   'property_ID':[]
    ,   'property_name':[]
    # sale information
    ,   'sale_price':[]
    ,   'contract_date': []
    ,   'download_date': []
    # address information
    ,   'subdwelling_no':[]
    ,   'street_no':[]
    ,   'street_name':[]
    ,   'suburb':[]
    ,   'postcode':[]
    ,   'strata_lot':[]
    })

nswgovDF = recordDF[keep_cols.keys()]

# foramt date
nswgovDF['download_date'] = pd.to_datetime(nswgovDF['download_date'],format='%Y%m%d %H:%M')

nswgovDF['contract_date'] = pd.to_datetime(nswgovDF['contract_date'],format='%Y%m%d',errors='coerce')
nswgovDF['contract_date'] = nswgovDF['contract_date'].fillna(pd.to_datetime(nswgovDF['download_date'].dt.strftime('%Y-%m-%d')))
print('SHOULD all be FALSE')
print(nswgovDF['contract_date'].isnull().value_counts())

# format area
nswgovDF['area_type'].value_counts(dropna=False)
nswgovDF['area_size'] = nswgovDF['area_size'] * nswgovDF['area_type'].fillna(0.0).apply(lambda x: 1000.0 if x=='H' else 1.0 if x=='M' else x)
nswgovDF = nswgovDF.drop('area_type',axis=1)
#

### Duplicates.
nswgovDF['strata_lot'].isnull().value_counts()
nswgovDF['strata_lot'] = nswgovDF['strata_lot'].fillna(999999)

dups_check = nswgovDF.groupby(['property_ID','strata_lot','sale_price']).size()
print('Dup Check 1')
print(dups_check.value_counts())

## First Priority DeDup
dedupDF =  nswgovDF.groupby(['property_ID','strata_lot','sale_price'])['download_date'].max().reset_index()
nswgovDF = pd.merge(nswgovDF,dedupDF,on=['property_ID','strata_lot','sale_price','download_date'],how='inner')

print('Dup Check 2')
dups_check = nswgovDF.groupby(['property_ID','strata_lot','sale_price']).size()
print(dups_check.value_counts())
dups_check[dups_check==2]

nswgovDF = nswgovDF.drop_duplicates(['property_ID','strata_lot','sale_price'],keep='first')

nswgovDF.query('property_ID ==4096546 and strata_lot== 999999 and sale_price==8435477')

nswgovDF.to_csv(output_dir+ '/nswgovDF_'+dateid+'.csv')













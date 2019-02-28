#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sun May 13 20:14:50 2018

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
diri = home_dir + "00 data"
os.listdir(diri)

output_dir =  home_dir  + '01 output_data'
if os.path.exists(output_dir) == False:
    os.mkdir(output_dir)

## YYYY range
yyyy_range = pd.DataFrame({'YYYY':os.listdir(diri)})
yyyy_range = yyyy_range[yyyy_range.YYYY.str.contains('\d{4}')]
yyyy_range.YYYY = yyyy_range.YYYY.astype(int)
yyyy_range = yyyy_range.query('YYYY>2011')


## record_type_mapping: from 
dat_mapping = pd.read_csv(home_dir+'NSWGOV_dat_mapping_20180516.csv')
# create regex extract mapping
#dat_mapping['fillna'] = dat_mapping['fillna'].fillna('')
#dat_mapping['fillna'] = dat_mapping['fillna'].apply(lambda x: '|'+x if x==';;' else x)
dat_mapping['fillna'] = dat_mapping['fillna'].apply(lambda x: '' if pd.isnull(x) else '|')

dat_mapping = dat_mapping.sort_values(['record_type','fieldID'])
dat_mapping['record_type'] = dat_mapping['record_type'].str.upper()

dat_mapping['field_pattern'] = '(?P<'+dat_mapping['fieldName']+'>[^;]+' + dat_mapping['fillna'] + ')'
record_regex = dat_mapping.groupby('record_type').agg({'field_pattern':lambda x: ';'.join(x)}).reset_index()

###
for yyyy in yyyy_range.YYYY: # yyyy =2012
    print(yyyy)
    yyyy_dir = diri + '/' + str(yyyy)
    ymd_range = pd.DataFrame({'YMD':os.listdir(yyyy_dir)})
    ymd_range = ymd_range[ymd_range.YMD.str.contains('(\d{8})|([A-z]+ \d{2}, \d{4})')]
    #if ymd_range.YMD.str.contains('([A-z] \d{2}, \d{4})').sum()>0:
    #    ymd_range.YMD = pd.to_datetime(ymd_range.YMD.str.extract('([A-z]+ \d{2}, \d{4})'),format='%B %d, %Y')
    #    ymd_range.YMD = ymd_range.YMD.dt.strftime('%Y%m%d')
    for ymd in ymd_range.YMD:
        print(ymd)
        if os.path.exists(output_dir + '/output_' + ymd+'.csv')==False:
            ymd_dir = yyyy_dir + '/' + ymd
            files = pd.Series(os.listdir(ymd_dir))
            files = files[files.str.contains('.DAT')]
            print('Files to extract: %d' % files.shape[0])
            file_extract = pd.DataFrame()
            for f in files: # f = files.iloc[0]
                print(f)    
                ## pull data
                with open(ymd_dir+'/'+f) as fff:
                    raw_dat = pd.DataFrame({'raw':pd.Series(fff.readlines(1))})
                #Tag regex
                raw_dat['record_type'] = raw_dat['raw'].str.split(';',expand=True)[0]
                raw_dat = pd.merge(raw_dat,record_regex,on='record_type',how='left')
                if raw_dat['field_pattern'].isnull().sum() > 0 :
                    print("ERROR: don't have all RECORD TYPE MAPPING")
                ## TEST extract
                #raw_dat['raw'].loc[[1]].str.extract(raw_dat['field_pattern'].loc[1],expand=False)
                test = raw_dat.apply(lambda x: re.findall(x['field_pattern'],x['raw']),axis=1)
                text_extract = test.apply(lambda x: len(x))
                if [0] in text_extract.value_counts(normalize=True).index.values and text_extract.value_counts(normalize=True).loc[0] > 0.1:
                    print("ERROR: dont have REGEX DOWN PROPERLY")
                ### Apply REGEX
                extractDF = pd.DataFrame()
                for idx in raw_dat.index.values: # idx=raw_dat.index.values[0]
                    series = raw_dat['raw'].loc[[idx]].str.extract(raw_dat['field_pattern'].loc[idx],expand=False)
                    extractDF = pd.concat([
                        extractDF
                    ,   series.reset_index().melt(id_vars = ['index','record_type'])
                    ],axis=0,ignore_index=True)
                extractDF['value'] = extractDF['value'].apply(lambda x: np.NaN if x=='' else x)
                extractDF.query('record_type =="Z"')
                #extractDF = extractDF.query('value==value')
                extractDF['DAT'] = f
                ## check for a pulse on extraction
                file_extract = pd.concat([file_extract,extractDF],axis=0,ignore_index=True)
            ## write csv
            file_extract.to_csv(output_dir + '/output_' + ymd+'.csv',index=False)
                



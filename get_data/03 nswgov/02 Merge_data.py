#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu May 17 18:35:32 2018

@author: macmac
"""


### IMPORT Libraries
import pandas as pd
import numpy as np
import re,time, os
import time,datetime,math

home_dir = "/Users/macmac/Documents/Property/20180116 NSWGOV_data/"
os.listdir(home_dir)

diri = home_dir + '01 output_data'
os.listdir(diri)

output_dir = home_dir + '02 output_data'
os.listdir(output_dir)

dateid = '20180517'


files = pd.Series(os.listdir(diri))
files = files[files.str.contains('output_')]

### CREATE MASTER FILE

master = pd.DataFrame()
for f in files:
    print(f)
    fdf = pd.read_csv(diri +'/'+ f)
    master = pd.concat([master,fdf],axis=0)

master.to_csv(output_dir+'/ALLrecords_'+dateid+'.csv',index=False)

### SPLIT this master file into record types
for rtype in ['A','B','C','D','Z']:  # rtype = 'B'
    print('record type: %s' % rtype)
    recordDF = master.query('record_type =="'+rtype+'"')
    #recordDF = pd.pivot_table(recordDF,index=['DAT','index'],columns='variable',values = 'value',aggfunc=np.max)
    recordDF['index'] = recordDF['DAT']+'__' +recordDF['index'].astype(str)
    recordDF = recordDF.drop_duplicates(['index','variable'],keep='first')
    #recordDF.groupby('index').size().value_counts()
    recordDF = recordDF.pivot(index='index',columns='variable',values = 'value').reset_index()
    recordDF.to_csv(output_dir+'/record_'+rtype+'_'+dateid+'.csv',index=False)
    





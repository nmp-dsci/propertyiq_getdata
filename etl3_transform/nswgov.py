#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sun May 13 20:14:50 2018

@author: macmac

Pre-requisites
    (1) go to valuation website and download and unzip all the files needed


"""

### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import re
import time
import requests, zipfile
import os
import matplotlib.pyplot as plt
import time
import datetime
import math


sourceid = 'nswgov'
home_dir = f'../../data/propertyiq_getdata/{sourceid}'
input_dir = f'{home_dir}/output_etl2'
output_dir = f'{home_dir}/output_etl3'

outputdf_dir = f'{output_dir}/{sourceid}_df.csv'

if os.path.exists(outputdf_dir) == False:
    print("NEW")
    sale_df = pd.DataFrame()
    output_files = os.listdir(input_dir)
else: 
    print("EXISTING")
    sale_df = pd.read_csv(outputdf_dir)
    output_files = np.setdiff1d(os.listdir(input_dir),sale_df['fn_src'])



for fn in output_files: 
    print(fn)
    fn_df = pd.read_csv(f'{input_dir}/{fn}')
    fn_df['fn_src'] = fn
    fn_df = fn_df.query('record_type == "B"')
    fn_df = fn_df.query('label == label')
    fn_df['index'] = fn_df['index'].astype(str)
    fn_df2 = fn_df.groupby(['file','fn_src','ymd','index','label'])['value'].max().unstack('label')
    fn_df2 = fn_df2.reset_index()
    print(f'saving file = "{fn}" with {fn_df2.shape[0]} rows')
    if fn_df2.shape[0] == 0 : 
        print('ZERO rows added, investigate')
        break
    sale_df = pd.concat([sale_df,fn_df2],axis=0,ignore_index=True)



# ## write csv
print(f'saving file = {sale_df.shape[0]} rows')

sale_df.to_csv(f'{output_dir}/{sourceid}_df.csv',index=False)




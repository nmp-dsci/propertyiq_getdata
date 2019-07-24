#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 11 20:48:00 2018

@author: macmac
"""

### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import re,time,os,sys
import time,datetime,math

sys.path.append('/Users/macmac/Documents/GitHub/propertyiq_getdata')

from config import * 
from utils import * 


sourceid = 'auhouse_auction'

scrape_area_dir = output_directory + '01a Region href property/'+ sourceid 

project_dir =  output_directory + '01b Suburb_Files/'+ sourceid 
if os.path.exists(project_dir) ==False:
    os.mkdir(project_dir)

## PUll list of files that need to be placed into 1b
files_df = os.listdir(scrape_area_dir)
complete = list(pd.Series(os.listdir(project_dir)).str.replace('.csv','.txt'))
files_df = np.setdiff1d(files_df,complete )

for url in files_df:        # url = 'NSW_2018-06-09_p1.txt'
    print(url)
    # get data
    rawdata = open(scrape_area_dir + '/' + url,"r").read()
    soup = BeautifulSoup(rawdata)
    ## FIND MAX
    find_max = soup.findAll("li", { "class" : "active" })
    find_max = pd.Series(find_max)
    find_max = find_max.apply(lambda x: x.text)
    find_max = find_max[find_max.str.contains('\d+ to \d+ of \d+')]
    bottom_page = find_max.str.extract('\d+ to (\d+) of \d+',expand=False).astype(float).iloc[0]
    top_page = find_max.str.extract('(\d+) to \d+ of \d+',expand=False).astype(float).iloc[0]
    listing_n = (bottom_page-top_page) + 1
    # EXTRACT address and auction results
    find_sold = pd.Series(str(soup.findAll("table"
                             ,  { "class" : 'table table-bordered table-condensed'}
                            )))
    find_rows = find_sold.str.split('<tr>|<tr|<td',expand=True)
    ## extract values
    row_map = pd.Series([                                               # define row source (same?)
            'a href="(?P<href_suburb>.*)">'                             # rowID=1
        ,   '<span class="text-success">(?P<suburb>.*)</span>'          # rowID=1
        ,   '<small>(?P<postcode>.*)</small'                            # rowID=1
        ,   'class="pull-left" href="(?P<href_addr>.*/)">'              # rowID=2
        ,   '/">(?P<href_street>[A-Z]*\d+.*)</a'                        # rowID=2
        ,   'class="pull-right icon-sold" title="(?P<dateID>.*)"><'     # rowID=2
        ,   'class="text-right">(?P<value>.*)</td'                      # rowID=3:6
        ,   'class="text-right hidden-xs".*>(?P<agent>.*)</td'          # rowID=7
        ])
    pull_fields = pd.DataFrame()
    for idx, str_ext in enumerate(row_map):
        #print(idx)
        new_col = find_rows.loc[0].str.extract(str_ext,expand=True)
        pull_fields = pd.concat([pull_fields,new_col],axis=1)
    # create an index ID
    pull_fields['ID'] = range(pull_fields.shape[0])
    ## identify SUBURBs
    suburb_mapping = ['href_suburb','suburb','postcode']
    suburb_df = pull_fields[suburb_mapping+['ID']].dropna(axis=0).copy()
    pull_fields['suburbID'] = 0
    pull_fields['suburbID'][suburb_df.index] = 1
    pull_fields[suburb_mapping] = pull_fields[suburb_mapping].fillna(method='ffill')
    pull_fields = pull_fields.query('suburbID==0').drop('suburbID',axis=1)
    pull_fields = pull_fields.query('suburb==suburb')
    ## drop useless columns
    value_cols = ['href_addr','href_street','dateID','value','agent']
    pull_fields['drop'] = pull_fields[value_cols].isnull().sum(axis=1).apply(lambda x: 1 if x==len(value_cols) else 0)
    pull_fields = pull_fields.query('drop == 0')
    # DateID fix for not sold
    pull_fields['dateID'].loc[pull_fields.query('href_street==href_street & dateID!=dateID').index.values] = 'Not Sold'
    ## identify PROPERTY
    addr_mapping = ['href_addr','href_street','dateID']
    pull_fields['drop'] = pull_fields[addr_mapping].isnull().sum(axis=1).apply(lambda x: 1 if x==0 else 0)
    pull_fields[addr_mapping] = pull_fields[addr_mapping].fillna(method='ffill')
    pull_fields = pull_fields.query('drop == 0')
    ### Pull out value strings
    pull_fields['value'] = pull_fields['value'].fillna(pull_fields['agent'])
    pull_fields = pull_fields.drop(['agent','drop','ID'],axis=1,errors='ignore')
    # random NaN observed = 'NSW_2015-02-14_p1.txt'
    pull_fields = pull_fields.query('value==value')
    pull_fields['variable'] = pull_fields.groupby('href_addr').cumcount()
    var_counts = pull_fields['variable'].value_counts()
    if sum(var_counts == listing_n) != len(var_counts):
        print('ERROR: cant find VALUES for every Address')
        break
    # apply column names to vlauea
    column_mapping = pd.Series({
                    0:'sold_price'
                ,   1:'result_code'
                ,   2:'property_type'
                ,   3:'bedrooms'
                ,   4:'agent'
                }).reset_index().rename(columns={'index':'variable',0:'column'})
    pull_fields = pd.merge(pull_fields,column_mapping,on='variable',how='left')
    auction_df = pull_fields.groupby(suburb_mapping+addr_mapping+['column'])['value'].max().unstack('column').reset_index()
    ## check it all worked
    if abs(auction_df.shape[0] -  listing_n)>5:
        print('ERROR: Address count doesnt Match PAGE COUNT...actual:{a} VS listings:{b}'.format(a=auction_df.shape[0],b=listing_n))
        break
    #
    auction_df.to_csv(project_dir+'/'+re.sub('.txt','.csv',url))

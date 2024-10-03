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


export_dir = f'{home_dir}/output_etl2'
if os.path.exists(export_dir) == False: 
    os.mkdir(export_dir)


# NSWgov dat file mapping
# https://www.valuergeneral.nsw.gov.au/__data/assets/pdf_file/0015/216402/Current_Property_Sales_Data_File_Format_2001_to_Current.pdf
nswgov_dat_map = [
    # Record: A: Header record (1 per file)
    {'record_type':'A','variable':0,'label':'record_type'},
    {'record_type':'A','variable':1,'label':'file_type'},
    {'record_type':'A','variable':2,'label':'district_code'},
    {'record_type':'A','variable':3,'label':'create_dt'},
    {'record_type':'A','variable':4,'label':'userid'},
    # Record: B: contain property address and sale information
    {'record_type':'B','variable':0,'label':'record_type'},
    {'record_type':'B','variable':1,'label':'district_code'},
    {'record_type':'B','variable':2,'label':'property_id'},
    {'record_type':'B','variable':3,'label':'sale_counter'},
    {'record_type':'B','variable':4,'label':'create_dt'},
    {'record_type':'B','variable':5,'label':'prop_name'},
    {'record_type':'B','variable':6,'label':'unit_no'},
    {'record_type':'B','variable':7,'label':'house_no'},
    {'record_type':'B','variable':8,'label':'street_name'},
    {'record_type':'B','variable':9,'label':'locality'},
    {'record_type':'B','variable':10,'label':'postcode'},
    {'record_type':'B','variable':11,'label':'area_sqm'},
    {'record_type':'B','variable':12,'label':'area_type'},
    {'record_type':'B','variable':13,'label':'contract_dt'},
    {'record_type':'B','variable':14,'label':'settle_dt'},
    {'record_type':'B','variable':15,'label':'sale_price'},
    {'record_type':'B','variable':16,'label':'zoning'},
    {'record_type':'B','variable':17,'label':'prop_nature'},
    {'record_type':'B','variable':18,'label':'prop_purpose'},
    {'record_type':'B','variable':19,'label':'strata_no'},
    {'record_type':'B','variable':20,'label':'component_cd'},
    {'record_type':'B','variable':21,'label':'sale_cd'},
    {'record_type':'B','variable':22,'label':'sale_interest'},
    {'record_type':'B','variable':23,'label':'dealing_no'},
    # Record: C: property description details
    {'record_type':'C','variable':0,'label':'record_type'},
    {'record_type':'C','variable':1,'label':'district_code'},
    {'record_type':'C','variable':2,'label':'property_id'},
    {'record_type':'C','variable':3,'label':'sale_counter'},
    {'record_type':'C','variable':4,'label':'create_dt'},
    {'record_type':'C','variable':5,'label':'prop_desc'},
    # Record: D: owners details suppressed
    {'record_type':'D','variable':0,'label':'record_type'},
    {'record_type':'D','variable':1,'label':'district_code'},
    {'record_type':'D','variable':2,'label':'property_id'},
    {'record_type':'D','variable':3,'label':'sale_counter'},
    {'record_type':'D','variable':4,'label':'create_dt'},
    {'record_type':'D','variable':5,'label':'vendor'},
    # Record: Z: tail record
    {'record_type':'Z','variable':0,'label':'record_type'},
    {'record_type':'Z','variable':1,'label':'total_records'},
    {'record_type':'Z','variable':2,'label':'records_b'},
    {'record_type':'Z','variable':3,'label':'records_c'},
    {'record_type':'Z','variable':4,'label':'records_d'},
]

nswgov_dat_map = pd.DataFrame(nswgov_dat_map)


## YYYY range

output_dir = f'{home_dir}/annual'

yyyy_range = pd.DataFrame({'YYYY':os.listdir(output_dir)})
yyyy_range = yyyy_range[yyyy_range.YYYY.str.contains('\d{4}')]
yyyy_range.YYYY = yyyy_range.YYYY.astype(int)
yyyy_range = yyyy_range.query('YYYY>2011')


###
for yyyy in yyyy_range.YYYY: # yyyy =2012
    print(yyyy)
    # 
    yyyy_dir = f'{output_dir}/{yyyy}'
    ymd_range = pd.DataFrame({'YMD':os.listdir(yyyy_dir)})
    ymd_range = ymd_range[ymd_range.YMD.str.contains('(\d{8}).*|([A-z]+ \d{2}, \d{4}).*')]
    ymd_range['YMD'] = ymd_range.YMD.str.strip('.zip')
    ymd_range = ymd_range['YMD'].unique()
    # 
    for ymd in ymd_range: # ymd = '20190204'
        print(ymd)
        ymd_name = ymd 
        if re.search('\d{8}', ymd_name) == None : 
            ymd_name = re.sub(r' \([A-Z]+\)','',ymd_name)
            ymd_name = datetime.datetime.strptime(ymd_name.replace(' 0',' '), '%B %d, %Y').strftime('%Y%m%d')
        # 
        ymd_dir = f'{yyyy_dir}/{ymd}'
        if os.path.exists(f'{export_dir}/{ymd_name}.csv')==False:
            print('file doesnt exist')
            if os.path.exists(ymd_dir) ==False:
                print('Unzip')
                with zipfile.ZipFile(f'{ymd_dir}.zip', 'r') as zip_ref: 
                    zip_ref.extractall(ymd_dir)
            # 
            week_files = pd.Series(os.listdir(ymd_dir))
            week_files = week_files[week_files.str.contains('.DAT')]
            if week_files.shape[0] == 0 : 
                child_folder = np.setdiff1d(os.listdir(ymd_dir),['.DS_Store'])[0]
                ymd_dir = f'{ymd_dir}/{child_folder}'
                week_files = pd.Series(os.listdir(ymd_dir))
                week_files = week_files[week_files.str.contains('.DAT')]
            # 
            file_extract = pd.DataFrame()
            for f in week_files:  
                ## pull data
                # data
                with open(f'{ymd_dir}/{f}') as fff:
                    raw_dat = pd.DataFrame({'raw':pd.Series(fff.readlines())})
                # 
                raw_dat = raw_dat.raw.str.split(';',expand=True)
                raw_dat['record_type'] = raw_dat[0]
                raw_dat['index'] = raw_dat.index.values
                raw_dat2 = raw_dat.melt(id_vars = ['record_type','index'])
                raw_dat2 = raw_dat2.query('value == value')
                raw_dat2 = pd.merge(raw_dat2,nswgov_dat_map,on=['record_type','variable'],how='left')
                raw_dat2['ymd'] = ymd_name
                raw_dat2['file'] = f
                # ÷checks
                # raw_dat2.query('label!= label').groupby(['record_type','variable']).size()
                # raw_dat2.query('label!= label')['value'].value_counts()
                file_extract = pd.concat([file_extract,raw_dat2],axis=0,ignore_index=True)
            # ## write csv
            print(f'saving file = "{ymd_name}" with {file_extract.shape[0]} rows')
            if file_extract.shape[0] == 0 : 
                print('ZERO rows added, investigate')
                break
            file_extract.to_csv(f'{export_dir}/{ymd_name}.csv',index=False)
                


## weekly range

output_dir = f'{home_dir}/weekly'

yyyy_range = pd.DataFrame({'YYYY':os.listdir(output_dir)})
yyyy_range = yyyy_range[yyyy_range.YYYY.str.contains('\d{8}')]
yyyy_range.YYYY = yyyy_range.YYYY.astype(int)


###
for yyyymmdd in yyyy_range.YYYY: # yyyy =2012
    print(yyyymmdd)
    # 
    yyyy_dir = f'{output_dir}/{yyyymmdd}'
    ymd_range = pd.DataFrame({'YMD':os.listdir(yyyy_dir)})
    ymd_range = ymd_range[ymd_range.YMD.str.contains('(\d{8}).*|([A-z]+ \d{2}, \d{4}).*')]
    ymd_range['YMD'] = ymd_range.YMD.str.strip('.zip')
    ymd_range = ymd_range['YMD'].unique()
    # 
    # for ymd in ymd_range: # ymd = '20190204'
    #     print(ymd)
    #     ymd_name = ymd 
    #     if re.search('\d{8}', ymd_name) == None : 
    #         ymd_name = re.sub(r' \([A-Z]+\)','',ymd_name)
    #         ymd_name = datetime.datetime.strptime(ymd_name.replace(' 0',' '), '%B %d, %Y').strftime('%Y%m%d')
    #     # 
    #     ymd_dir = f'{yyyy_dir}/{ymd}'
    #     if os.path.exists(f'{export_dir}/{ymd_name}.csv')==False:
    #         print('file doesnt exist')
    #         if os.path.exists(ymd_dir) ==False:
    #             print('Unzip')
    #             with zipfile.ZipFile(f'{ymd_dir}.zip', 'r') as zip_ref: 
    #                 zip_ref.extractall(ymd_dir)
    #         # 
    week_files = pd.Series(os.listdir(yyyy_dir))
    week_files = week_files[week_files.str.contains('.DAT')]
    if week_files.shape[0] == 0 : 
        child_folder = np.setdiff1d(os.listdir(yyyy_dir),['.DS_Store'])[0]
        yyyy_dir = f'{yyyy_dir}/{child_folder}'
        week_files = pd.Series(os.listdir(yyyy_dir))
        week_files = week_files[week_files.str.contains('.DAT')]
    # 
    file_extract = pd.DataFrame()
    for f in week_files:  
        ## pull data
        # data
        with open(f'{yyyy_dir}/{f}') as fff:
            raw_dat = pd.DataFrame({'raw':pd.Series(fff.readlines())})
        # 
        raw_dat = raw_dat.raw.str.split(';',expand=True)
        raw_dat['record_type'] = raw_dat[0]
        raw_dat['index'] = raw_dat.index.values
        raw_dat2 = raw_dat.melt(id_vars = ['record_type','index'])
        raw_dat2 = raw_dat2.query('value == value')
        raw_dat2 = pd.merge(raw_dat2,nswgov_dat_map,on=['record_type','variable'],how='left')
        raw_dat2['ymd'] = ymd_name
        raw_dat2['file'] = f
        # ÷checks
        # raw_dat2.query('label!= label').groupby(['record_type','variable']).size()
        # raw_dat2.query('label!= label')['value'].value_counts()
        file_extract = pd.concat([file_extract,raw_dat2],axis=0,ignore_index=True)
    # ## write csv
    print(f'saving file = "{yyyymmdd}" with {file_extract.shape[0]} rows')
    output_etl2 = f'{export_dir}/{yyyymmdd}.csv'
    if file_extract.shape[0] == 0 : 
        print('ZERO rows added, investigate')
        break
    if os.path.exists(output_etl2) == False:
        file_extract.to_csv(output_etl2,index=False)
                    



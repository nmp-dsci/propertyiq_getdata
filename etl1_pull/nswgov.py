
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests, zipfile
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import re,time,os,sys
import time,datetime,math
from bs4.element import Tag

# from config import * 
# from utils import * 

## set directory
sourceid = 'nswgov'

scrape_area_dir = f'../../data/propertyiq_getdata/{sourceid}'
if os.path.exists(scrape_area_dir) == False:
    os.mkdir(scrape_area_dir)


### Get files required

latest_yr = np.max(pd.Series(os.listdir(scrape_area_dir)).astype(str).str.extract('(\d{4})',expand=False).dropna())


####
nswgov_html = requests.get('https://valuation.property.nsw.gov.au/embed/propertySalesInformation').text
nswgov_html = BeautifulSoup(nswgov_html)

dataTerm = ['annual','weekly']
classPattern = {'annual':{
        'class':'btn btn-primary btn-sales-data'
    ,   'href':'.*/(\d{4}).zip'
    }
    , 'weekly':{
        'class':'btn btn-primary btn-sales-data btn-sales-data'
    ,   'href':'.*/(\d{8}).zip'
    }
}


for term in dataTerm:
    print(f'{term}')
    #
    payload_dir = f'{scrape_area_dir}/{term}'
    if os.path.exists(payload_dir) == False:
        os.mkdir(payload_dir)
    # 
    latest_yr_files = pd.DataFrame({'href':[x.get('href') for x in nswgov_html.find_all('a',{'class':classPattern[term]['class']})]})
    latest_yr_files['dt'] = latest_yr_files.href.str.extract(classPattern[term]['href'],expand=False)
    latest_yr_files.index = latest_yr_files.dt
    latest_yr_files['complete'] = latest_yr_files['dt'].isin(os.listdir(payload_dir))
    ####
    for filei in latest_yr_files.query('complete == 0').index:
        print("looking through: {d}".format(d=filei))
        zip_url = requests.get(latest_yr_files.loc[filei,'href'])
        # output name
        output_dir = f'{payload_dir}/{filei}.zip'
        with open(output_dir, 'wb') as zip_dump: 
            zip_dump.write(zip_url.content)
        # extract
        extract_dir = f'{payload_dir}/{filei}'
        os.mkdir(extract_dir)
        with zipfile.ZipFile(output_dir, 'r') as zip_ref: 
            zip_ref.extractall(extract_dir)
        # Delete
        os.remove(output_dir)




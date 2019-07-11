
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

sys.path.append('/Users/macmac/Documents/GitHub/propertyiq_getdata')

from config import * 
from utils import * 

## set directory
sourceid = 'nswgov'

scrape_area_dir = output_directory + '01a Region href property/'+ sourceid 
if os.path.exists(scrape_area_dir) == False:
    os.mkdir(scrape_area_dir)


### Get files required

latest_yr = max(pd.Series(os.listdir(scrape_area_dir)).str.extract('(\d{4})',expand=False).dropna())

payload_dir = '{a}/{b}'.format(a=scrape_area_dir,b=latest_yr)
existing_dt = os.listdir(payload_dir) 

####
nswgov_html = requests.get('https://valuation.property.nsw.gov.au/embed/propertySalesInformation').text
nswgov_html = BeautifulSoup(nswgov_html)

latest_yr_files = pd.DataFrame({'href':[x.get('href') for x in nswgov_html.find_all('a',{'class':'btn btn-primary btn-sales-data btn-sales-data'})]})
latest_yr_files['dt'] = latest_yr_files.href.str.extract('.*/(\d{8}).zip',expand=False)
latest_yr_files.index = latest_yr_files.dt
latest_yr_files['complete'] = latest_yr_files['dt'].isin(existing_dt)

####
for filei in latest_yr_files.query('complete == 0').index:
    print("looking through: {d}".format(d=filei))
    zip_url = requests.get(latest_yr_files.loc[filei,'href'])
    # output name
    output_dir = '{a}/{b}.zip'.format(a=payload_dir,b=filei)
    with open(output_dir, 'wb') as zip_dump: 
        zip_dump.write(zip_url.content)
    # extract
    extract_dir = '{a}/{b}'.format(a=payload_dir,b=filei)
    os.mkdir(extract_dir)
    with zipfile.ZipFile(output_dir, 'r') as zip_ref: 
        zip_ref.extractall(extract_dir)
    # Delete
    os.remove(output_dir)
    # update
    latest_yr_files['complete'] = latest_yr_files['dt'].isin(existing_dt)




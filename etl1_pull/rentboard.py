
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
sourceid = 'rentboard'

scrape_area_dir = f'../../data/propertyiq_getdata/{sourceid}'
if os.path.exists(scrape_area_dir) == False:
    os.mkdir(scrape_area_dir)

nswgov_html = requests.get('https://www.fairtrading.nsw.gov.au/about-fair-trading/data-and-statistics/rental-bond-data').text
nswgov_html = BeautifulSoup(nswgov_html)

##############################################
## STEP 1: identify all data available for scraping
href_links = nswgov_html.find_all('td')
href_links = [x.find_all('a') for x in href_links]
href_links = [x[0]['href']for x in href_links  if len(x) >= 1 ]
href_df = pd.DataFrame({'href':href_links})

href_df = href_df[href_df.href.str.lower().str.contains('copy') == False]
href_df = href_df[href_df.href.str.lower().str.contains('refund') == False]

regex_rules =[
    {'regex_rule':'lodge_year_v1', 'regex':'/RentalBond_Lodgements_Year_(\d+).xlsx$','period':'annual'}
,   {'regex_rule':'lodge_year_v2', 'regex':'/rental-bond-lodgement-data-year-(\d+).xlsx$','period':'annual'}
,   {'regex_rule':'lodge_monthly_v1', 'regex':'/Rental-bond-lodgements-data-(\w+-\d+).xlsx$','period':'month'}
,   {'regex_rule':'lodge_monthly_v2', 'regex':'/Rental-bond-lodgement-data-(\w+-\d+).xlsx$','period':'month'}
,   {'regex_rule':'lodge_monthly_v3', 'regex':'/RentalBond_Lodgements_(\w+_\d+).xlsx$','period':'month'}
,   {'regex_rule':'lodge_monthly_v4', 'regex':'/Rental-Bond-Lodgements-(\w+-\d+).xlsx$','period':'month'}
,   {'regex_rule':'lodge_monthly_v5', 'regex':'/Rental-Bond-Lodgements-for-(\w+-\d+).xlsx$','period':'month'}
]
rule_names = [x.get('regex_rule') for x in regex_rules]


for rule in regex_rules: 
    print(rule)
    href_df[rule.get('regex_rule')] = href_df.href.str.extract(rule.get('regex'),flags=re.IGNORECASE,expand=False)

found_regex = href_df.melt(id_vars = 'href', value_vars = rule_names).query('value==value')
found_regex = found_regex[found_regex.value.str.lower().str.contains('year') == False]
found_regex['dedup'] = found_regex.groupby('href').cumcount()
assert found_regex['dedup'].max() == 0, 'ERROR: href regex identification rules are duping'
found_regex = found_regex.rename(columns={'variable':'regex_rule','value':'regex_value'})

href_df = href_df.merge(found_regex,on='href',how='left')

assert href_df.query('regex_value != regex_value').shape[0] == 0 , "ERROR: missing href classification"


href_df = href_df.merge(pd.DataFrame(regex_rules),on='regex_rule',how='left')

##############################################
## STEP 2: scrape annual files

periodID = 'annual'
csvColumns = ['Lodgement Date','Postcode','Dwelling Type','Bedrooms','Weekly Rent']
scrape_df = href_df.query(f'period=="{periodID}"')

for href  in scrape_df.to_dict(orient='records'): 
    print(f'Scraping period:{periodID} for value:{href.get("regex_value")}')
    # step 1:get xlsx
    dir_xlsx = f'{scrape_area_dir}/{href.get("regex_value")}.xlsx'
    if os.path.exists(dir_xlsx) == False:  
        print(f"loading xlsx: {href.get('regex_value')}")
        zip_url = requests.get(href.get('href'))
        with open(dir_xlsx, 'wb') as zip_dump: 
            zip_dump.write(zip_url.content)
    # step 2: convert to csv
    dir_csv = f'{scrape_area_dir}/{href.get("regex_value")}.csv'
    if os.path.exists(dir_csv) == False:  
        print(f"loading csv: {href.get('regex_value')}")
        xlsx_df = pd.read_excel(dir_xlsx, header = 2)
        assert len(np.setdiff1d(xlsx_df.columns,csvColumns)) == 0 , "ERROR: columns names not lining up "
        xlsx_df.to_csv(dir_csv,index=False)



##########################################
## step 3 :build final stacked dataset

rent_df = pd.DataFrame(columns = csvColumns)

for href  in scrape_df.to_dict(orient='records'): 
    print(f'Build base table:{periodID} for value:{href.get("regex_value")}')
    dir_csv = f'{scrape_area_dir}/{href.get("regex_value")}.csv'
    xlsx_df = pd.read_csv(dir_csv)
    rent_df = rent_df.append(xlsx_df)

rent_df = rent_df.rename(columns={
    'Lodgement Date':'lodgement_dt'
,   'Postcode':'postcode'
,   'Dwelling Type':'property_type'
,   'Bedrooms':'bedrooms'
,   'Weekly Rent':'weekly_rent'
})

rent_df.to_csv(f'{scrape_area_dir}/rentboard_df.csv',index=False)


# rent_df = pd.read_csv(f'{scrape_area_dir}/rent_lodgement_basedf.csv')


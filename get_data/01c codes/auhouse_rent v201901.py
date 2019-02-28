
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import re
import time
import os
import time
import datetime
import math

from bs4.element import Tag
#time.sleep(3600*3)
#dateid = time.strftime("%Y%m%d")
sourceid = 'auhouse_rent'
dateid = str(20190202)
print (dateid)

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))


final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid[last_dateid.str.contains(sourceid)]
last_dateid = last_dateid.str.extract('(\d{8})',expand=False)
last_dateid = last_dateid[last_dateid!= dateid]
last_dateid = last_dateid.astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))
scrape_area_dir =  output_directory + '01a Region href property/' + dateid +'_'+sourceid
suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_'+sourceid

#######################################################################
# Build Master
suburb_files = pd.DataFrame({'suburb':os.listdir(suburb_dir)})
suburb_files['size'] = suburb_files['suburb'].apply(lambda x: os.stat(suburb_dir+'/'+x).st_size)
# filters
suburb_files = suburb_files.query('suburb != ".DS_Store"  and size > 100')


master_df = pd.DataFrame()
for suburb in suburb_files['suburb'].values:         # suburb = suburb_files.values[0]
    print(suburb)                   # suburb = 'nsw_2061_kirribilli.csv'
    suburb_df = pd.read_csv(suburb_dir +'/'+ suburb)
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)

### Do some checks
master_df.dtypes



for col in list(master_df.columns):
    print(col)
    master_df[col] = master_df[col].str.strip('b').str.strip("'")

# float treatment
for flloat in ['bedrooms','bathrooms','carpark']:
    print(flloat)
    master_df[flloat] = master_df[flloat].astype(float)

# property type treatment
master_df['propertyType'] = master_df['propertyType'].str.lower()
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'duplex' if 'duplex' in x else x)
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'acreage' if 'acreage' in x else x)
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'apartment' if 'unit' == x else x)
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'apartment' if 'studio' == x else x)
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'apartment' if 'flat' == x else x)
master_df['propertyType'] = master_df['propertyType'].apply(lambda x: 'apartment' if 'apartment' in x else x)

master_df['propertyType'].value_counts(dropna=False)



##

check_lookup = {
        'bathrooms':[x for x in range(10)] + [np.NaN]
    ,   'bedrooms':[x for x in range(10)] + [np.NaN]
    ,   'carpark':[x for x in range(10)] + [np.NaN]
    ,   'propertyType':['apartment',
                         'other',
                         'house',
                         'terrace',
                         'townhouse',
                         'duplex',
                         'acreage',
                         'villa',
                         'warehouse',
                         'alpine',
                         'retirement living']
    }

print("Check no missing values, NaN okay")
for k in check_lookup.keys():       # k = 'bedrooms'
    print(k)
    print(np.setdiff1d(master_df[k].unique(),check_lookup[k]))




####################
pd.options.display.max_columns = 28

# step 1: Pull out Date and Sold Type
master_df['sale_date'] = master_df['sale_date'].str.lower()
print('should be of Singular VAlue')
print(master_df['sale_date'].str.extract('([a-z]+ [a-z]+) .*',expand=False).value_counts())

master_df['sale_date'] = master_df['sale_date'].str.replace('rent on','').str.strip()
master_df['sale_date'] = master_df['sale_date'].apply(lambda x: '01 ' + x)

master_df['DateID'] = pd.to_datetime(master_df['sale_date'],format='%d %b %Y',errors='coerce')

print('should be NO MISSING')
print(master_df['DateID'].isnull().value_counts(dropna=False))
# only 16... drop them
master_df = master_df.query('DateID == DateID')

# price
print('PRICE: per week')
price_format = '\$\d*,*\d{2,3}/week'
print('Should ALL BE TRUE... price format')
master_df['price_fmt']=master_df['price_str'].str.contains(price_format)
print(master_df['price_str'].str.contains(price_format).value_counts(dropna=False))

master_df.query('price_fmt ==False')['price_str'].value_counts()
master_df = master_df.query('price_fmt ==True')
master_df['price_str'] = master_df['price_str'].str.replace('[$,/week]','').astype(int)



#####################
## extract address
master_df['ID_valid'] = master_df['href'].str.extract('.*/(\d+)/.*',expand=False).notnull()
print('THERE should be no MISSING ID aka FALSEs')
print(master_df['ID_valid'].value_counts())
master_df['ID'] = master_df['href'].str.extract('.*/(\d+)/.*',expand=False)



####################
### Clean UP dataset
master_df = master_df.drop(['price_fmt','ID_valid','property_attr'],axis=1,errors='ignore')

###################
## finalise beds/baths/ garage / property type

for k in check_lookup.keys():
    print(k)
    master_df[k] = master_df[k].fillna(0)


###################
### PULL OUT ADDRESS
master_df['raw_addr'] = master_df['href'].str.extract('\d+/(.*)/',expand=False).str.lower()

## kill available on request or flag it!!
master_df['Addr0_none'] = master_df['raw_addr'].str.contains('address_available_on_request').astype(int)

## pull out apartment reference
master_df['Addr1_unit'] = master_df['raw_addr'].str.contains('([a-z]*\d*[a-z]*)_\d+[a-z]*_.*')

pd.crosstab(master_df['Addr1_unit'],master_df['propertyType'],normalize='columns').T

master_df.query('Addr1_unit == False and propertyType == "apartment"')['raw_addr'].head(100)

### extract STREET NUMBER
house = master_df['raw_addr'].str.extract('(?P<streetNo>\d+[a-z]*)_[a-z]+_.*',expand=True)
unit1 = master_df['raw_addr'].str.extract('(?P<sub1>[a-z]*\d*[a-z]*)_(?P<streetNo>\d+[a-z]*)_[a-z]+_.*',expand=True)
unit2 = master_df['raw_addr'].str.extract('(?P<sub0>[a-z]*\d*[a-z]*)_(?P<sub1>\d+[a-z]*)_(?P<streetNo>\d+[a-z]*)_[a-z]+_.*',expand=True)

addr_number_map = unit2.copy()
addr_number_map[unit1.columns.values] = addr_number_map[unit1.columns.values].fillna(unit1)
addr_number_map[house.columns.values] = addr_number_map[house.columns.values].fillna(house)
addr_number_map['addr_missing'] = addr_number_map.notnull().sum(axis=1).apply(lambda x: 1 if x == 0 else 0)

master_df = pd.concat([master_df,addr_number_map],axis=1)

#### POSTCODE
master_df['postcode'] = master_df['address'].str.lower().str.extract('[a-z]+ (\d{4})',expand=False).astype(int)


####################
## PULL SUBURB from file name and done!!
master_df['suburb2'] = master_df['suburb'].str.replace('nsw_\d{4}_','')
master_df['suburb2'] = master_df['suburb2'].str.replace('+',' ')

###################
## street               x = master_df.iloc[1,:]
street_raw = master_df.query('streetNo==streetNo and address==address').apply(lambda x: re.split(x['streetNo'],x['raw_addr'])[1],axis=1)
master_df['street2'] = street_raw.copy()
street_raw2 = master_df.query('streetNo==streetNo and address==address').apply(lambda x: re.split(re.sub(' ','_',x['suburb2']),x['street2'])[0],axis=1)
master_df['street3'] = street_raw2.copy()
master_df['street3'] = master_df['street3'].str.strip('_').str.replace('_',' ')
master_df['street3'] = master_df['street3'].apply(lambda x: np.NaN if len(str(x)) <4 else x)


master_df = master_df.drop(['suburb','street2'],axis=1).rename(columns={'street3':'street','suburb2':'suburb'})


##############################
### Final Delivery
##############################



master_df.to_csv(final_dir  + '/'+dateid+'_'+sourceid+'.csv',index=False)


# 20190202: 504,632
master_df.shape


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

from bs4.element import Tag

#dateid = time.strftime("%Y%m%d")
dateid = str(20171104)
print (dateid)


## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid +'_domain.com'

suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_domain.com'
if os.path.exists(suburb_dir) == False :
    os.mkdir(suburb_dir)

#######################################################################
#### functiosn for search page

#### Attirbutes needed
# 0. DomainID
# 1. sale type + date date
# 2. price
# 3. address line 1
# 4. address line 2 [ has  suburb/ region/ postcode/ latitude/ longitude]
# 5. beds
# 6. bathrooms
# 7. parking

dummy = '<i href="missing" src="missing" content="missing" data-listing-id ="missing" >'
dummy = BeautifulSoup(dummy)
dummy = dummy.findAll('i')[0]
dummy.get_text()



#### go through suburb + page
def get_value(domType, classValue, x):
    result = x.findAll(domType, classValue)
    if len(result) == 0:
        return(dummy)
    else:
        return(result[0])


fields_funcs = pd.Series({
            "domainid":lambda x:  x['data-reactid'] if x.find('data-listing-id') is None else x['data-listing-id']
        ,   "details": lambda x: x.get_text('|')
#        ,   "price_str":lambda x: get_value("p", { "class" : 'listing-result__price'}, x).get_text(strip=True)
#        ,   "address":lambda x: get_value("meta", { "itemprop" : 'name'}, x)['content']
#        ,   "state":lambda x: get_value("span", { "itemprop" : 'addressRegion'}, x).get_text(strip=True)
#        ,   "suburb":lambda x: get_value("span", { "itemprop" : 'addressLocality'}, x).get_text(strip=True)
#        ,   "postcode":lambda x: get_value("span", { "itemprop" : 'postalCode'}, x).get_text(strip=True)
        ,   "latitude":lambda x: get_value("meta", { "itemprop" : 'latitude'}, x)['content']
        ,   "longitude":lambda x: get_value("meta", { "itemprop" : 'longitude'}, x)['content']
#        ,   "sale_date":lambda x: get_value("span", { "class" : 'listing-result__tag is-sold'}, x).get_text(strip=True)
#        ,   "beds":lambda x: re.sub('[^0-9]','',get_value("span", { "class" : 'listing-result__feature-bed'}, x).get_text(strip = True))
#        ,   "bathrooms":lambda x: re.sub('[^0-9]','',get_value("span", { "class" : 'listing-result__feature-bathroom'}, x).get_text(strip = True))
#        ,   "parking":lambda x: re.sub('[^0-9]','',get_value("span", { "class" : 'listing-result__feature-parking'}, x).get_text(strip = True))
        })

### Text files to aggreage on 
txt_files = pd.DataFrame({'filename':pd.Series(os.listdir(scrape_area_dir))})
txt_files = txt_files[txt_files['filename'].str.contains('_p|.txt')]
txt_files['suburb'] = txt_files['filename'].str.split('_b',expand=True)[0]
txt_files['suburb'].value_counts()

### iterate through postcodes are create master file
suburb_list = txt_files['suburb'].sort_values().unique()

iters = 5
leni = len(suburb_list)
len_iter = leni/iters

rows1 = range( len_iter * 1 - len_iter ,len_iter * 1)
rows2 = range( len_iter * 2 - len_iter ,len_iter * 2)
rows3 = range( len_iter * 3 - len_iter ,len_iter * 3)
rows4 = range( len_iter * 4 - len_iter ,len_iter * 4)
rows5 = np.setdiff1d(range(leni),  rows1+rows2+rows3 + rows4)

trackerDF = pd.DataFrame()
for suburb in suburb_list[rows5]:     # suburb = suburb_list[rows4][0]   suburb = 'kirribilli-nsw-2061'
    if os.path.exists(suburb_dir+'/'+suburb+'.csv') ==False:
        s_t1 = time.time()
        suburb_files = txt_files.query('suburb=="'+suburb+'"')[['filename']]
        suburb_files['page_no'] = suburb_files['filename'].str.extract('_p(.*?).txt').astype(int)
        suburb_files = suburb_files.sort_values('page_no')
        #
        master_df = pd.DataFrame()
        for filename in  suburb_files['filename']: # filename =suburb_files['filename'].iloc[0]
            s_t2 = time.time()
            print('\t '+filename)     # filename = 'abbotsbury-nsw-2176_p2.txt'
            # get data
            rawdata = open(scrape_area_dir + '/' + filename,"r").read()
            soup = BeautifulSoup(rawdata)
            #
            find_sold = pd.Series(soup.findAll("li", { "class" : 'strap new-listing'}))
            if len(find_sold)==0:
                find_sold = pd.Series(soup.findAll("li", { "class" : 'search-results__listing'}))
            sold_info = find_sold.apply(lambda x: fields_funcs.apply(lambda f: f(x)))
            if sold_info.shape[0]> 0:
                sold_info['filename'] = filename
                master_df = pd.concat([master_df, sold_info], axis = 0,ignore_index=True)
            #
            e_t2 = time.time()
            print('\t Page Time taken: %s seconds for %d files' % (round(e_t2-s_t2,2),len(master_df)))
            ## update file extraction
            extracted = pd.DataFrame({'f':filename,'listings':len(sold_info)},index=[0])
            trackerDF = pd.concat([trackerDF,extracted],axis=0,ignore_index=True)
        # 
        # write file
        master_df = master_df.apply(lambda x: x.str.encode('utf-8'),axis=0)
        master_df.to_csv(suburb_dir+'/'+suburb+'.csv',index=False)
        e_t1 = time.time()
        print('Suburb Time taken: %s seconds for %d files' % (round(e_t1-s_t1,2),len(master_df)))
        #
        #
trackerDF.to_csv(output_directory + '01b Suburb_Files/' + dateid +'_domain_row5.csv',index=False)
#### END LOOP 









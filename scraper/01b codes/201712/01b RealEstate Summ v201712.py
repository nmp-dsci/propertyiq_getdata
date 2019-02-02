
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


#dateid = time.strftime("%Y%m%d")
dateid = str(20171231)
print (dateid)

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid[~last_dateid.str.contains(dateid)]
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_realestate.com'

suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_realestate.com'
if os.path.exists(suburb_dir) == False :
    os.mkdir(suburb_dir)


################################################################
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

#### go through suburb + page



dummy = '<i href="missing" src="missing" content="missing" >'
dummy = BeautifulSoup(dummy)
dummy = dummy.findAll('i')[0]


def get_value(domType, classValue, x):
    result = x.findAll(domType, classValue)
    if len(result) == 0:
        return(dummy)
    else:
        return(result[0])


fields_funcs = pd.Series({
            "price_str":lambda x: get_value("span", { "class" : 'property-price'}, x).get_text(strip=True)
        ,   "price_img":lambda x: get_value("img", { "class" : 'property-price__image'}, x)['src']
        ,   "address":lambda x: get_value("a", { "class" : 'property-card__info-text'}, x).get_text(strip=True)
        ,   "href":lambda x: get_value("a", { "class" : 'property-card__info-text'} , x)['href']
        ,   "property_type":lambda x: get_value("span", { "class" : 'property-card__property-type'}, x).get_text(strip=True)
        ,   "sale_date":lambda x: get_value("span", { "class" : 'property-card__with-comma'}, x).get_text(strip=True)
        ,   "beds":lambda x: get_value("span", { "class" : 'general-features__icon general-features__beds'}, x).get_text(strip=True)
        ,   "bathrooms":lambda x: get_value("span", { "class" : 'general-features__icon general-features__baths'}, x).get_text(strip=True)
        ,   "parking":lambda x: get_value("span", { "class" : 'general-features__icon general-features__cars'}, x).get_text(strip=True)
        })
    
fields_funcs_v2 = pd.Series({
            "price_str":lambda x: get_value("span", { "class" : 'property-price'}, x).get_text(strip=True)
        ,   "price_img":lambda x: get_value("img", { "class" : 'property-price__image'}, x)['src']
        ,   "address":lambda x: get_value("a", { "class" : 'residential-card__info-text'}, x).get_text(strip=True)
        ,   "href":lambda x: get_value("a", { "class" : 'residential-card__info-text'} , x)['href']
        ,   "property_type":lambda x: get_value("span", { "class" : 'residential-card__property-type'}, x).get_text(strip=True)
        ,   "sale_date":lambda x: get_value("span", { "class" : 'residential-card__with-comma'}, x).get_text(strip=True)
        ,   "beds":lambda x: get_value("span", { "class" : 'general-features__icon general-features__beds'}, x).get_text(strip=True)
        ,   "bathrooms":lambda x: get_value("span", { "class" : 'general-features__icon general-features__baths'}, x).get_text(strip=True)
        ,   "parking":lambda x: get_value("span", { "class" : 'general-features__icon general-features__cars'}, x).get_text(strip=True)
        })
       
       
### Text files to aggreage on 
txt_files = pd.DataFrame({'filename':pd.Series(os.listdir(scrape_area_dir))})
txt_files = txt_files[txt_files['filename'].str.contains('_p|.txt')]
txt_files['suburb'] = txt_files['filename'].str.split('-\d_p',expand=True)[0]
txt_files['suburb'].value_counts()
txt_files['suburb'][txt_files['suburb'].str.contains('_p')] = np.NaN
txt_files = txt_files.query('suburb==suburb')

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
for row in range(len(suburb_list)):     # row = 0   suburb = 'surry+hills-nsw-2010'
    suburb = suburb_list[row]
    if os.path.exists(suburb_dir+'/'+suburb+'.csv') ==False:
        s_t1 = time.time()
        suburb_files = txt_files.query('suburb=="'+suburb+'"')[['filename']]
        suburb_files['page_no'] = suburb_files['filename'].str.extract('_p(.*?).txt').astype(int)
        suburb_files = suburb_files.sort_values('page_no')
        #
        master_df = pd.DataFrame()
        for filename in  suburb_files['filename']: # filename =suburb_files['filename'].iloc[0]
            s_t = time.time()
            print(filename)
            # get data
            rawdata = open(scrape_area_dir + '/' + filename,"r").read()
            soup = BeautifulSoup(rawdata)
            #######
            ## PULL Attributes
            # verions 0 scrape
            find_sold = pd.Series(soup.findAll("div", { "class" : 'property-card__content'}))
            sold_info = find_sold.apply(lambda x: fields_funcs.apply(lambda f: f(x)))
            if len(sold_info)==0:
                find_sold = pd.Series(soup.findAll("div", { "class" : 'residential-card__content-wrapper'}))
                sold_info = find_sold.apply(lambda x: fields_funcs_v2.apply(lambda f: f(x)))
            master_df = pd.concat([master_df, sold_info], axis = 0)
            #
            e_t = time.time()
            print('Time taken: %s seconds for %d files' % (round(e_t-s_t,2),len(master_df)))
            ## update file extraction
            extracted = pd.DataFrame({'f':filename,'listings':len(sold_info)},index=[0])
            trackerDF = pd.concat([trackerDF,extracted],axis=0,ignore_index=True)
        # 
        if master_df.shape[0] > 0 :
            # write file
            master_df= master_df[fields_funcs_v2.keys()]
            master_df = master_df.apply(lambda x: x.str.encode('utf-8'),axis=0)
            master_df.to_csv(suburb_dir+'/'+suburb+'.csv',index=False)
            e_t1 = time.time()
            print('Suburb Time taken: %s seconds for %d files' % (round(e_t1-s_t1,2),len(master_df)))
        #
        #
trackerDF.to_csv(output_directory + '01b Suburb_Files/' + dateid +'_realestate_row1.csv',index=False)
        
        
#### END LOOP 








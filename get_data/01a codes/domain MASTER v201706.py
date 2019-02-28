
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
dateid = str(20170820)
print (dateid)


## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
csv_output_dir = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"

os.listdir(os.path.dirname(output_directory))


final_dir  = output_directory + '01c Property_DF'
os.listdir(final_dir)


### Get seed postcodes
seed_poas = pd.read_csv(output_directory +  '01 domain_data_update_201607.csv' )
seed_poas['postcode'] = seed_poas['postcode'].astype(int).astype(str)
seed_poas['state'] =  seed_poas['state'].str.lower().str.strip()
seed_poas['suburb'] =  seed_poas['suburb'].str.lower().str.strip().str.replace('\s+', '-')

keep_poas = (seed_poas['postcode'].value_counts()>50)
keep_poas = keep_poas[keep_poas].index.values

seed_poas = seed_poas[seed_poas['postcode'].isin(keep_poas)]


##  Create final area_counts
area_counts = pd.pivot_table(seed_poas, index = ['suburb','state','postcode'], values = 'sale_date', aggfunc = len).reset_index()
del seed_poas
# wrap up final words to iter
area_counts = area_counts[area_counts['state'] == 'nsw']
area_counts['area_sydney'] = area_counts.apply(lambda x: '-'.join(x[['suburb','state','postcode']]),axis = 1)


##
template_url = 'https://www.domain.com.au/sold-listings/###AREA_SYDNEY###/?sort=solddate-desc&page=#PAGE#'



## STEP 2 SET FunctionFOR HREF
def get_hrefs(a):
    href_i = a.split('href="')[1]
    href_i = href_i.split('"')[0]
    return(href_i);\


#### drivers
rows = len(area_counts['area_sydney'])
iters = 5
leni = len(area_counts)
len_iter = leni/iters

rows1 = range( len_iter * 1 - len_iter ,len_iter * 1)
rows2 = range( len_iter * 2 - len_iter ,len_iter * 2)
rows3 = range( len_iter * 3 - len_iter ,len_iter * 3)
rows4 = range( len_iter * 4 - len_iter ,len_iter * 4)
rows5 = np.setdiff1d(range(rows),  range( leni/iters * 5 - leni/5))


scrape_area_dir =  output_directory + '01a Region href property/' + dateid +'_domain.com'
if os.path.exists(scrape_area_dir) == False :
    os.mkdir(scrape_area_dir)


max_page = 50



## manual fixe
area_counts['area_sydney'] = area_counts['area_sydney'].str.replace('brightonlesands','brighton-le-sands')


# region = regions[1]
#for row in np.setdiff1d(rows1,[947,1047]):           # row = rows2[0]
#    #
#    region = area_counts['area_sydney'].iloc[row]
#    print(region)
#
#    #
#    ## STEP 1 IDENTIFY URL
#    url_domain = template_url.replace("###AREA_SYDNEY###", region)
#    #
#    ## STEP 3: INITIALISE VALUES
#    no_hrefs = False;\
#    page_no = np.array(1);\
#    total_start = time.time();\
#    #
#    ## STEP 4:  GET PAGES
#    for page_no in range(1,max_page + 1):
#        # create directory
#        output_name = scrape_area_dir + '/' + region +'_p' +str(page_no) + '.txt'
#        if os.path.exists(output_name):
#            continue      
#        else:
#            #        
#            print("Iterating Through Page: %s" % page_no)
#            start = time.time()
#            domain_url = url_domain.replace("#PAGE#",str(page_no))
#            #
#            html = urlopen(domain_url).read();\
#            #
#            #               
#            text_file = open(output_name, "w")
#            text_file.write(html)
#            text_file.close()
#            #
#            print("Time taken: --- %s seconds ---" % (time.time() - start))
#    #       
#    print("Time taken: --- %s seconds ---" % (time.time() - total_start))

##### END LOOP 





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

suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_domain.com'
if os.path.exists(suburb_dir) == False :
    os.mkdir(suburb_dir)

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
txt_files['suburb'] = txt_files['filename'].str.split('_p',expand=True)[0]
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

#for suburb in suburb_list[rows4]:     # suburb = 'abbotsbury-nsw-2176'
#    if os.path.exists(suburb_dir+'/'+suburb+'.csv') ==False:
#        s_t1 = time.time()
#        suburb_files = txt_files.query('suburb=="'+suburb+'"')[['filename']]
#        suburb_files['page_no'] = suburb_files['filename'].str.extract('_p(.*?).txt').astype(int)
#        suburb_files = suburb_files.sort_values('page_no')
#        #
#        master_df = pd.DataFrame()
#        for filename in  suburb_files['filename']: # filename =suburb_files['filename'].iloc[0]
#            s_t2 = time.time()
#            print('\t '+filename)     # filename = 'abbotsbury-nsw-2176_p2.txt'
#            # get data
#            rawdata = open(scrape_area_dir + '/' + filename,"r").read()
#            soup = BeautifulSoup(rawdata)
#            #
#            find_sold = pd.Series(soup.findAll("li", { "class" : 'strap new-listing'}))
#            if len(find_sold)==0:
#                find_sold = pd.Series(soup.findAll("li", { "class" : 'search-results__listing'}))
#            sold_info = find_sold.apply(lambda x: fields_funcs.apply(lambda f: f(x)))
#            if sold_info.shape[0]> 0:
#                sold_info['filename'] = filename
#                master_df = pd.concat([master_df, sold_info], axis = 0,ignore_index=True)
#            #
#            e_t2 = time.time()
#            print('\t Page Time taken: %s seconds for %d files' % (round(e_t2-s_t2,2),len(master_df)))
#        # 
#        # write file
#        master_df = master_df.apply(lambda x: x.str.encode('utf-8'),axis=0)
#        master_df.to_csv(suburb_dir+'/'+suburb+'.csv',index=False)
#        e_t1 = time.time()
#        print('Suburb Time taken: %s seconds for %d files' % (round(e_t1-s_t1,2),len(master_df)))
##### END LOOP 

#######################################################################
# Build Master

suburb_files = pd.DataFrame({'suburb':os.listdir(suburb_dir)})
suburb_files['size'] = suburb_files['suburb'].apply(lambda x: os.stat(suburb_dir+'/'+x).st_size)
# filters
suburb_files = suburb_files.query('suburb <> ".DS_Store"  and size > 100')


master_df = pd.DataFrame()
for suburb in suburb_files['suburb'].values:         # suburb = suburb_files.values[0]
    print(suburb)
    suburb_df = pd.read_csv(suburb_dir +'/'+ suburb)
    suburb_df = suburb_df.query('details==details')
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)

####################
pd.options.display.max_columns = 28

master_df['index'] = master_df.index.values

# get attributes out of details
detail_df = master_df['details'].copy()
detail_df = detail_df.str.replace('0 parkings','0|parking|')
detail_df = detail_df.str.replace('0 beds','0|bed|')
detail_df = detail_df.str.replace('0 baths','0|bath|')
detail_df = detail_df.str.replace('parkings','parking|')
detail_df = detail_df.str.replace('beds','bed|')
detail_df = detail_df.str.replace('baths','bath|')
detail_df = detail_df.str.split('|',expand=True)

# step 1: Pull out Date and Sold Type
master_df['DateID'] = pd.to_datetime(detail_df[0].apply(lambda x: x[(len(x)-11):]),format='%d %b %Y',errors='coerce')
master_df['DateID'].isnull().value_counts()

detail_df['datestr'] = master_df['DateID'].dt.strftime('%d %b %Y').fillna('')
master_df['SoldType'] = detail_df.apply(lambda x: x[0].replace(x['datestr'],''),axis=1).str.strip()
detail_df = detail_df.drop([0,'datestr'],axis=1)

# price
price_col = detail_df.apply(lambda x: x.str.contains('[$]|Price'),axis=0).sum(axis=0)
master_df['price'] = detail_df[price_col[price_col==price_col.max()].index.values]
detail_df = detail_df.drop(price_col[price_col==price_col.max()].index.values,axis=1)

## get street
master_df['street'] = detail_df.apply(lambda x: x[5] if 'price from' in x[3] else x[3],axis=1)
## Override for suburb
master_df['street'][master_df['street'].str.contains('[0-9]')==False] = np.NaN

#### Check how much of Street is null
master_df['street'].isnull().value_counts()

detail_df.loc[master_df.query('street <> street').index.values,[2,3,4,5]]


street_dup = master_df.groupby('street').size().reset_index().rename(columns={0:'n'})
street_dup['n'].value_counts()
street_dup.query('n==12')

##### GET ATTRIBUTES
detail_df = detail_df.reset_index()
get_attr = pd.melt(detail_df, id_vars='index')
get_attr = get_attr[get_attr['value'].str.replace('[^A-Za-z0-9]','').str.strip().str.len().fillna(0) > 0 ]
get_attr['value'] = get_attr['value'].str.replace('\s+',' ')

######
# street
get_attr['street'] = get_attr['value'].str.lower().str.contains('([0-9/abc]+) ([a-z]+)')


# bath/ bed/ parking
attr = ['bath','bed','parking']

get_attr['rowID'] = get_attr.index.values
get_attr['is_attr'] = get_attr['value'].apply(lambda x: 1 if x in attr else 0)
get_attr['is_attr'] = get_attr['is_attr'] * get_attr['rowID']
get_attr['is_attr'] = get_attr['is_attr'].apply(lambda x: np.NaN if x==0 else x)

print('check the values found for attr seeding')
print(get_attr.query('is_attr == is_attr and street == False')['value'].value_counts())
print(get_attr.query('street == True').shape)

### make bath/bed/parking count to position of attr
get_attr = get_attr.sort_values(['index','variable'])
get_attr['attrID'] = get_attr['is_attr'].fillna(method='bfill',limit=1)

print('This is all be 2s')
print(get_attr['attrID'].value_counts().value_counts())

### Attr only
attr_df = get_attr.query('attrID==attrID').copy()
attr_df['variable'] = attr_df['is_attr'].apply(lambda x: 'type' if x==x else 'value')
attr_df = attr_df.pivot(index='attrID',columns='variable',values='value' ).reset_index()
attr_df = pd.merge(
            attr_df
        ,   get_attr.groupby(['attrID','index']).size().reset_index().drop(0,axis=1)
        ,   on='attrID'
        ,   how='left'
        )
print('Check results')
print(attr_df.isnull().sum(axis=0))
### final mapping
attr_df = attr_df.pivot(index='index',columns='type',values='value')
attr_df = attr_df.reset_index()
### Apply mapping
master_df = pd.merge(
            master_df
        ,   attr_df
        ,   on='index'
        ,   how='left'
        )

##############################
### Final Delivery
##############################


## DomainID
master_df['domainid'] = master_df['domainid'].str.extract('([0-9]{10})')
# suburub and postcode
suburb_state = master_df['filename'].str.split('-nsw-',expand=True)
master_df['suburb'] = suburb_state[0]
master_df['postcode'] = suburb_state[1].str.extract('([0-9]{4})_p').astype(int)
## price
master_df['price'] = master_df['price'].str.replace('[$,]','')
master_df['price'] = master_df['price'].apply(lambda x: np.NaN if x == 'Price Withheld' else x)
master_df['price'] = master_df['price'].astype(float)

### CHECKS

master_df.isnull().sum(axis=0)
master_df.query('DateID <> DateID')


master_df['details'].loc[269]

### OUTPUT
delivery_col = ['domainid','latitude','longitude','DateID',
                'SoldType','price','street','suburb','postcode',
                'bath','bed','parking']


master_df[delivery_col].to_csv(final_dir  + '/'+dateid+'_domain.csv',index=False)












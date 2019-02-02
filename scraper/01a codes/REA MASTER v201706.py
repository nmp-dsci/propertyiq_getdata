
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
seed_poas['suburb'] =  seed_poas['suburb'].str.lower().str.strip().str.replace('\s+', '+')


keep_poas = (seed_poas['postcode'].value_counts()>50)
keep_poas = keep_poas[keep_poas].index.values

seed_poas = seed_poas[seed_poas['postcode'].isin(keep_poas)]

##  Create final area_counts
area_counts = pd.pivot_table(seed_poas, index = ['suburb','state','postcode'], values = 'sale_date', aggfunc = len).reset_index()
del seed_poas
# wrap up final words to iter
area_counts = area_counts[area_counts['state'] == 'nsw']


##
template_url = 'https://www.realestate.com.au/sold/in-###SUBURB###%2c+###STATE###+###POSTCODE###/list-#PAGE#?includeSurrounding=false&activeSort=solddate'


## STEP 2 SET FunctionFOR HREF
def get_hrefs(a):
    href_i = a.split('href="')[1]
    href_i = href_i.split('"')[0]
    return(href_i);\


#### drivers
rows = len(area_counts['suburb'])
iters = 5
leni = len(area_counts)
len_iter = leni/iters

rows1 = range( len_iter * 1 - len_iter ,len_iter * 1)
rows2 = range( len_iter * 2 - len_iter ,len_iter * 2)
rows3 = range( len_iter * 3 - len_iter ,len_iter * 3)
rows4 = range( len_iter * 4 - len_iter ,len_iter * 4)
rows5 = np.setdiff1d(range(rows),  range( leni/iters * 5 - leni/5))


scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_realestate.com'
if os.path.exists(scrape_area_dir) == False :
    os.mkdir(scrape_area_dir)


max_page = 50

###SUBURB###
###STATE###
###POSTCODE###
#PAGE#
#
## region = regions[1]
#for row in rows4:           # row = rows2[0]
#    ## STEP 1 IDENTIFY URL
#    url_domain = template_url.replace("###SUBURB###", area_counts.iloc[row]['suburb'])
#    url_domain = url_domain.replace("###STATE###", area_counts.iloc[row]['state'])
#    url_domain = url_domain.replace("###POSTCODE###", area_counts.iloc[row]['postcode'])
#    #
#    region = '-'.join(area_counts[['suburb','state','postcode']].iloc[row])
#    ## STEP 3: INITIALISE VALUES
#    no_hrefs = False;\
#    page_no = np.array(1);\
#    total_start = time.time();\
#    ## get max page
#    find_max_pages = urlopen(url_domain.replace("#PAGE#",str(page_no))).read()
#    soup = BeautifulSoup(find_max_pages)
#    # find class, max page
#    find_max = soup.findAll("p", { "class" : "results-set-footer__heading" })
#    if len(find_max) == 0:
#        print('couldnt find page max')
#        #break
#        max_page = 50
#    else:
#        find_max = pd.Series(find_max[0].string)
#        find_max = pd.Series(find_max.str.split('[^0-9]')[0])
#        max_page = (find_max[find_max.str.len() == find_max.str.len().max() ]).astype(int).max()
#        max_page = max_page/20.0
#        max_page = 50 if max_page > 50 else int(np.ceil(max_page))
#    #
#    ## STEP 4:  GET PAGES
#    for page_no in range(1,max_page + 1): 
#        print("Iterating Through Page: %s" % page_no)
#        start = time.time()
#        domain_url = url_domain.replace("#PAGE#",str(page_no))
#        # create directory
#        output_name = scrape_area_dir + '/' + region +'_p' +str(page_no) + '.txt'
#        if os.path.exists(output_name):
#            continue          
#        #
#        #
#        html = urlopen(domain_url).read();\
#        #
#        #               
#        text_file = open(output_name, "w")
#        text_file.write(html)
#        text_file.close()
#        #
#        print("Time taken: --- %s seconds ---" % (time.time() - start))
#    #       
#    print("Time taken: --- %s seconds ---" % (time.time() - total_start))

##### END LOOP 





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

suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_realestate.com'
if os.path.exists(suburb_dir) == False :
    os.mkdir(suburb_dir)


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

#for suburb in suburb_list[rows5]:     # suburb = suburb_list[rows4][0]
#    if os.path.exists(suburb_dir+'/'+suburb+'.csv') ==False:
#        s_t1 = time.time()
#        suburb_files = txt_files.query('suburb=="'+suburb+'"')[['filename']]
#        suburb_files['page_no'] = suburb_files['filename'].str.extract('_p(.*?).txt').astype(int)
#        suburb_files = suburb_files.sort_values('page_no')
#        #
#        master_df = pd.DataFrame()
#        for filename in  suburb_files['filename']: # filename =suburb_files['filename'].iloc[0]
#            s_t = time.time()
#            print(filename)
#            # get data
#            rawdata = open(scrape_area_dir + '/' + filename,"r").read()
#            soup = BeautifulSoup(rawdata)
#            #
#            find_sold = pd.Series(soup.findAll("div", { "class" : 'property-card__content'}))
#            sold_info = find_sold.apply(lambda x: fields_funcs.apply(lambda f: f(x)))
#            master_df = pd.concat([master_df, sold_info], axis = 0)
#            #
#            e_t = time.time()
#            print('Time taken: %s seconds for %d files' % (round(e_t-s_t,2),len(master_df)))
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
    suburb_df['filename'] = suburb
    #suburb_df = suburb_df.query('details==details')
    master_df = pd.concat([master_df,suburb_df],axis=0,ignore_index=True)


# suburub and postcode
suburb_state = master_df['filename'].str.split('-nsw-',expand=True)
master_df['suburb'] = suburb_state[0]
master_df['postcode'] = suburb_state[1].str.extract('([0-9]{4}).csv').astype(int)


################
## Price
master_df['price'] = master_df['price_str'].str.replace('[$,]','')
master_df['price'] = master_df['price'].apply(lambda x: np.NaN if x == 'Contact agent' else x)

### fix for Range
find_range = master_df['price'].str.contains('Range').fillna(False)
range_str = master_df['price'][find_range].str.split(' ',expand=True).reset_index()
range_str = pd.melt(range_str, id_vars = 'index')
range_str = range_str[range_str['value'].isin(['','-']) ==False]
### create interger
range_str2 = range_str[range_str['value'].str.replace('[a-z ]','').str.len() == range_str['value'].str.len()]
range_str2['value'] = range_str2['value'].astype(int)

### Apply 
master_df['price'][find_range] = range_str2.groupby('index')['value'].median()
master_df['price'] = master_df['price'].astype(float)



pd.crosstab(
            master_df['price'].isnull()
        ,   master_df['price_img'] <> 'missing'
        )


#####################
## TO CSV
master_df.to_csv(final_dir  + '/'+dateid+'_realestate.csv',index=False)










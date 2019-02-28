
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

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
os.listdir(os.path.dirname(output_directory))

## Get data
dateid =  pd.Series(os.listdir(output_directory + '01a Region href property')).str.extract('(\d{8})_').max()
dateid = "20180524"
print (dateid)

final_dir  = output_directory + '01c Property_DF'
last_dateid = pd.Series(os.listdir(final_dir))
last_dateid = last_dateid[~last_dateid.str.contains(dateid)]
last_dateid = last_dateid.str.extract('(\d{8})',expand=False).astype(float).max().astype(int).astype(str)
print('last Data Scrape: %s' % (last_dateid))

scrape_area_dir =  output_directory + '01a Region href property/' + dateid  + '_REA'

suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_REA'
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

fields_funcs_v3 = pd.Series({
            "price_str":lambda x: get_value("span", { "class" : 'property-price'}, x).get_text(strip=True)
        ,   "price_img":lambda x: get_value("img", { "class" : 'property-price__image'}, x)['src']
        ,   "address":lambda x: get_value("div", { "class" : 'residential-card__info-text'}, x).get_text(strip=True)
        ,   "href":lambda x: get_value("a", { "class" : 'details-link residential-card__details-link'} , x)['href']
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

iters = 1
leni = len(suburb_list)
len_iter = leni/iters

rows1 = range( len_iter * 1 - len_iter ,len_iter * 1)
#rows2 = np.setdiff1d(range(leni),  rows1)
#rows3 = range( len_iter * 3 - len_iter ,len_iter * 3)
#rows4 = range( len_iter * 4 - len_iter ,len_iter * 4)
#rows5 = np.setdiff1d(range(leni),  rows1+rows2+rows3 + rows4)

trackerDF = pd.DataFrame()
#for row in range(len(suburb_list)):     # row = 0   suburb = 'surry+hills-nsw-2010'
for row in rows1:     # row = 0   suburb = 'allambie+heights-nsw-2100'
    suburb = suburb_list[row]
    if os.path.exists(suburb_dir+'/'+suburb+'.csv') ==False:
        s_t1 = time.time()
        suburb_files = txt_files.query('suburb=="'+suburb+'"')[['filename']]
        suburb_files['page_no'] = suburb_files['filename'].str.extract('_p(.*?).txt').astype(int)
        suburb_files = suburb_files.sort_values('page_no')
        #
        master_df = pd.DataFrame()
        #master_df = pd.DataFrame({
        #        'domainid':pd.Series([],dtype=int)
        #    ,   'value':pd.Series([],dtype=str)
        #})
        for filename in  suburb_files['filename']: # filename =suburb_files['filename'].iloc[0]
            s_t = time.time()
            print(filename)
            # get data
            rawdata = open(scrape_area_dir + '/' + filename,"r").read()
            soup = BeautifulSoup(rawdata)
            #######  soup.findAll('2627339')
            ## PULL Attributes
            # verions 0 scrape
            # iter 1
            find_sold1 = pd.Series(soup.findAll("div", { "class" : 'property-card__content'}))
            sold_info1 = find_sold1.apply(lambda x: fields_funcs.apply(lambda f: f(x)))
            # iter 2
            find_sold2 = pd.Series(soup.findAll("div", { "class" : 'residential-card__content-wrapper'}))
            sold_info2 = find_sold2.apply(lambda x: fields_funcs_v2.apply(lambda f: f(x)))
            # iter 3
            find_sold3 = pd.Series(soup.findAll("article", { "class" : 'results-card residential-card '}))
            sold_info3 = find_sold3.apply(lambda x: fields_funcs_v3.apply(lambda f: f(x)))
            ## Create sold info
            sold_info = pd.concat([sold_info1,sold_info2,sold_info3])
            if sold_info.shape[0]> 0:
                sold_info = sold_info.query('href <> "missing"')
            # now pull the pretty dictionary with all the data at the end of the page
            if sold_info.shape[0]> 0:
                sold_info['REAid'] = sold_info['href'].str.extract('-(\d+)')
                sold_info['extract'] = sold_info['REAid'].apply(lambda x: pd.Series(soup.decode()).str.extract('({"channel":"sold","listingId":"'+x+'".*)',expand=False))
                sold_info.index = sold_info['REAid']
                extract_df = sold_info['extract'].str.split(',"lister":',expand=True)
                sold_info['extract'] = extract_df[0]+'}'  # fir cut of the data
                # this string is in another language but a dictionary, so fix coding language discrepancies
                replace_df = {':null':':None',':true':':True',':false':':False'}
                for word in replace_df.keys(): # word = replace_df.keys()[0]
                    sold_info['extract'] = sold_info['extract'].str.replace(word,replace_df[word])
                ## build final dictionary
                #####new_dict.keys()
                ## required fields:
                # 'key','variable','value'
                rename_df ={'index':'variable',0:'value'}
                def series_df(x={'a':1,'b':2},key='test'):
                    outDF = pd.Series(x).reset_index()
                    outDF['key'] = key
                    outDF = outDF.rename(columns = rename_df)
                    return outDF
                def dict_df(x={'a':1,'b':{'c':2,'d':3},'e':4},key='test'):
                    types = pd.Series(dict(zip(x.keys(),[str(type(x[a])) for a in x.keys()]))).reset_index().rename(columns={0:'c'})
                    types['c'] = types['c'].str.extract("'([a-z]+)'",expand=False)
                    outDF = pd.concat(
                            [pd.DataFrame({'variable':o,'value':x[o]},index=[0]) for o in types.query('c<>"dict"')['index']]
                    ,axis=0)
                    #now dictionaries
                    for o in types.query('c=="dict"')['index']:
                        outDF = pd.concat([outDF,pd.Series(x[o]).reset_index().rename(columns=rename_df)],axis=0)
                    outDF['key'] = key
                    return outDF
                def single_df(x = 'established',key='constructionStatus'):
                    outDF =pd.Series({key:x}).reset_index().rename(columns=rename_df)
                    outDF['key'] = key
                    return outDF
                def multi_dict(x=[{'a':1,'b':2},{'a':1,'b':2}], key= 'test'):
                    outDF = pd.DataFrame(x).reset_index().melt(id_vars='index')
                    outDF['index'] = key + outDF['index'].astype(str)
                    outDF = outDF.rename(columns={'index':'key'})
                    return outDF
                def record_dict(x = {'a':{'aa':1,"bb":2},'b':{'aa':11,'bb':22}},key = 'test'):
                    outDF = pd.DataFrame(x).reset_index().melt(id_vars = 'index').rename(columns={'variable':'key'}).rename(columns=rename_df)
                    outDF['key'] = key +'_'+ outDF['key']
                    return outDF
                #### The Rules DF
                extract_rules = {           # x = new_dict['status']
                    'status':lambda x:              series_df(x,key='status')
                ,   'description': lambda x:        series_df(x,key='description')
                ,   'price':lambda x:               series_df(x,key='price')
                ,   'address':lambda x:             dict_df(x, key = 'address')
                ,   'constructionStatus':lambda x:  single_df(x, key='constructionStatus')
                ,   'prettyUrl':lambda x:           series_df(x,key='prettyUrl')
                ,   'propertyType': lambda x:       series_df(x,key='propertyType')
                ,   'images': lambda x:             multi_dict(x, key='images')
                ,   'listers': lambda x:            multi_dict(x, key='listers')
                ,   'dateSold': lambda x:           series_df(x,key='dateSold')
                ,   'generalFeatures':lambda x:     record_dict(x, key='generalFeatures')
                ,   'features':lambda x:            record_dict(x, key='features')
                ,   'mainImage':lambda x:           series_df(x,key='mainImage')
                }
                ####
                #print('Dictionary Extraction')
                s_dd = time.time()
                info_extract = pd.DataFrame()
                for idx in sold_info['extract'].index.values:
                    #print(idx)
                    new_dict = eval(sold_info['extract'].loc[idx])
                    extract_df = pd.DataFrame()
                    for k in extract_rules.keys():    # k = 'address'
                        if k in new_dict.keys():
                            new_info = extract_rules[k](x=new_dict[k])
                            extract_df = pd.concat([extract_df,new_info],axis=0)
                            extract_df['REAid'] = idx
                    info_extract = pd.concat([info_extract,extract_df],axis=0)
                e_dd = time.time()
                print('Dictionary Extraction Time Taken: %0.2f seconds' % (e_dd-s_dd))
                """
                ### pull all together
                """
                keep_fields = ['address','bathrooms','beds','href','parking','price_img','price_str','property_type','sale_date']
                sold_info = sold_info.melt(id_vars = ['REAid'], value_vars=keep_fields)
                sold_info['key'] = 'HTML'
                ### Append
                sold_info = pd.concat([sold_info,info_extract],axis=0)
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
            def encode(x = 'aaa'):
                try :
                    return str(x).encode('utf-8')
                except:
                    return re.sub('[^A-Za-z0-9 ]','',x)
            master_df['value'] = master_df['value'].apply(lambda x: encode(x))
            master_df.to_csv(suburb_dir+'/'+suburb+'.csv',index=False)
            e_t1 = time.time()
            print('Suburb Time taken: %s seconds for %d files' % (round(e_t1-s_t1,2),len(master_df)))
        #
        #
trackerDF.to_csv(output_directory + '01b Suburb_Files/' + dateid +'_realestate.csv',index=False)


#### END LOOP

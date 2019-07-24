
### IMPORT Libraries
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import re,time,os,sys
import time,json
import datetime
import math
from bs4.element import Tag

sys.path.append('/Users/macmac/Documents/GitHub/propertyiq_getdata')

from config import * 
from utils import * 

## Get data
sourceid = 'domain'

scrape_area_dir = output_directory+'01a Region href property/'+dateid +'_'+sourceid

suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_'+sourceid
if os.path.exists(suburb_dir) == False :
    os.mkdir(suburb_dir)

#######################################################################
#### functiosn for search page
#
#attr_df = {
#    'DomainID': {'comments':'','format':''}
#   ,'sale type': {'comments':'type and date','format':''}
#   ,'price': {'comments':'','format':''}
#   ,'address line 1': {'comments':'','format':''}
#   ,'address line 2': {'comments':'suburb/ region/ postcode/ latitude/ longitude','format':''}
#   ,'beds': {'comments':'','format':''}
#   ,'bathrooms': {'comments':'','format':''}
#   ,'parking': {'comments':'','format':''}
#   }


fields_funcs = pd.Series({
            "domainid":lambda x:  re.search('\d{10}',x.decode()).group()
        ,   "details": lambda x: x.get_text(separator=str('|'))
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

trackerDF = pd.DataFrame()
for suburb in suburb_list:     
    print(suburb)
    if os.path.exists(suburb_dir+'/'+suburb+'.csv') ==False:
        s_t1 = time.time()
        suburb_files = txt_files.query('suburb=="'+suburb+'"')[['filename']]
        suburb_files['page_no'] = suburb_files['filename'].str.extract('_p(.*?).txt').astype(int)
        suburb_files = suburb_files.sort_values('page_no')
        #  create a flag for if the amount of properties pulled is off
        last_block = 'NO_BLOCK'
        last_page_blocks = 999
        #
        master_df = pd.DataFrame({
                'domainid':pd.Series([],dtype=int)
            ,   'value':pd.Series([],dtype=str)
        })
        for filename in  suburb_files['filename']: # filename =suburb_files['filename'].iloc[1]
            s_t2 = time.time()
            print('\t '+filename)     # filename = 'kirribilli-nsw-2061_b1_p1.txt'
            # get data
            rawdata = open(scrape_area_dir + '/' + filename,"r").read()
            soup = BeautifulSoup(rawdata)
            #  Find the property listing blocks
            find_sold = pd.Series(soup.findAll("li", { "class" : 'strap new-listing'}))
            if len(find_sold)==0:
                find_sold = pd.Series(soup.findAll("li", { "class" : 'search-results__listing'}))
            if len(find_sold)==0:
                find_sold = pd.Series(soup.findAll("li", {}))
                find_sold = find_sold[find_sold.apply(lambda x: x.get('data-testid') is not None)]
            else:
                print("cant find listings!!")
                break
            ## pull results
            # find_sold = find_sold[find_sold.apply(lambda x: 'href' in x)]
            # clean out anything without a 'href' ... no property id
            sold_info = find_sold.apply(lambda x: fields_funcs.apply(lambda f: f(x)))
            ## update last_page_blocks
            same_block = re.search('(.*)_p',filename).group(0) == last_block
            if  same_block and last_page_blocks < 20:
                print('Error same block but didnt extract 20 blocks LaST time and still running')
                #break
            # now pull the pretty dictionary with all the data at the end of the page
            if sold_info.shape[0]> 0:
                # with domainIDs find addtional          x = sold_info['domainid'][0]   '{"id":'+x+'.*}}}'
                sold_info['extract'] = sold_info['domainid'].apply(lambda x: pd.Series(str(soup)).str.extract('({"id":'+x+'.*})',expand=False))
                sold_info = sold_info.query('extract == extract')
                ## 'str.extract' is a 'greedy' matcher so only take first time it matches "}}}" not last time
                sold_info['extract'] = sold_info['extract'].str.split('}}}',expand=True)[0].apply(lambda x: x+'}}}')
                # this string is in another language but a dictionary, so fix coding language discrepancies
                replace_df = {'\:null':':None','\:true':':True','\:false':':False'}
                for word in replace_df.keys(): # word = replace_df.keys()[0]
                    sold_info['extract'] = sold_info['extract'].str.replace(word,replace_df[word])
                ## build final dictionary
                info_extract = pd.DataFrame()
                for idx in sold_info['extract'].index.values:
                    #print(idx)
                    new_info = pd.DataFrame(eval(sold_info['extract'].str.strip().loc[idx])).reset_index()
                    new_info = new_info.rename(columns={'index':'key','id':sourceid+'id'}).drop('listingType',axis=1)
                    info_extract = pd.concat([info_extract, new_info],axis=0, ignore_index=True)
                # now combine final set
                info_extract['listingModel_class'] = info_extract['listingModel'].apply(lambda x: '%s' % type(x)).str.extract("'(.*)'",expand=False)
                # TREAT dictionaries
                info_extract = pd.concat([
                        info_extract
                    ,   info_extract.query('listingModel_class == "dict"')['listingModel'].apply(lambda x: pd.Series(x))
                    ], axis = 1)
                # TREAT lists
                info_extract = pd.concat([
                        info_extract
                    ,   info_extract.query('listingModel_class == "list"').apply(lambda x:
                                pd.Series(dict(zip(
                                       [x['key']+str(i) for i in range(len(x['key']))]
                                    ,   x['listingModel']))
                                    ),axis=1)
                    ],  axis=1)
                ### Treat Booleans and Str
                info_extract = pd.concat([
                        info_extract
                    ,   info_extract.query('listingModel_class in ["str","bool"]').apply(lambda x:
                                pd.Series({x['key']:x['listingModel']})
                                    ,axis=1)
                    ],  axis=1)
                #### now melt down dataset
                id_vars = ['key',sourceid+'id']
                exclude = [ 'listingModel', 'listingModel_class']
                value_vars = np.setdiff1d(info_extract.columns.values, id_vars+exclude)
                info_extract = info_extract.melt(id_vars = id_vars, value_vars = value_vars)
                info_extract = info_extract.query('value==value')
                ### now append sold info
                sold_info2 = sold_info.melt(id_vars=[sourceid+'id'],value_vars=['details','latitude','longitude'])
                sold_info2['key'] = sold_info2['variable']
                info_extract = pd.concat([
                        info_extract
                    ,   sold_info2
                    ],  axis=0)
                ## NaN override, add file name
                info_extract['value'] = info_extract['value'].apply(lambda x: np.NaN if x == '' else x)
                info_extract = info_extract.query('value == value')
                info_extract['filename'] = filename
                info_extract[sourceid+'id'] = info_extract[sourceid+'id'].astype(int)
                #info_extract = info_extract.apply(lambda x: x.str.encode('utf-8',errors='ignore') if x.dtype == 'O' else x ,axis=0)
                ## append
                master_df = pd.concat([master_df, info_extract], axis = 0,ignore_index=True)
                ## last block extract update
                last_page_blocks = info_extract[sourceid+'id'].nunique()
            #
            e_t2 = time.time()
            print('\t Page Time taken: %s seconds for %d files' % (round(e_t2-s_t2,2),master_df[sourceid+'id'].nunique()))
            ## update file extraction
            extracted = pd.DataFrame({'f':filename,'listings':len(sold_info)},index=[0])
            trackerDF = pd.concat([trackerDF,extracted],axis=0,ignore_index=True)
            # add error detection vars
            last_block = re.search('(.*)_p',filename).group(0)
        #
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



trackerDF.to_csv(output_directory + '01b Suburb_Files/' + dateid +'_'+sourceid+'.csv',index=False)





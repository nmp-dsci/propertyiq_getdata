
####################
#
#   PURPOSE: GET NSW GOVERMENT DATA
#
#   DATE: 2015-12-20
#
#   STEPS
#       1.
#       2.
#       3.
#       4.
#       5.
#
#####################


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

suburb_dir =  output_directory + '01b Suburb_Files/' + dateid +'_nswgov'


##### build file as of today
filesDF = pd.Series(os.listdir(suburb_dir))
filesDF = filesDF[filesDF.str.contains('\w+-\w+.csv')]

def createDF(files=[]):
    coreDF = pd.DataFrame()
    for filei in files: # filei = '2830-BROCKLEHURST.csv'
        fileDf = pd.read_csv(suburb_dir+'/' + filei)
        coreDF = pd.concat([coreDF, fileDf],axis=0)
    return(coreDF)

#### EXECUTE FUNCTION ACROSS 6 cores
s_time = time.time()
import multiprocessing as mp
cores = 8
p = mp.Pool(cores)
pool_results = p.map(createDF, np.array_split(filesDF.values,cores))
p.close()
p.join()
nswgov_DF = pd.DataFrame()
for result in pool_results:
    nswgov_DF = pd.concat([nswgov_DF,result],axis=0)
e_time = time.time()
# time taken === 577 seconds
print("step 1: time taken %s seconds" % (np.round(e_time-s_time,4)))

## 
nswgov_DF.columns = pd.Series(nswgov_DF.columns).str.replace('[^A-z]','')
nswgov_DF['SALEDATE'] = pd.to_datetime(nswgov_DF['SALEDATE'],format='%d %B %Y')

# find what is unique
nswgov_DF.apply(lambda x: x.nunique(),axis=0)/nswgov_DF.shape[0]

pn_df = nswgov_DF.groupby([     'PROPERTYNUMBER'
                           ,    'ADDRESS'
                           ,    'SALEDATE'
                           ,    'STRATANONSTRATA'])['SALEPRICE'].max()
  
pn_df = pn_df.reset_index()
# to 
pn_df.to_csv(final_dir+'/'+dateid+'_nswgov.csv',index=False)














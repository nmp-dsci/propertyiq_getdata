
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
dateid = '20180524'

## set directory
output_directory = "/Users/macmac/Documents/Property/20151207 Scape Sydney/"
final_dir  = output_directory + '01c Property_DF'
master_dir = output_directory + '01e Master_DF'

source ='auhouse'
#######################################################################
# Get files
filesDF = pd.DataFrame({'f':os.listdir(final_dir)})
filesDF = filesDF[filesDF.f.str.contains('_'+source)]

domain_df = pd.DataFrame({})
for fi in filesDF.f.values:
    newDF = pd.read_csv(final_dir +'/'+ fi)
    domain_df = pd.concat([domain_df,newDF],axis=0)

domain_df = domain_df.drop_duplicates('REAid',keep='first')

print(domain_df['REAid'].value_counts()).value_counts()



###
domain_df.to_csv(master_dir+'/'+dateid+'_'+source+'.csv',index=False)

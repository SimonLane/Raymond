# -*- coding: utf-8 -*-
"""
Created on Mon Oct  3 14:38:53 2022

@author: Ray Lee
"""

import pandas as pd


address = "/Users/Ray Lee/Documents/GitHub/Raymond/"


dataframe = pd.read_csv("%sLaserCalibration.txt" %(address), sep ='\t')

print(dataframe.head(10))
        
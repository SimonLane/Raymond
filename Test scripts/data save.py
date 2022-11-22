# -*- coding: utf-8 -*-
"""
Created on Fri Sep 30 19:43:20 2022

@author: Ray Lee
"""

import pandas as pd

lasers = [[405,     3932,   51773,  12,      6200,   'lin',  0.1276,  -406.11],
          [488,     6554,   58982,  6.83,    860,    'pow',  3e-08,   2.1936  ],
          [561,     13107,  58982,  183.6,   4480,   'pow',  1e-06,   2.002   ],
          [660,     49152,  65535,  51.2,    780,    'lin',  0.042,  -1959.3  ],
          [780,     5000,   20000,  0.1,     300,    'lin',  83.401,  -464.74 ],
          ]
address = "/Users/Ray Lee/Documents/GitHub/Raymond/"
headings = ["wav.","minVal","maxVal","minPow","maxPow","Eqn.","P1","P2"]

dataframe = pd.DataFrame(data=None,columns=["wav.","minVal","maxVal","minPow","maxPow","Eqn.","P1","P2"])
for row in lasers:
    print(row)
    dataframe.loc[len(dataframe)] = row


print(dataframe.shape)

dataframe.to_csv("%sLaserCalibration.txt" %(address), mode='w', index=True, sep ='\t')


        
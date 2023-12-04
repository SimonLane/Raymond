# -*- coding: utf-8 -*-
"""
Created on Thu Aug 17 18:31:35 2023

@author: Ray Lee
"""
import numpy as np
import matplotlib.pyplot as plt

# =============================================================================
# generate images for SLM
# =============================================================================
Xs = []
Ys = []
Zs = []
Is = []
n = 0
step = 45
range = step*6
target_image = np.zeros((1940, 1200), dtype='uint8')

for x in np.arange(int(960 - (range/2)), int(960 + (range/2)+step), step):
    for y in np.arange(int(600 - (range/2)), int(600 + (range/2)+step), step):
        for x2 in [-4,-3,-2,-1,0,1,2,3,4]:
            for y2 in [-4,-3,-2,-1,0,1,2,3,4]:
                Xs.append(x+x2)
                Ys.append(y+y2)
                Zs.append(0)
                Is.append(1)
                n+=1
                target_image[x+x2,y+y2] = 255
                
plt.imshow(target_image)
plt.show()
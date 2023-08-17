# -*- coding: utf-8 -*-
"""
Created on Mon Aug 14 16:55:27 2023

@author: Ray Lee
"""
import numpy as np
import imageio.v2 as imageio
import os



image_dir = 'C:/Program Files/Meadowlark Optics/Blink 1920 HDMI/Image Files/'

new_image = []
test_image = imageio.imread(os.path.join(image_dir, 'centergrid_FL+200.bmp'))
new_image = np.reshape(test_image[:,:,0], 1200*1920)






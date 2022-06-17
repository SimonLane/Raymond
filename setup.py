# -*- coding: utf-8 -*-
"""
Created on Wed Jun  8 18:15:19 2022

@author: Ray Lee
"""

from distutils.core import setup
import py2exe

setup(console=[{"script": "laserGUIv1.py"}])
# setup(windows=[{"script":"laserGUIv1.py"}], options={"py2exe":{"includes":["sip"]}})
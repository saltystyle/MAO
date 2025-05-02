#!/usr/bin/env python
__all__ = ["main"]

__doc__ = """Quick look for VDIF

Usage: vdif-qlook [-f <PATH>] [--folder <PATH>] [--pattern <pattern>] [--integ <T>] [--delay <T>] [--interval <T>] [--chbin <N>] [--cal <T>] [--sample <N>]

-f <PATH>       Input VDIF file.
--folder <PATH>  
--pattern <pattern>
--integ <T>     Integration time in seconds [default: 1e-2]. #積分時間
--delay <T>     Time delay for plot in seconds [default: 0.0].
--interval <T>  Plot interval time in seconds [default: 1.0]. #プロット間隔時間
--chbin <N>     Number of channels to bin [default: 8].
--cal <T>       Calibration time in seconds [default: 1e-2].
--sample <N>     滞在時間のサンプル数[default: 5]
-h --help       Show this screen and exit.
-v --version    Show version and exit.

"""



__author__ = "Shion Takeno"
__version__ = "0.1.1"


# standard library
import time
from pathlib import Path


# dependencies
import numpy as np
import matplotlib.pyplot as plt
import os
from docopt import docopt
from .reader1 import  get_cal_spectrum, generate_patterned, get_nth_spectrum_in_range, convert_spectrum_to_epl, get_n_from_current_time

import re
from typing import Pattern
import csv 
import datetime

def main() -> None:
    #print(f"__doc__: {__doc__}")
    #print(f"__version__: {__version__}")
    args = docopt(__doc__, version=__version__) #コマンドライン
    path = Path(args["-f"]).resolve()
    folder = Path(args["--folder"]).resolve()
    pattern = str(args["--pattern"])
    integ = float(args["--integ"])
    delay = float(args["--delay"])
    interval = float(args["--interval"])
    chbin = int(args["--chbin"])
    cal = float(args["--cal"])
    sample = int(args["--sample"])
    
     
    n_offset_2024 = 2
    
    
    #feed
    feed = ["c", "t", "r", "b", "l"]
    pattern = generate_patterned(pattern, sample, n_offset_2024)
    pattern_len = len(pattern)
    m = []
    for i in range(5):
        m.append(pattern.find(feed[i]))

    spec_zero = 0   
    
    #キャリブレーション
    spec_cal = []
    #n = get_n_from_current_time(path, delay)
    n=40    
    for i in range(5):
        if m[i] != -1:
            l = (n - n%pattern_len -pattern_len) + m[i] 
            spectrum_cal = get_cal_spectrum(path, l, cal, delay, chbin)
            spec_cal.append(spectrum_cal)  
        else:
            spec_cal.append(0)    

    
    csv_path = path.with_suffix(".csv")
    csv_file = f'{folder}/{csv_path.name}'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)   
        # ヘッダーを書き込む
        writer.writerow(["time", "c", "t", "r", "b", "l"])
        
    while True:
        #s = datetime.datetime.now() 
        spec_epl = []      
       
        #最新のspecとepl
        #n = get_n_from_current_time(path, delay)
        n=n+1
        now = datetime.datetime.now()  
        now_time = now.strftime('%Y%m%d %H:%M:%S.%f')[:-3]
        for i in range(5):
            if m[i] == -1: #pattern内に文字が一致しなければ空で返す
                spectrum = spec_zero
                spec_epl.append(0)
            else:
                for j in range(n, -1, -1):
                    if pattern[j % pattern_len] == feed[i]:                                        
                        spectrum = get_nth_spectrum_in_range(path, j, integ, delay, chbin)  
                        spectrum /= spec_cal[i]                    
                        spec_epl.append(convert_spectrum_to_epl(spectrum)*1e6)
                        break
                   
        
        
        #e = datetime.datetime.now() 
        #print(e-s)
        #print(spec_epl)
        
        with open(csv_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([now_time] + spec_epl)
    

# run command line interface
if __name__ == "__main__":
    main()
    

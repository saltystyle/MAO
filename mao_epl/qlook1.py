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
__version__ = "0.1.2"


# standard library
import time
from pathlib import Path


# dependencies
import numpy as np
import matplotlib.pyplot as plt
import os
from docopt import docopt
from reader1 import  get_cal_spectrum, spectrum_zero,generate_patterned, get_nth_spectrum_in_range, get_phase, get_amp,  convert_spectrum_to_epl, get_n_from_current_time, get_freq

import re
from typing import Callable, Pattern
import csv 
import datetime
import sys

def main() -> None:
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

    freq = get_freq()
    freq_selected = freq[(freq >= 19.5) & (freq <= 22.0)]
    
    csv_path = path.with_suffix(".csv")
    csv_file = f'{folder}/{csv_path.name}'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)  
        # ヘッダーを書き込む
        writer.writerow(["time", "c", "t", "r", "b", "l"])
    
    
    #get_cal_spectrumに入れる    
    #キャリブレーション
    spec_cal = [np.zeros(312, dtype=np.complex128) for _ in range(5)]  
    
    t = time.perf_counter() #calスタート時間
    n = 100
    count = [np.zeros(1,dtype=int) for _ in range(5)] 
    a = -1
    while cal >= time.perf_counter() - t :
        #n = get_n_from_current_time(path, delay)#（データの時刻-開始時刻）÷0.01の関数に書きかえ
        n = n+1
        target = pattern[n % pattern_len]
        if n != a and target in feed:   
            f = feed.index(target)
        else:
            time.sleep(0.005)
            continue        
        a = n   
        
        #s = time.perf_counter()  
        spec_cal[f] += get_nth_spectrum_in_range(path, n, freq, integ, delay, chbin)
        #e = time.perf_counter()
        #print("加算:",e-s)
        count[f] += 1
        print("count:", count)
    
    #s = time.perf_counter() 
    spec_cal = [spec_cal[i] / count[i] for i in range(5)]
    #e = time.perf_counter()
    #print("除算:",e-s)
    

    
    t = time.perf_counter()#最終キャリブレーション更新時刻
    count = [np.zeros(1,dtype=int) for _ in range(5)]
    spec_cal_befor = [np.zeros(312, dtype=np.complex128) for _ in range(5)]
    
    while True:
        s = time.perf_counter()
        spec_epl = []      
       
        #n = get_n_from_current_time(path, delay)        
        n=n+1    
        now = datetime.datetime.now()  
        now_time = now.strftime('%Y%m%d %H:%M:%S.%f')[:-3] #jst
        for i in range(5):
            if m[i] == -1: #pattern内に文字が一致しなければ空で返す
                spec_epl.append(0)
            else:
                for j in range(n, -1, -1):
                    if pattern[j % pattern_len] == feed[i]:                                        
                        spectrum = get_nth_spectrum_in_range(path, j, freq, integ, delay, chbin)  
                        spec_cal_befor[i] += spectrum
                        count[i] += 1
                        print("count:", count)
                        if time.perf_counter()-t >= cal: #cal秒経過したら
                           spec_cal = [spec_cal[i] / count[i] for i in range(5)]
                           t = time.perf_counter()
                           count = [np.zeros(1,dtype=int) for _ in range(5)]
                        spectrum /= spec_cal[i]                    
                        spec_epl.append(float(convert_spectrum_to_epl(spectrum, freq_selected)*1e6)) #um
                        break


        with open(csv_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([now_time] + spec_epl)
        e = time.perf_counter()
        print(e-s)    
    

# run command line interface
if __name__ == "__main__":
    main()

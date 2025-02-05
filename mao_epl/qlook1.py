#!/usr/bin/env python
__all__ = ["main"]

"""Quick look for VDIF

Usage: vdif-qlook [-f <PATH>] [--pattern <pattern>] [--integ <T>] [--delay <T>] [--interval <T>] [--chbin <N>] [--cal <T>] [--sample <N>]

-f <PATH>       Input VDIF file.
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
__version__ = "0.1.0"


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
from typing import Callable, Pattern
import csv 
import datetime

def main() -> None:
    
    args = docopt(__doc__, version=__version__) #コマンドライン
    path = Path(args["-f"]).resolve()
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

    VDIF_PATTERN: Pattern = re.compile(r"\w+_(\d+)_\d.vdif")
    match = VDIF_PATTERN.search(path.name)
    csv_file = f'../epl_csv/{match.groups()[0]}.csv'   
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)   
        # ヘッダーを書き込む
        writer.writerow(["time", "c", "t", "r", "b", "l"])
        
    while True:
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
                   
        
        
        #print(f"{match.groups()[0]}.vdif") #YYYYmmddHHMMSS.vdif
        print(now_time)
        print(spec_epl)
        time.sleep(0.5) 
        
        with open(csv_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([now_time] + spec_epl)
    

# run command line interface
if __name__ == "__main__":
    main()
    
    





# standard library
import re 
import time
from datetime import datetime, timedelta
from pathlib import Path
from struct import Struct
from typing import Callable, Pattern
from scipy.optimize import curve_fit
#import os
import re

# dependent packages
import numpy as np 
from docopt import docopt

# constants
LITTLE_ENDIAN: str = "<" # 変数”LITTLE_ENDIAN”が文字列型、＜を代入して制御
UINT: str = "I"
SHORT: str = "h"
N_ROWS_VDIF_HEAD: int = 8
N_ROWS_CORR_HEAD: int = 64
N_ROWS_CORR_DATA: int = 512 #1スキャンあたりの相関データの行数 スペクトルのチャンネル数？？
N_UNITS_PER_SCAN: int = 64 #1スキャンあたりのユニット数
N_BYTES_PER_UNIT: int = 1312 #
N_BYTES_PER_SCAN: int = 1312 * 64 #1スキャンあたりのバイト数
TIME_PER_SCAN: float = 1e-2  # seconds #1スキャンあたりの時間　10ms
TIME_FORMAT: str = "%Y%j%H%M%S"
VDIF_PATTERN: Pattern = re.compile(r"\w+_(\d+)_\d.vdif")
LOWER_FREQ_MHZ = 16384 #周波数の下限値(MHｚ)
N_CHANS_FOR_FORMAT = 8192
C = 299792458 # m/s
PI = np.pi



# main features
def get_nth_spectrum(
    path: Path, 
    n: int, 
    integ: float = 1e-2, 
    delay: float = 0.0,
    chbin: int = 8,
) -> np.ndarray:
    n_integ = int(integ / TIME_PER_SCAN) #積分スキャン数
    n_units = N_UNITS_PER_SCAN * n_integ #積分に必要なユニット数
    n_chans = N_ROWS_CORR_DATA // 2 #チャンネル数

    byte_start = N_BYTES_PER_SCAN * n #読み込みたいデータ

    if byte_start < 0:
        raise ValueError("Not enough data in the file to integrate")
    
    spectra = np.empty([n_units, n_chans], dtype=complex)#空のスペクトラ配列を作成    

    with open(path, "rb") as f:
        f.seek(byte_start, 0)
        for i in range(n_units):
            read_vdif_head(f)
            read_corr_head(f)
            corr_data = read_corr_data(f)
            spectra[i] = parse_corr_data(corr_data)

    spectra = spectra.reshape([n_integ, N_UNITS_PER_SCAN * n_chans])
    spectrum = integrate_spectra(spectra, chbin) #integrate_spectraにspectra, chbinを代入
    return spectrum

# 周波数範囲を指定
def get_nth_spectrum_in_range(path: Path, n: int, integ: float = 1e-2, delay: float = 0.0, chbin: int = 8, n_chans: int = 1024) -> np.ndarray:
    spec = get_nth_spectrum(path, n, integ, delay, chbin)
    freq = get_freq(n_chans = len(spec))
    filtered_spec = spec[(freq >= 19.5) & (freq <= 22.0)] #ブール配列  
    return filtered_spec

# キャリブレーション用のスペクトラム、最初のデータを使う
def get_cal_spectrum(
    path: Path, 
    n: int, 
    cal: float = 1e-2, 
    delay: float = 0.0,
    chbin: int = 8) -> np.ndarray:
    while get_elapsed_time_from_start(path, delay) < (n+1)*TIME_PER_SCAN: #経過時間がキャリブレーション時間を経過するまで0.01秒ごとに待機
        time.sleep(0.01)
    return get_nth_spectrum_in_range(path, n, cal, delay, chbin)     

 

#spectraの配列が全て0 
def spectrum_zero(integ: float = 1e-2) -> np.ndarray:
    n_integ = int(integ / TIME_PER_SCAN) #積分スキャン数
    n_units = N_UNITS_PER_SCAN * n_integ #積分に必要なユニット数
    n_chans = N_ROWS_CORR_DATA // 2 #チャンネル数
    spec = np.zeros([n_units, n_chans], dtype=complex)
    freq = get_freq(n_chans = len(spec))
    filtered_spec = spec[(freq >= 19.5) & (freq <= 22.0)] #ブール配列 
    return filtered_spec



#EPL
def convert_spectrum_to_epl(spec: np.ndarray) -> float:
    fit = curve_fit(line_through_origin, get_freq(n_chans = len(spec)), get_phase(spec)) 
    slope = fit[0] 
    slope = slope[0]
    epl = (C * slope * 1e-9) / (2 * PI)
    return epl

#周波数
def get_freq(bin_width: int = 8, n_chans: int = 1024) -> np.ndarray:
    freq = 1e-3 * (LOWER_FREQ_MHZ + np.arange(n_chans * bin_width))
    freq = freq.reshape((n_chans, bin_width)).mean(-1)
    return freq

#パターン生成
def generate_patterned(pattern: str, times: int = 5, offset: int = 0):
    result = []  
    for char in pattern:
        result.extend([char] * (times - 1))
        result.append("x")
    
    result = np.roll(result, offset)
    return ''.join(result)

#現在時刻から、データがｎ番目にあたるか
def get_n_from_current_time(path: Path, delay: float = 0) -> int:
    n = int(get_elapsed_time_from_start(path, delay) / TIME_PER_SCAN) -1 
    return n


    
    


#振幅
def get_amp(da: np.ndarray) -> np.ndarray:   
    """複素数DataArrayの絶対値Amplitudeを返す関数"""
    amp = np.abs(da)
    return amp


def get_phase(da: np.ndarray) -> np.ndarray:
    """複素数DataArrayの偏角（ラジアン単位）を返す関数"""
    phase = np.arctan2(da.imag, da.real)
    return phase


def line_through_origin(freq: np.ndarray, slope: float) -> np.ndarray :
    """原点を通る直線モデル"""
    return slope * freq 









def integrate_spectra(spectra: np.ndarray, chbin: int = 8) -> np.ndarray:
    spectrum = spectra.mean(0) #全てのスペクトルを平均化し、１つのスペクトルにまとめる バンドパスの較正源
    return spectrum.reshape([len(spectrum) // chbin, chbin]).mean(1) #chbinごとにデータがグループ化され再形成、それぞれの平均値
    


# 経過時間 
def get_elapsed_time_from_start(path: Path , delay: float = 0.0) -> float:
    match = VDIF_PATTERN.search(path.name) #VDIFファイル名から開始時間を抽出する

    if match is None: #ファイル名に時間が書かれて無かったらエラー表示
        raise ValueError("Cannot parse start time from file name.")

    t_start = datetime.strptime(match.groups()[0], TIME_FORMAT)
    t_now = datetime.utcnow() - timedelta(seconds=delay)

    return (t_now - t_start).total_seconds() #開始時間と現在の時間差を計算し、その差を秒単位で返す






# struct readers
# データの読み取り
def make_binary_reader(n_rows: int, dtype: str) -> Callable: #読み取るデータの行数、データの型を指定(I：符号なし整数、H：短整数)
    struct = Struct(LITTLE_ENDIAN + dtype * n_rows) #??

    def reader(f):
        return struct.unpack(f.read(struct.size)) #Pythonのデータ型に変換
    return reader


read_vdif_head: Callable = make_binary_reader(N_ROWS_VDIF_HEAD, UINT)
read_corr_head: Callable = make_binary_reader(N_ROWS_CORR_HEAD, UINT)
read_corr_data: Callable = make_binary_reader(N_ROWS_CORR_DATA, SHORT)


# struct parsers
def parse_vdif_head(vdif_head: list):
    # not implemented yet
    pass


def parse_corr_head(corr_head: list):
    # not implemented yet
    pass

#相関データを解析する
def parse_corr_data(corr_data: list) -> np.ndarray: #corr_data: list:複素数データを表すリスト
    real = np.array(corr_data[0::2]) #偶数の要素を実部
    imag = np.array(corr_data[1::2]) #奇数の要素を虚部
    return real + imag * 1j

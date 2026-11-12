import OpenCV_initialization as end
import numpy as np 
import matplotlib.pyplot as plt 
import time
import opencv
import bb84

#dont forget to deleet the calls at the end of the bb84 file 
#delete print line in bb84 to avoid clutter when running

runtime = 120 
interval = 1 

#from bb84 
n = 1000
f = 0.25
Percent_revealed = 0.25

runtime = []
QBER_list = []
key_length_list = []
useful_keys = []
r_list = []
w_list = []

start = time.time()

for second in range(runtime):
    loop_start = time.time()

    dx, dy, move_vector, radius = opencv.main()
    key, errors, E_tap, QBER = bb84.bb84(n, f, Percent_revealed, move_vector, radius)

    if len(key) >= 8: 
        useful = True
    else: 
        useful = False

    runtime.append(second)
    QBER_list.append(QBER)
    key_length_list.append(len(key))
    useful_keys.append(useful)
    r_list.append(move_vector)
    w_list.append(radius)

    time_used = time.time() - start 
    if time_used < interval: 
        time.sleep(interval - time_used)

    file= open("results.csv", "w")
    file.write("second,r,w,QBER,key_length,useful\n")
    for i in range(len(second)):
        file.write(str(second[i]) + "," + str(r_list[i]) + "," + str(w_list[i]) + "," +
               str(QBER_list[i]) + "," + str(key_length_list[i]) + "," + str(useful_list[i]) + "\n")
    file.close()

end.close_program()


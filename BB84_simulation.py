import numpy as np
rng = np.random.default_rng()

#Alice's initial bits (from rng)
#lets say alice wants to start woth 1000 photons
def Alice_bits(n): 
    A_bits = []
    for i in range (n):
        A_bits.append(int(rng.integers(0,2))) # this gives us a random number between 0 and 1 int. 
    return A_bits
#i also want to multiply the A_bits and shrink the list depending on the reruned error feedback - come back and see where this needs to be added in)

#next alice would pick between two random bases (45* and -45*)
def A_random_Bases(n): 
    A_bases = []
    for i in range (n):
        if (int(rng.integers(0,2))) ==0: 
            A_bases.append("Z")
        else: 
            A_bases.append("X")
    return A_bases

#bob would also pick a random base
def B_random_Bases(n): 
    B_bases = []
    for i in range (n):
        if (int(rng.integers(0,2))) ==0: 
            B_bases.append("Z")
        else: 
            B_bases.append("X")
    return B_bases

#this compares the bases of alice and bob, and creates a list of bobs bits (if bases are same bob has same bit as from alice's list, if dfifferent, its randomly picked)
#add in a eve in a one of E chance (E meaning you can change the probablity of E being present)
def Bobs_bits(A_bits, A_bases, B_bases, E):
    B_bits=[]
    E_tap = 0

    for i in range (len(A_bases)): 
        if A_bases[i] == B_bases[i]:
            bit = A_bits[i]
        else: 
            bit = (int(rng.integers(0,2)))

        #one in E chance of tapping this specific bit & flips it ( so she can tap multuple times in one key)
        if int(rng.integers(0,E)) == 0 : 
            bit = 1- bit
            E_tap = E_tap +1 

        B_bits.append(bit)

    return B_bits, E_tap


#then the compare the bases on the open channel and delete thet ones that didn't match
def sift(A_bits, B_bits, A_bases, B_bases): 
    A_key = []
    B_key = []

    for i in range(len(A_bits)):
        if A_bases[i] == B_bases[i]: 
            A_key.append(A_bits[i])
            B_key.append(B_bits[i])
    return A_key, B_key

#the reveal of __ % of keys (in the form of fraction)
def E_check(A_key, B_key, Percent_revealed): 
    tested_vals = int(len(A_key)*Percent_revealed)
    errors = 0 
    for i in range (tested_vals): 
        if A_key[i] != B_key[i]: 
            errors = errors + 1

    if tested_vals> 0: 
        QBER = errors/ tested_vals
    else: 
        QBER = 1.0 #because nothing is tested and thiis 100% untrusted

    return tested_vals, errors, QBER

#if there are no errors, scrap the parts and cont. else delete the whole key
def final_key(A_key, tested_vals, QBER, threshold = 0.11): 
    if QBER < threshold:
        key = []
        for i in range (tested_vals, len(A_key)):
            key.append(A_key[i])
        return key
    else: 
        return []

#now set itup so it can run in a loop
#n = number of intial bits
#E = 1/ E chance of eve being present
def bb84(n, E=5, Percent_revealed =0.25): 
    A_bits = Alice_bits(n)
    A_bases = A_random_Bases(n)
    B_bases = B_random_Bases(n)
    B_bits, E_tap = Bobs_bits(A_bits, A_bases, B_bases, E)
    A_key, B_key = sift(A_bits, B_bits, A_bases, B_bases)
    tested_vals, errors, QBER = E_check(A_key, B_key, Percent_revealed)
    key = final_key(A_key, tested_vals, QBER)
   
    print("|QBER",round(QBER *100,2), "% | key length:", len(key))
    return key, errors, E_tap, QBER



bb84(1000, E=100)


import numpy as np

def generator(max, min, size):
    #this is intializing the random number generator
    rng = np.random.default_rng()

    #Generate an array of multiple random numbers
    random_array = rng.integers(low = min, high = max, size = size)

    #Puts all the random numbers together
    final_num = "0"
    for i in random_array:
        final_num = final_num + str(i)

    #Returns the final number as an int
    return int(final_num)
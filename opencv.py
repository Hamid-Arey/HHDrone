import cv2
import numpy as np
import OpenCV_initialization as init

def main():

    #Capture frame
    frame = init.picam2.capture_array()

    #Convert to grayscale (Makes it simpler since it does not have to process as many color brightnesses)
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    #Reduce image noise (Blurs the image slightly to get rid of outcast pixels)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Threshold bright IR sources (Examines every pixel in the image and compares its brightness to the brightness threshold)
    #If pixel is greater than threshold then it becomes white other wise black  
    _, threshold = cv2.threshold(
        blurred,
        init.IR_THRESHOLD,
        255,   	            #Max pixel value white
        cv2.THRESH_BINARY 	#Applies the threshold color switch
    )

    # Remove small noise (Creates a 3x3 matrix filed with 1’s which will be used to get rid of small noise)
    Kernel = np.ones((3, 3), np.uint8)

    threshold = cv2.morphologyEx(	#Changes shapes of regions in a binary image
        threshold,
        cv2.MORPH_OPEN,		        #Shrinks white regions (removing small white dots) and expands remaining white
        Kernel		                #The matrix used to check the surrounding pixels to check for this noise
    )

    # Find bright objects (Finds the outline of the bright objects)
    #Contour is the outline of a connected group of white pixels in your binary image 
    contours, _ = cv2.findContours(
        threshold,		            #The image
        cv2.RETR_EXTERNAL,		    #Find only outermost contours (Not contours inside of contours)
        cv2.CHAIN_APPROX_SIMPLE		#Simplifies the contour stores only important boundary points
    )

    #Keeps track of if the light has IR source has been detected
    detected = False

    #Initialize variables to find biggest contour and largest area
    best_contour = None
    largest_area = 0

    # Find largest bright object
    #Find contours returns a collection of contours this is how we got them
    for contour in contours:

    #Calculates area enclosed in contour
        area = cv2.contourArea(contour)


    #Just finding the biggest contour (Isn't this flawed since there could be a bigger contour and it not be the correct source)
        if area > largest_area and area > 2:
            largest_area = area
            best_contour = contour

    # -----------------------------
    # CALCULATE LED POSITION
    # -----------------------------

    #This section calculates the coordinates of the largest bright region
    if best_contour is not None:		#Make sure you actually have one
        M = cv2.moments(best_contour)	#Gets moments (Essentially the shape and position of a region (Uses to get regions center)

        #Makes sure the area is not zero (Since is will be dividing by zero)
        if M["m00"] != 0:

            #Calculates the center of the brightest region
            x = int(M["m10"] / M["m00"])
            y = int(M["m01"] / M["m00"])

            #determines detected as true
            detected = True

            ##Getting the radius from center of bright light to its closest radius##

            ## ---------------------------------------------##

           #Get all points along the blob's outer boundary
            contour_points = best_contour.reshape(-1, 2)

            #Calculate distance from each boundary point to blob centre
            distances = np.sqrt(
                (contour_points[:, 0] - x)**2 +
                (contour_points[:, 1] - y)**2
            )

            #Find the closest boundary point to the blob centre
            closest_index = np.argmin(distances)

            edge_x, edge_y = contour_points[closest_index]

            #Calculate vector from blob centre to its boundary
            dxR = int(edge_x) - x
            dyR = int(edge_y) - y

            #Calculate vector length
            distance_radius = np.sqrt(dxR**2 + dyR**2)

    # -----------------------------
    # CHECK BLINKING
    # -----------------------------

    #Adds value to the deque if a brightest region was detected (Store 0 or 1)
    init.brightness_history.append(1 if detected else 0)

    #This detects how many times the brightness changes between consecutive frames (Sum adds up all the results up (1,0))
    #Essentially counts as the amount of transitions
    transitions = sum(
        init.brightness_history[i] != init.brightness_history[i - 1]
        for i in range(1, len(init.brightness_history))
    )

    #Determines if the object is blinking or not
    #4 transitions is 2 complete blinks so 2 blinks per 90 frames
    blinking = (len(init.brightness_history) == init.HISTORY_SIZE and transitions >= 4)	

    #We set last position to this position when it is BOTH blinking and IR light
    if(blinking == True and detected == True):
        init.last_position = (x, y)
        init.last_radius = distance_radius

    #Makes sure the deque is completely full (We want all 30 comparisons)
	#There must be at least 4 changes between detected and not detected

    #If we have not detcted blinking of the IR in 90 frames, the last point we saw it is irrelevant since we are now off course
    if (sum(init.brightness_history) == 0 and len(init.brightness_history) == init.HISTORY_SIZE):
        init.last_position = None
        init.last_radius = None

    # -----------------------------
    # DISPLAY TRACKING
    # -----------------------------

    #Creating a copy of the current frame because when we draw we don't want to change the original image
    display = frame.copy()

    #Draws a circle at the camera center
    #Later, we can compare the detected IR LED's position (Last position) against this centre to see where the LED is relative to the camera's centre
    cv2.circle(
        display,
        (init.center_x, init.center_y),
        5,
        (255, 0, 0),
        -1
    )

    #This code draws a green circle around the last detected position of the object in your camera feed
    #Makes sure we have a last position (Something was found)
    #Possible we are using previous last_position because we did not find the light this time
    if init.last_position is not None:

    #Extracts coordinates from the positon
        x, y = init.last_position

    # Draw circle detected position
        cv2.circle(
            display,
            (x, y),
            12,
            (0, 255, 0),
            2
        )

    # This code draws a blue line from the centre of the camera frame to the last detected position of the tracked object. 
        cv2.line(
            display,
            (init.center_x, init.center_y),
            (x, y),
            (255, 0, 0),
            2
        )

    #Calculates how far the detected object is from the center of the camera frame
        dx = x - init.center_x
        dy = y - init.center_y
        distance = np.sqrt(dx**2 + dy**2)


        #Prints tracking info onto the console
        print(
            f"X: {x:4d} | Y: {y:4d} | "
            f"DX: {dx:4d} | DY: {dy:4d} | "
            f"Distance: {distance:6.1f} px | "
            f"Blinking: {blinking}"
        )

        #Returns the distance of the vector
        return (dx,dy,distance,init.last_radius)

    else:
        #If no blinking or we have no last position we are going to let them know we cant find and IR source
        print("Nothing Detected")
        return (None,None,None,None)


if __name__ == "__main__":
    main()
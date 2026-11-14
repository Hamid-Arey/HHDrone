import logging

import cv2
import numpy as np
import OpenCV_initialization as init

def main(show=False):

    #Capture frame
    frame, now = init.capture_timed_frame()

    #Convert to grayscale (Makes it simpler since it does not have to process as many color brightnesses)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    #Reduce image noise (Blurs the image slightly to get rid of outcast pixels)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Threshold bright IR sources (Examines every pixel in the image and compares its brightness to the brightness threshold)
    #If pixel is greater than threshold then it becomes white other wise black  
    _, threshold = cv2.threshold(
        blurred,
        init.IR_THRESHOLD,
        255,   	            #Max pixel value white
        cv2.THRESH_BINARY 	#Applies the threshold color switch
    )

    # Reject tiny contours below instead of eroding a small/moving LED away.

    # Find bright objects (Finds the outline of the bright objects)
    #Contour is the outline of a connected group of white pixels in your binary image 
    contours, _ = cv2.findContours(
        threshold,		            #The image
        cv2.RETR_EXTERNAL,		    #Find only outermost contours (Not contours inside of contours)
        cv2.CHAIN_APPROX_SIMPLE		#Simplifies the contour stores only important boundary points
    )

    detections = []
    for contour in contours:
        if cv2.contourArea(contour) <= 2:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        x = int(moments["m10"] / moments["m00"])
        y = int(moments["m01"] / moments["m00"])
        points = contour.reshape(-1, 2)
        radius = float(np.min(np.hypot(points[:, 0] - x, points[:, 1] - y)))
        detections.append((x, y, radius))

    target = init.blink_tracker.update(detections, now)
    init.update_tracking_exposure(target is not None, init.blink_tracker.is_locked, now)
    if target is not None:
        x, y, radius = target
        init.last_position = (x, y)
        init.last_radius = radius
    else:
        init.last_position = None
        init.last_radius = None

    # Compute only from the fresh target. Predictions are for association only.
    result = (None, None, None, None)
    if target is not None:
        x, y, radius = target
        dx, dy = x - init.center_x, y - init.center_y
        result = (dx, dy, float(np.hypot(dx, dy)), radius)
        logging.debug("Target x=%d y=%d dx=%d dy=%d", x, y, dx, dy)
    if not show:
        return result

    display = frame.copy()
    cv2.circle(display, (init.center_x, init.center_y), 5, (255, 0, 0), -1)
    position = init.last_position
    if position is None and init.blink_tracker.is_locked:
        position = init.blink_tracker.locked['point'][:2]
    if position is not None:
        x, y = position
        cv2.circle(display, (x, y), 12, (0, 255, 0), 2)
        cv2.line(display, (init.center_x, init.center_y), (x, y), (0, 255, 255), 2)
    state = "LOCKED" if init.blink_tracker.is_locked else "SEARCHING"
    if init.tracking_hold_active and target is None:
        state = "HOLDING - waiting for LED (5 s)"
    cv2.putText(display, state, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, .6,
                (0, 255, 255), 2)
    cv2.imshow("IR tracking", display)
    return result


if __name__ == "__main__":
    try:
        while True:
            main(show=True)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        init.close_program()
        cv2.destroyAllWindows()

import cv2
import numpy as np
import time
import mysql.connector

# Capture the video stream
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Could not open video stream.")
    exit()

# List to hold bounding boxes
bounding_boxes = []
start_point = None
end_point = None
drawing = False

# Connect to the database and create table
try:
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='turtle'
    )
except mysql.connector.Error as err:
    print(f"Error connecting to MySQL: {err}")
    exit()
else:
    print("MySQL connection established successfully.")

try:
    
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS colour_changes
                 (id INTEGER PRIMARY KEY AUTO_INCREMENT,
                  colour_change VARCHAR(20),
                  time_changed DATETIME,
                  bounding_box_id INTEGER NOT NULL)''')
    conn.commit()
    
    # Function to detect colour changes
    def detect_colour_change(frame, box):
        
        # Coordinates of the bounding box
        start_point, end_point = box['start_point'], box['end_point']
        x1, y1 = start_point
        x2, y2 = end_point
        
        # Flag values for red_logged and yellow_logged
        red_logged = box['red_logged']
        yellow_logged = box['yellow_logged']
        green_logged = box['green_logged']

        # Portion of the frame within the bounding box, region of interest
        roi = frame[y1:y2, x1:x2]

        # Convert the ROI to the HSV colour space
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # colour ranges
        red_lower = np.array([0, 100, 100])
        red_upper = np.array([10, 255, 255])
        yellow_lower = np.array([25, 100, 100])
        yellow_upper = np.array([35, 255, 255])
        green_lower = np.array([50, 100, 100])
        green_upper = np.array([70, 255, 255])
    
        # Threshold to get only the colours in the range
        red_mask = cv2.inRange(hsv, red_lower, red_upper)
        yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)
        green_mask = cv2.inRange(hsv, green_lower, green_upper)

        # Contours in the image
        contours, hierarchy = cv2.findContours(red_mask + yellow_mask + green_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # Loop through each contour
        for contour in contours:
            # Get the bounding rectangle for the contour
            x, y, w, h = cv2.boundingRect(contour)
            
            # Check if contour is a colour change to red
            if (w/h > 2) and (w > 10) and (h > 10):
                roi = hsv[y:y+h, x:x+w]
                red_pixels = cv2.countNonZero(cv2.inRange(roi, red_lower, red_upper))
                if red_pixels > 0:
                    return ('red', bounding_boxes.index(box))
            
            
            # Check if the contour is colour change to yellow
            if (w/h > 2) and (w > 10) and (h > 10):
                roi = hsv[y:y+h, x:x+w]
                yellow_pixels = cv2.countNonZero(cv2.inRange(roi, yellow_lower, yellow_upper))
                if yellow_pixels > 0:
                    return ('yellow', bounding_boxes.index(box))

            # Check if the contour is colour change to green
            elif (h/w > 2) and (w > 10) and (h > 10):
                roi = hsv[y:y+h, x:x+w]
                green_pixels = cv2.countNonZero(cv2.inRange(roi, green_lower, green_upper))
                if green_pixels > 0:
                    return ('green', bounding_boxes.index(box))

        # Return if no colour changes were detected
        return None


    # Function to draw bounding boxes on the video stream
    def draw_rectangle(event, x, y, flags, param):
        global bounding_boxes, drawing, start_point, end_point

        # If the user clicks the left mouse button, start drawing a rectangle
        if event == cv2.EVENT_LBUTTONDOWN:
            start_point = (x, y)
            drawing = True

        # If the user moves the mouse while holding down the left mouse button
        elif event == cv2.EVENT_MOUSEMOVE:
            if drawing == True:
                end_point = (x, y)
            
        # If the user releases the left mouse button, stop drawing and thus create new bounding box
        elif event == cv2.EVENT_LBUTTONUP:
            end_point = (x, y)
            bounding_boxes.append({'start_point': start_point, 'end_point': end_point, 'red_logged': False, 'yellow_logged': False, 'green_logged': False})
            drawing = False
            
        
        
    # Set up the mouse callback function to draw bounding boxes
    cv2.namedWindow('VideoStream')
    cv2.setMouseCallback('VideoStream', draw_rectangle)

    
    # Main loop involving video stream and detecting colour changes
    while True:
        
        #Capture a frame from the video stream
        ret, frame = cap.read()
    
        if ret:
            
        # Draw the bounding boxes on the frame
            for box in bounding_boxes:
                cv2.rectangle(frame, box['start_point'], box['end_point'], (0, 255, 0), 2)

                # Detect colour changes in the frame
                colour_change = detect_colour_change(frame, box)

                
                # Checks colour change
                if colour_change:
                    current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                    print(colour_change)
                    print(current_time)

                    # Check if the colour change is to red
                    if colour_change[0] == 'red' and (not box['yellow_logged']) and (not box['red_logged']) and (not box['green_logged']):
                        c.execute("INSERT INTO colour_changes (colour_change, time_changed, bounding_box_id) VALUES (%s, %s, %s)", (colour_change[0], current_time, colour_change[1]))
                        conn.commit()

                        # Marks when red has been logged inro database, to ensure only one input of this colour change
                        box['red_logged'] = True
                    
                    # Check if the colour change is true from red to yellow
                    if colour_change[0] == 'yellow' and (not box['yellow_logged']) and (box['red_logged']) and (not box['green_logged']):
                        c.execute("INSERT INTO colour_changes (colour_change, time_changed, bounding_box_id) VALUES (%s, %s, %s)", (colour_change[0], current_time, colour_change[1]))
                        conn.commit()

                        # Marks when yellow has been logged inro database, to ensure only one input of this colour change
                        box['yellow_logged'] = True

                    # Check if the colour change is red, yellow and green has been logged
                    if colour_change[0] == 'green' and box['yellow_logged'] and (box['red_logged']) and (not box['green_logged']):
                        c.execute("INSERT INTO colour_changes (colour_change, time_changed, bounding_box_id) VALUES (%s, %s, %s)", (colour_change[0], current_time, colour_change[1]))
                        conn.commit()
                        
                        # Marks when green has been logged inro database, to ensure only one input of this colour change
                        box['green_logged'] = True
                

        cv2.imshow('VideoStream', frame)

        # Exit the loop if the user presses the 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

finally:
    if 'c' in locals():
        c.close()
    if 'conn' in locals() and conn.is_connected():
        conn.close()
        print("MySQL connection is closed.")
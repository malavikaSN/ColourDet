import cv2
import numpy as np
import time
import mysql.connector

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Could not open video stream.")
    exit()

# Global Variables
boundingBoxes = []
start_point = None
end_point = None
drawing = False
prev_point = None
selectedBox = None

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
    c.execute('''DROP TABLE IF EXISTS colourChanges''')
    c.execute('''CREATE TABLE IF NOT EXISTS colourChanges
                 (id INTEGER PRIMARY KEY AUTO_INCREMENT,
                  colourChange VARCHAR(20),
                  timeChanged DATETIME,
                  boundingBoxID INTEGER NOT NULL)''')
    conn.commit()
    
    # Function to detect colour changes
    def detectColourChange(frame, box):
        
        start_point, end_point = box['start_point'], box['end_point']
        x1, y1 = start_point
        x2, y2 = end_point
        
        # Ensure the bounding box is within the image dimensions
        frame_h, frame_w, _ = frame.shape
        if x1 < 0 or x1 > frame_w or x2 < 0 or x2 > frame_w or y1 < 0 or y1 > frame_h or y2 < 0 or y2 > frame_h:
            return None
        
        # Flag values for red_logged, yellow_logged and green_logged
        red_logged = box['red_logged']
        yellow_logged = box['yellow_logged']
        green_logged = box['green_logged']

        
        roi = frame[y1:y2, x1:x2]
        
        # Check if roi is empty or None (for moving funciotionality of bounding boxes)
        if roi is None or roi.size == 0:
            return None

        
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Colour ranges
        red_lower = np.array([0, 100, 100])
        red_upper = np.array([10, 255, 255])
        yellow_lower = np.array([25, 100, 100])
        yellow_upper = np.array([35, 255, 255])
        green_lower = np.array([50, 100, 100])
        green_upper = np.array([70, 255, 255])
    
        # Threshold values to get colours in this range
        red_mask = cv2.inRange(hsv, red_lower, red_upper)
        yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)
        green_mask = cv2.inRange(hsv, green_lower, green_upper)

        
        contours, hierarchy = cv2.findContours(red_mask + yellow_mask + green_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        
        for contour in contours:
            
            x, y, w, h = cv2.boundingRect(contour)
            
            # Check if red is detected
            if (w/h > 2) and (w > 10) and (h > 10):
                roi = hsv[y:y+h, x:x+w]
                red_pixels = cv2.countNonZero(cv2.inRange(roi, red_lower, red_upper))
                if red_pixels > 0:
                    return ('red', boundingBoxes.index(box))
            
            
            # Check if yellow is detected
            if (w/h > 2) and (w > 10) and (h > 10):
                roi = hsv[y:y+h, x:x+w]
                yellow_pixels = cv2.countNonZero(cv2.inRange(roi, yellow_lower, yellow_upper))
                if yellow_pixels > 0:
                    return ('yellow', boundingBoxes.index(box))

            # Check if green is detected
            if (h/w > 2) and (w > 10) and (h > 10):
                roi = hsv[y:y+h, x:x+w]
                green_pixels = cv2.countNonZero(cv2.inRange(roi, green_lower, green_upper))
                if green_pixels > 0:
                    return ('green', boundingBoxes.index(box))

        
        return None

    
    

    # Function to draw bounding boxes
    def drawRectBox(event, x, y, flags, param):
        global boundingBoxes, drawing, start_point, end_point, prev_point, selectedBox
        
        if event == cv2.EVENT_LBUTTONDOWN:
            # Check if any bounding box is clicked
            for box in boundingBoxes:
                if x >= box['start_point'][0] and x <= box['end_point'][0] and y >= box['start_point'][1] and y <= box['end_point'][1]:
                    selectedBox = box
                    prev_point = (x, y)
                    return

            start_point = (x, y)
            drawing = True


        elif event == cv2.EVENT_MOUSEMOVE:
            
            # Move the selected bounding box
            if selectedBox is not None:
                dx = x - prev_point[0]
                dy = y - prev_point[1]
                selectedBox['start_point'] = (selectedBox['start_point'][0] + dx, selectedBox['start_point'][1] + dy)
                selectedBox['end_point'] = (selectedBox['end_point'][0] + dx, selectedBox['end_point'][1] + dy)
                prev_point = (x, y)

            elif drawing == True:
                end_point = (x, y)
                
                
        elif event == cv2.EVENT_LBUTTONUP:
            if selectedBox is not None:
                # Update database
                c.execute(f"UPDATE colourChanges SET boundingBoxID={boundingBoxes.index(selectedBox)} WHERE boundingBoxID={boundingBoxes.index(selectedBox)}")
                conn.commit()
                selectedBox = None
                
            elif drawing == True:
                end_point = (x, y)
                boundingBoxes.append({'start_point': start_point, 'end_point': end_point, 'red_logged': False, 'yellow_logged': False, 'green_logged': False})
            drawing = False
        
    
    cv2.namedWindow('VideoStream')
    cv2.setMouseCallback('VideoStream', drawRectBox)

    
    # Main loop involving video stream and detecting colour changes
    while True:
        
       
        ret, frame = cap.read()
    
        if ret:
            
        # Draw the bounding boxes
            for box in boundingBoxes:
                cv2.rectangle(frame, box['start_point'], box['end_point'], (0, 255, 0), 2)

                
                colourChange = detectColourChange(frame, box)

                
                # Checks colour change
                if colourChange:
                    current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                    print(colourChange)
                    print(current_time)

                    # Check if the colour change is to red
                    if colourChange[0] == 'red' and (not box['yellow_logged']) and (not box['red_logged']) and (not box['green_logged']):
                        c.execute("INSERT INTO colourChanges (colourChange, timeChanged, boundingBoxID) VALUES (%s, %s, %s)", (colourChange[0], current_time, colourChange[1]))
                        conn.commit()

                        # Marks when red has been logged inro database, to ensure only one input of this colour change
                        box['red_logged'] = True
                    
                    # Check if the colour change is true from red to yellow
                    if colourChange[0] == 'yellow' and (not box['yellow_logged']) and (box['red_logged']) and (not box['green_logged']):
                        c.execute("INSERT INTO colourChanges (colourChange, timeChanged, boundingBoxID) VALUES (%s, %s, %s)", (colourChange[0], current_time, colourChange[1]))
                        conn.commit()

                        # Marks when yellow has been logged inro database, to ensure only one input of this colour change
                        box['yellow_logged'] = True

                    # Check if the colour change is red, yellow and green has been logged
                    if colourChange[0] == 'green' and box['yellow_logged'] and (box['red_logged']) and (not box['green_logged']):
                        c.execute("INSERT INTO colourChanges (colourChange, timeChanged, boundingBoxID) VALUES (%s, %s, %s)", (colourChange[0], current_time, colourChange[1]))
                        conn.commit()
                        
                        # Marks when green has been logged inro database, to ensure only one input of this colour change
                        box['green_logged'] = True
                

        cv2.imshow('VideoStream', frame)

        # Exit
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

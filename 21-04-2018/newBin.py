from picamera import PiCamera
from picamera.array import PiRGBArray
import cv2,os,socket,sys,time,Adafruit_PCA9685
import numpy as np
from twilio.rest import Client


def sendSMS(msg):
    account_sid = "AC3b65d4b08b4242625715cb559f5410b0"
    auth_token = "a4f4e1298494f1e9f166df22e48912f2"
    client = Client(account_sid, auth_token)
    client.api.account.messages.create(to="+918147661833",from_="+18043125524",body=msg)
    print("SMS sent !")


def binStatus():

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(16,GPIO.IN) #GPIO 16 bio degradable 
    GPIO.setup(18,GPIO.IN) #GPIO 18 non bio degradable bin
    
    
    bio = GPIO.input(16)
    nonbio= button_state = GPIO.input(18)
    if bio != False : #object is near   
        time.sleep(2)
        if bio!=False :
            msg="Biodegradable bin is full. Please replace."
            sendSMS(msg)
    
    if nonbio != False : #object is near  
        time.sleep(2)
        if nonbio!=False :
            msg="Non-biodegradable bin is full. Please replace."
            sendSMS(msg)

    print("Bin status is updated !")


def flap(direction):
    print("Operating flap..")
    center=185
    left=90
    right=320
    pin=0
    if direction=='l':
        for i in range(center,left,-1):
            pwm.set_pwm(pin,0,i)
            time.sleep(0.01)
        time.sleep(2)
        for i in range(left,center,1):
            pwm.set_pwm(pin,0,i)
            #time.sleep(0.01)
    elif direction=='r':
        center=170
        for i in range(center,right,1):
            pwm.set_pwm(pin,0,i)
            time.sleep(0.01)
        time.sleep(2)
        for i in range(right,center,-1):
            pwm.set_pwm(pin,0,i)
            time.sleep(0.01)


def clientResponse(img):
    #os.system("clear")
    filename="newimg.jpg"
    cv2.imwrite(filename,img)
    #extractForegroundImage(filename)
    s = socket.socket()         
    port = 60000              
    s.connect(("192.168.43.36", port))
    print("Established connection.")
    f=open(filename,"rb")
    data=f.read()
    f.close()
    print("\nSending Length information..")
    length=str(len(data))
    s.send(bytes(length,"utf-8"))
    
    status=s.recv(2)
    print("Length Reception Acknowledgement - "+str(status.decode("utf-8")))
    print("Sending the image to Google Cloud for Tensorflow processing. . .")
    f=open(filename,"rb")
    data=f.read(1)
    # Progress bar to indicate status of sending the image.
    length=int(length)
    count=0
    counter=0
    slab=int(length/10)
    print("\nProgress-")
    while data:
        s.send(data)
        data=f.read(1)
        count+=1
        if count==slab:
            counter+=1
            sys.stdout.write('\r')
            sys.stdout.write('['+"#"*counter+" "*(10-counter)+']'+" "+str(counter*10)+"%")
            sys.stdout.flush()
            count=0
    sys.stdout.write("\n")
    sys.stdout.flush()
    print("Sent sucessfully!")
    f.close()
    
    binFlag=s.recv(1)
    print("Cloud response received.")
    if str(binFlag.decode("utf-8"))=="l":
        print("Object is biodegradable. Rotating bin on the left side.")
    elif str(binFlag.decode("utf-8"))=="r":
        print("Object is non-biodegradable. Rotating bin on the right side.")
    s.close()
    os.system("clear")
    return binFlag.decode("utf-8")




def imageSubtract(img):
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2YUV)
    return hsv

def  imageProcessing():


    camera = PiCamera()
    camera.resolution = (512,512)
    #camera.zoom=(0.0,0.0,0.4,0.5)
    camera.awb_mode="fluorescent"
    camera.iso = 800
    camera.contrast=25
    camera.brightness=64
    camera.sharpness=100
    rawCapture = PiRGBArray(camera, size=(512, 512))

    first_time=0
    frame_buffer=0
    counter=0
    camera.start_preview()
    time.sleep(1)

    for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
        if first_time==0:
            rawCapture.truncate(0)
            if frame_buffer<10:
                print("Frame rejected -",str(frame_buffer))
                frame_buffer+=1
                continue
            os.system("clear")
            refImg=frame.array
            #refImg=refImg[260:512,50:490]
            refThresh=imageSubtract(refImg)
            first_time=1
            frame_buffer=0

        frame_buffer+=1

        image = frame.array
        
        rawCapture.truncate(0)
        newThresh=imageSubtract(image)
        cv2.imshow("Foreground", newThresh)
        key = cv2.waitKey(1)

        diff=cv2.absdiff(refThresh,newThresh)
        #cv2.imshow("subtracted",diff)
        cv2.imshow("Background",refThresh)
        diff=cv2.cvtColor(diff,cv2.COLOR_BGR2GRAY)
        kernel = np.ones((5,5),np.uint8)
        diff = cv2.morphologyEx(diff, cv2.MORPH_OPEN, kernel)
        diff=cv2.erode(diff,kernel,iterations = 2)
        diff=cv2.dilate(diff,kernel,iterations = 4)

        _, thresholded = cv2.threshold(diff, 0 , 255, cv2.THRESH_BINARY +cv2.THRESH_OTSU)
        _, contours, _= cv2.findContours(thresholded,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        #print("Total contours ",len(contours))
        try:
            c=max(contours,key=cv2.contourArea)
            mask = np.zeros(newThresh.shape[:2],np.uint8)
            new_image = cv2.drawContours(mask,[c],0,255,-1,)
            cv2.imshow("new",new_image)
            cv2.imshow("threshold",thresholded)
            if cv2.contourArea(c)>500 and len(contours)<=2:
                if counter==0:
                    print("Possible object detcted ! Going to sleep for 2 seconds")
                    time.sleep(3)
                    counter=1
                    continue
                else:
                    os.system("clear")
                    M=cv2.moments(c)
                    cX = int(M['m10']/M['m00'])
                    cY = int(M['m01']/M['m00'])
                    print("Total contours found=",len(contours))
                    print("Object detected with area = ",cv2.contourArea(c))

                    binDir=clientResponse(image)
                    flap(binDir) # call the flap function
                    first_time=0
                    frame_buffer=0
                    counter=0
                    print("Waste segregated !")
                    continue
            
        except Exception as e:
            print(e)
            pass
        
        if key == ord('q'):
            camera.close()
            cv2.destroyAllWindows()
            break

       

if __name__ == "__main__" :
    try:
        pwm = Adafruit_PCA9685.PCA9685()
        pwm.set_pwm_freq(50)
        imageProcessing()
        print("Started the system !")
                       
    except KeyboardInterrupt:  # When 'Ctrl+C' is pressed, the child program destroy() will be  executed.
        GPIO.cleanup() 

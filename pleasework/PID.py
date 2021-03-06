#!/usr/bin/env python
import csv
import rospy
import math
import numpy
import sys
import time
from mavros_msgs.msg import OpticalFlowRad 
from mavros_msgs.msg import State  
from sensor_msgs.msg import Range  
from sensor_msgs.msg import Imu  
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import Pose 
from geometry_msgs.msg import TwistStamped 
from mavros_msgs.srv import *   





class velControl:
    def __init__(self, attPub):  
        self._attPub = attPub
        self._setVelMsg = TwistStamped()
        self._targetVelX = 0
        self._targetVelY = 0
        self._targetVelZ = 0
        self._AngVelX = 0
        self._AngVelY = 0
        self._AngVelZ = 0

      
    def setVel(self, coordinates, coordinates1):
        self._targetVelX = float(coordinates[0])
        self._targetVelY = float(coordinates[1])
        self._targetVelZ = float(coordinates[2])
        self._AngVelX = float(coordinates1[0])
        self._AngVelY = float(coordinates1[1])
        self._AngVelZ = float(coordinates1[2])
        #rospy.logwarn("Target velocity is \nx: {} \ny: {} \nz: {}".format(self._targetVelX,self._targetVelY, self._targetVelZ))

     
    def publishTargetPose(self, stateManagerInstance):
        self._setVelMsg.header.stamp = rospy.Time.now()    
        self._setVelMsg.header.seq = stateManagerInstance.getLoopCount()
        self._setVelMsg.header.frame_id = 'fcu'
        self._setVelMsg.twist.linear.x = self._targetVelX
        self._setVelMsg.twist.linear.y = self._targetVelY
        self._setVelMsg.twist.linear.z = self._targetVelZ
        self._setVelMsg.twist.angular.x = self._AngVelX
        self._setVelMsg.twist.angular.y = self._AngVelY
        self._setVelMsg.twist.angular.z = self._AngVelZ
        
        self._attPub.publish(self._setVelMsg) 

class stateManager: 
    def __init__(self, rate):
        self._rate = rate
        self._loopCount = 0
        self._isConnected = 0
        self._isArmed = 0
        self._mode = None
     
    def incrementLoop(self):
        self._loopCount = self._loopCount + 1
     	
    def getLoopCount(self):
        return self._loopCount
     
    def stateUpdate(self, msg):
        self._isConnected = msg.connected
        self._isArmed = msg.armed
        self._mode = msg.mode
        rospy.logwarn("Connected is {}, armed is {}, mode is {} ".format(self._isConnected, self._isArmed, self._mode)) 
     
    def armRequest(self):
        rospy.wait_for_service('/mavros/set_mode')
        try:
            modeService = rospy.ServiceProxy('/mavros/set_mode', mavros_msgs.srv.SetMode) 
            modeService(custom_mode='OFFBOARD')
        except rospy.ServiceException as e:
            print("Service mode set faild with exception: %s"%e)
     
    def offboardRequest(self):
        rospy.wait_for_service('/mavros/cmd/arming')
        try:
            arm = rospy.ServiceProxy('/mavros/cmd/arming', mavros_msgs.srv.CommandBool) 
            arm(True)
        except rospy.ServiceException as e:   
           print("Service arm failed with exception :%s"%e)

    def waitForPilotConnection(self):   
        rospy.logwarn("Waiting for pilot connection")
        while not rospy.is_shutdown():  
            if self._isConnected:   
                rospy.logwarn("Pilot is connected")
                return True
            self._rate.sleep
        rospy.logwarn("ROS shutdown")
        return False

 
def distanceCheck(msg):
    global range1 
    #print("d")
    range1 = msg.range 
        



#convert imu reading to body fixed angles
 
def quaternion_to_euler_angle(w, x, y, z):
	ysqr = y * y
	
	t0 = +2.0 * (w * x + y * z)
	t1 = +1.0 - 2.0 * (x * x + ysqr)
	X = math.degrees(math.atan2(t0, t1))
	
	t2 = +2.0 * (w * y - z * x)
	t2 = +1.0 if t2 > +1.0 else t2
	t2 = -1.0 if t2 < -1.0 else t2
	Y = math.degrees(math.asin(t2))
	
	t3 = +2.0 * (w * z + x * y)
	t4 = +1.0 - 2.0 * (ysqr + z * z)
	Z = math.degrees(math.atan2(t3, t4))
	
	return X, Y, Z        
        

#receive time message
 
def timer(msg):
    global timer1
    #print("t")
    timer1 = msg.header.stamp.secs
    
#receive velocity message
 
def velfinder(msg):
    global velx, vely, velz
   # print("v")
    velx = msg.twist.linear.x
    vely = msg.twist.linear.y
    velz = msg.twist.linear.z
 
def callback(msg):
    global x
    global y
    #print("c")
    x = msg.integrated_x
    y = msg.integrated_y

#receive quaternion angles

 
def gyrocheck(msg):
    global x1
    global y1
    global z1
    #print("g")
    x2 = msg.orientation.x
    y2 = msg.orientation.y
    z2 = msg.orientation.z
    w = msg.orientation.w
    x1, y1, z1 = quaternion_to_euler_angle(w, x2, y2, z2)

def PosCheck(msg):
    global xpos
    global ypos
    global zpos
    xpos = msg.pose.position.x
    ypos = msg.pose.position.y
    zpos = msg.pose.position.z

#PID function
 
def PID(y, yd, Ki, Kd, Kp, ui_prev, e_prev, limit):
     # error
     e = yd - y
     # Integrator
     ui = ui_prev + 1.0 / Ki * e
     # Derivative
     ud = 1.0 / Kd * (e - e_prev)	
     #constraint on values, resetting previous values	
     ui = ui/8
     ud = ud/8
     e_prev = e
     ui_prev = ui
     u = Kp * (e + ui + ud)
     #print("U: ", u)
     if u > limit:
         u = limit
     if u < -limit:
         u = -limit
     return u, ui_prev, e_prev

def main():
   
    #import sensor variables
    tol = 0.1
    global range1
    range1 = 0
    global x, y
    x, y = 0, 0
    global x1, y1, z1 
    x1, y1, z1 = 0, 0, 0
    global timer1
    timer1 = 0
    global velx, vely, velz
    velx, vely, velz = 0, 0, 0
    global xpos, ypos, zpos
    xpos, ypos, zpos = 0, 0, 0
    
    yDesiredDistance = 0.0
    xDesiredDistance = 0.0
    zHeight = 0.0
    flightPhase = 0
    finalDistance = 6.0
    yGain = 3 #Alan: the y direction (drift) proportional gain
    xGain = 3
    yDesiredDistance = 0.0 #Alan: The desired y coordinate
    global xDistance
    global yDistance
    xDistance, yDistance = 0.0, 0.0

    rospy.init_node('navigator')   
    rate = rospy.Rate(20) 
    stateManagerInstance = stateManager(rate) 

    #Subscriptions
    rospy.Subscriber("/mavros/state", State, stateManagerInstance.stateUpdate)  
    rospy.Subscriber("/mavros/distance_sensor/hrlv_ez4_pub", Range, distanceCheck)  
    rospy.Subscriber("/mavros/px4flow/raw/optical_flow_rad", OpticalFlowRad, callback)     
    rospy.Subscriber("/mavros/imu/data", Imu, gyrocheck)
    rospy.Subscriber("/mavros/local_position/pose", PoseStamped, PosCheck)
    rospy.Subscriber("/mavros/local_position/odom", Odometry, timer)
    rospy.Subscriber("/mavros/local_position/velocity", TwistStamped, velfinder)

    #Publishers
    velPub = rospy.Publisher("/mavros/setpoint_velocity/cmd_vel", TwistStamped, queue_size=2) 
    controller = velControl(velPub) 
    stateManagerInstance.waitForPilotConnection()  

    #PID hover variables 
    ui_prev = 0.25
    e_prev = 0
    u = 0.25

    #PID stable x variables
    ui_prev1 = 0
    e_prev1 = 0
    u1 = 0
   
    #PID stable y variables
    ui_prev2 = 0
    e_prev2 = 0
    u2 = 0

    #PID stable z variables
    ui_prev3 = 0
    e_prev3 = 0
    u3 = 0

    #timer variable
    time1 = timer1
    timer2 = timer1
    neu_dict = {'dist': [], 'xvel': [], 'zvel': [], 'pitch':[],  'PIDz': [], 'PIDx': [], 'theta': []}
    switch = 0
    switch1 = 0
    xcontrol = 0
    deltax = 0
    deltaz = 0
    z = 0
    x = 0
    while not rospy.is_shutdown():

        
        
        ##while timer1 - time1 < 5:
        #    #print(timer1 - time1)
        #    #controller.setVel([0,0,0.5])
        
        #controller.publishTargetPose(stateManagerInstance)
        #stateManagerInstance.incrementLoop()
        #rate.sleep()   



        ##print debugging values
        #print("loop: " ,stateManagerInstance.getLoopCount(), " distance: ", range1, " u input: ", u, " zvel: ", velz, " angx: ", x1, " angvelx: ", u1, " angy: ", y1, " angvely: ", u2, " angx: ", z1, " angvelx: ", u3) 

        #if stateManagerInstance.getLoopCount() > 100:
            ##hover pid
            #zprev = z
            #z = range1
            #xprev = x
            #x = xpos            
            #deltaz = z - zprev
            #deltax = x - xprev
            #if deltax == 0:
                #deltax = 1
                #deltaz = numpy.inf
            #if range1 < 1.4 or range1 > 1.8:
                #switch = 0
            #elif abs(range1 - 1.5) < tol+0.05 and switch == 0:
                #switch = 1
                #timer2 = timer1
            #elif range1 > 1.3 and range1 < 1.8:
                #switch = 2
            #if switch == 0:
                #controller.setVel([0,yGain*(yDesiredDistance - ypos),u],[0,0,0])
                #u, ui_prev, e_prev = PID(range1, 1.5, 1, 1, 1, ui_prev, e_prev, 0.5) 
            #elif switch == 1 and abs(timer2-timer1) < 2:
                #controller.setVel([0,yGain*(yDesiredDistance - ypos),0],[0,0,0])
            #elif switch == 2 and abs(timer2-timer1) > 2:
                #controller.setVel([xcontrol,yGain*(yDesiredDistance - ypos),u],[0,0,0])
                #u, ui_prev, e_prev = PID(range1, 1.5, 1, 1, 1, ui_prev, e_prev, 0.5)
                ##xcontrol = 0.5 - (0.3/90)*math.degrees(numpy.arctan(abs(deltaz/deltax)))
                #xcontrol = 0.5 - (0.3/0.1)*numpy.clip(abs(range1 - 1.5),0,0.1)


            #"""#stable y pid
            #controller.setAngVel([0,u2,0])
            #u2, ui_prev2, e_prev2 = PID(y1, 0, 1, 1, 1, ui_prev2, e_prev2)"""
        #rest on ground phase
        if flightPhase == 0:
            controller.setVel([0,0,0],[0,0,0])
            controller.publishTargetPose(stateManagerInstance)
            stateManagerInstance.incrementLoop()
            rate.sleep()    #sleep at the set rate
        #takeoff phase
        if flightPhase == 1:
            zHeight = zHeight + 0.02
            controller.setVel([xGain*(xDesiredDistance - xpos),yGain*(yDesiredDistance - ypos),zHeight-range1],[0,0,0])
            controller.publishTargetPose(stateManagerInstance)
            stateManagerInstance.incrementLoop()
            rate.sleep()    #sleep at the set rate
        #hover phase
        if flightPhase == 2:
            controller.setVel([xGain*(xDesiredDistance - xpos),yGain*(yDesiredDistance - ypos),zHeight-range1],[0,0,0])
            controller.publishTargetPose(stateManagerInstance)
            stateManagerInstance.incrementLoop()
            rate.sleep()    #sleep at the set rate
        #forward flight phase
        if flightPhase == 3:
            #xDesiredDistance = xDesiredDistance + 0.02
            #controller.setVel([3*(xDesiredDistance - xpos),yGain*(yDesiredDistance - ypos),2*(zHeight-range1)])
            controller.setVel([xcontrol,yGain*(yDesiredDistance - ypos),u],[0,0,0])
            u, ui_prev, e_prev = PID(range1, 1.5, 1, 1, 1, ui_prev, e_prev, 0.5)
                
            xcontrol = 0.3 - (0.2/0.1)*numpy.clip(abs(range1 - 1.5),0,0.1) #this line is unstable when x0 > 0.4, at least on VM workstation (use player!)
            controller.publishTargetPose(stateManagerInstance)
            stateManagerInstance.incrementLoop()
            rate.sleep()    #sleep at the set rate    
                
        #landing A phase
        if flightPhase == 4:

            zHeight = zHeight*0.95 - 0.005
            controller.setVel([xGain*(xDesiredDistance - xpos),yGain*(yDesiredDistance - ypos),2*(zHeight-range1)],[0,0,0])
            controller.publishTargetPose(stateManagerInstance)
            stateManagerInstance.incrementLoop()
            rate.sleep()    #sleep at the set rate      
        #landing B phase    
        if flightPhase == 5:
            controller.setVel([0,0,-0.2],[0,0,0])
            controller.publishTargetPose(stateManagerInstance)
            stateManagerInstance.incrementLoop()
            rate.sleep()    #sleep at the set rate  
        
        
        #change from state 0 to 1 if count >100
        if stateManagerInstance.getLoopCount() > 100:   #need to send some position data before we can switch to offboard mode otherwise offboard is rejected
            if flightPhase == 0:
                flightPhase = 1
                print(1)
                #zHeight = 1.5
            stateManagerInstance.offboardRequest()  #request control from external computer
            stateManagerInstance.armRequest()   #arming must take place after offboard is requested
        #change from phase 1 to 2 if at z=1.5m
        if zHeight >= 1.5: #stateManagerInstance.getLoopCount() > 100:   #need to send some position data before we can switch to offboard mode otherwise offboard is rejected
            if flightPhase == 1:
                zHeight = 1.5
                flightPhase = 2 
                print(2)
                timer2 = timer1
        #change from phase 2 to 3 after two seconds
        if flightPhase == 2:
            if (timer1 - timer2) > 2:
				flightPhase = 3
				print(3)
        #print(xpos)
        #change from phase 3 to 4 after reaching finalDistance (=6m likely)
        if flightPhase == 3:
            if xpos >= finalDistance:
                flightPhase = 4
                print(4)
                xDesiredDistance = finalDistance
        #change from phase 4 to 5 when z = 0.2m
        if flightPhase == 4:
            if zHeight <= 0.2:
                flightPhase = 5
                print(5)
            

            #stateManagerInstance.offboardRequest()  
            #stateManagerInstance.armRequest()  
    rospy.spin()  

    



if __name__ == '__main__':
    main()




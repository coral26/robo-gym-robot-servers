#!/usr/bin/env python
import rospy
from std_msgs.msg import Bool
from geometry_msgs.msg import Pose, Twist
from gazebo_msgs.msg import ModelState
from scipy import signal, interpolate 
import numpy as np 
import copy

move = False 
class ObjectsController:
    def __init__(self):

        # Objects Model State publisher
        self.set_model_state_pub = rospy.Publisher('gazebo/set_model_state', ModelState, queue_size=1)

        # Objects position update frequency (Hz)
        self.update_rate = 100 

        # move_objects subscriber
        rospy.Subscriber("move_objects", Bool, self.callback_move_objects)
    
    def callback_move_objects(self, data):
        global move
        if data.data == True:
            move = True
        else:
            move = False

    def get_triangle_wave(self, x, y, amplitude, frequency, offset):

        """Generate samples of triangle wave function with amplitude in the z axis direction.

        Args:
            x (float): x coordinate (m).
            y (float): y coordinate (m).
            amplitude (float): amplitude of the triangle wave (m).
            frequency (float): frequency of the triangle wave (Hz).
            offset (float): offset from the ground of the zero of the triangle wave (m).


        Returns:
            np.array: Samples of the x coordinate of the function over time.
            np.array: Samples of the y coordinate of the function over time.
            np.array: Samples of the z coordinate of the function over time.

        """

        # Create array with time samples over 1 full function period
        sampling_rate = copy.deepcopy(self.update_rate)
        self.samples_len = int(sampling_rate / frequency)
        t = np.linspace(0, (1/frequency), self.samples_len)

        x_function = np.full(self.samples_len, x)
        y_function = np.full(self.samples_len, y)
        z_function = offset + amplitude * signal.sawtooth(2 * np.pi * frequency * t, 0.5)

        return x_function, y_function, z_function
    
    def get_3d_spline(self, x_min, x_max, y_min, y_max, z_min, z_max, n_points=10, n_sampling_points=4000):
        
        """Generate samples of the cartesian coordinates of a 3d spline.

        Args:
            x_min (float): min x coordinate of random points used to interpolate spline (m).
            x_max (float): max x coordinate of random points used to interpolate spline (m).
            y_min (float): min y coordinate of random points used to interpolate spline (m).
            y_max (float): max y coordinate of random points used to interpolate spline (m).
            z_min (float): min z coordinate of random points used to interpolate spline (m).
            z_max (float): max z coordinate of random points used to interpolate spline (m).
            n_points (int): number of random points used to interpolate the 3d spline.
            n_sampling_points (int): number of the samples to take over the whole length of the spline.

        Returns:
            np.array: Samples of the x coordinate of the function over time.
            np.array: Samples of the y coordinate of the function over time.
            np.array: Samples of the z coordinate of the function over time.

        """

        # Convert number of points to int
        n_points = int(n_points)
        # Convert number of  sampling points to int
        # By increasing the number of sampling points the speed of the object decreases
        n_sampling_points = int(n_sampling_points)
        # Create array with time samples over 1 full function period

        self.samples_len = n_sampling_points

        x = np.random.uniform(x_min, x_max, n_points)
        y = np.random.uniform(y_min, y_max, n_points)
        z = np.random.uniform(z_min, z_max, n_points)

        # set last point equal to first to have a closed trajectory
        x[n_points-1] = x[0]
        y[n_points-1] = y[0]
        z[n_points-1] = z[0]

        smoothness = 0
        tck, u = interpolate.splprep([x, y, z], s=smoothness)
        u_fine = np.linspace(0, 1, n_sampling_points)
        x_function, y_function, z_function = interpolate.splev(u_fine, tck)

        return x_function, y_function, z_function

    def objects_state_update_loop(self):
        
        while not rospy.is_shutdown():
            if move:
                self.n_objects = int(rospy.get_param("n_objects", 1))
                # Initialization of ModelState() messages
                objects_model_state = [ModelState() for i in range(self.n_objects)]
                # Get objects model names
                for i in range(self.n_objects):
                    objects_model_state[i].model_name = rospy.get_param("object_" + repr(i) + "_model_name")
                    rospy.loginfo(rospy.get_param("object_" + repr(i) + "_model_name"))

                # Generate Movement Trajectories
                objects_trajectories = []
                for i in range(self.n_objects):
                    function = rospy.get_param("object_" + repr(i) + "_function")
                    if function == "triangle_wave":
                        x = rospy.get_param("object_" + repr(i) + "_x")
                        y = rospy.get_param("object_" + repr(i) + "_y")
                        a = rospy.get_param("object_" + repr(i) + "_z_amplitude")
                        f = rospy.get_param("object_" + repr(i) + "_z_frequency")
                        o = rospy.get_param("object_" + repr(i) + "_z_offset")
                        x_trajectory, y_trajectory, z_trajectory = self.get_triangle_wave(x, y, a, f, o)
                    elif function == "3d_spline":
                        x_min = rospy.get_param("object_" + repr(i) + "_x_min")
                        x_max = rospy.get_param("object_" + repr(i) + "_x_max")
                        y_min = rospy.get_param("object_" + repr(i) + "_y_min")
                        y_max = rospy.get_param("object_" + repr(i) + "_y_max")
                        z_min = rospy.get_param("object_" + repr(i) + "_z_min")
                        z_max = rospy.get_param("object_" + repr(i) + "_z_max")
                        n_points = rospy.get_param("object_" + repr(i) + "_n_points")
                        n_sampling_points = rospy.get_param("n_sampling_points")
                        x_trajectory, y_trajectory, z_trajectory = self.get_3d_spline(x_min, x_max, y_min, y_max, z_min, z_max, n_points, n_sampling_points)
                    objects_trajectories.append([x_trajectory, y_trajectory, z_trajectory])

                # Move objects 
                s = 0 
                while move: 
                    s = s % self.samples_len
                    for i in range(self.n_objects):
                        objects_model_state[i].pose.position.x = objects_trajectories[i][0][s]
                        objects_model_state[i].pose.position.y = objects_trajectories[i][1][s]
                        objects_model_state[i].pose.position.z = objects_trajectories[i][2][s]
                        self.set_model_state_pub.publish(objects_model_state[i])             
                    rospy.Rate(self.update_rate).sleep()
                    s = s + 1

                # Move objects up in the air 
                for i in range(self.n_objects):
                        objects_model_state[i].pose.position.x = i
                        objects_model_state[i].pose.position.y = 0.0
                        objects_model_state[i].pose.position.z = 3.0
                        self.set_model_state_pub.publish(objects_model_state[i]) 
                rospy.Rate(self.update_rate).sleep()
            else:
                pass 



if __name__ == '__main__':
    try:
        rospy.init_node('objects_controller')
        oc = ObjectsController()
        oc.objects_state_update_loop()
    except rospy.ROSInterruptException:
        pass

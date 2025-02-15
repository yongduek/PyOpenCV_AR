from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import cv2
import cv2.aruco as aruco
from PIL import Image
import numpy as np
import imutils
import sys

 
from tools.Visualize import draw_axis
from objloader import * #Load obj and corresponding material and textures.
from MatrixTransform import extrinsic2ModelView, intrinsic2Project 
from Filter import Filter


class AR_render:
    
    def __init__(self, camera_matrix, dist_coefs, object_path, model_scale = 0.03):
        
        """[Initialize]
        
        Arguments:
            camera_matrix {[np.array]} -- [your camera intrinsic matrix]
            dist_coefs {[np.array]} -- [your camera difference parameters]
            object_path {[string]} -- [your model path]
            model_scale {[float]} -- [your model scale size]
        """
        # Initialise webcam and start thread
        # self.webcam = cv2.VideoCapture(0)
        self.webcam = cv2.VideoCapture(0)
        self.image_w, self.image_h = map(int, (self.webcam.get(3), self.webcam.get(4)))
###
        self.image_w, self.image_h = 640, 480
###
        self.initOpengl(self.image_w, self.image_h)
        self.model_scale = model_scale
    
        self.cam_matrix,self.dist_coefs = camera_matrix, dist_coefs
        self.projectMatrix = intrinsic2Project(camera_matrix, self.image_w, self.image_h, 0.01, 100.0)
        self.loadModel(object_path)
        
        # Model translate that you can adjust by key board 'w', 's', 'a', 'd'
        self.translate_x, self.translate_y, self.translate_z = 0, 0, 0
        self.pre_extrinsicMatrix = None
        
        self.filter = Filter()
        

    def loadModel(self, object_path):
        
        """[loadModel from object_path]
        
        Arguments:
            object_path {[string]} -- [path of model]
        """
        self.model = OBJ(object_path, swapyz = True)

  
    def initOpengl(self, width, height, pos_x = 500, pos_y = 500, window_name = b'Aruco Demo'):
        
        """[Init opengl configuration]
        
        Arguments:
            width {[int]} -- [width of opengl viewport]
            height {[int]} -- [height of opengl viewport]
        
        Keyword Arguments:
            pos_x {int} -- [X cordinate of viewport] (default: {500})
            pos_y {int} -- [Y cordinate of viewport] (default: {500})
            window_name {bytes} -- [Window name] (default: {b'Aruco Demo'})
        """
        
        glutInit()
        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH)
        glutInitWindowSize(width, height)
        glutInitWindowPosition(pos_x, pos_y)
        
        self.window_id = glutCreateWindow(window_name)
        glutDisplayFunc(self.draw_scene)
        glutIdleFunc(self.draw_scene)
        
        glClearColor(0.0, 0.0, 0.0, 0.0)
        glClearDepth(1.0)
        glShadeModel(GL_SMOOTH)
        glDepthFunc(GL_LESS)
        glEnable(GL_DEPTH_TEST)
        
        # # Assign texture
        glEnable(GL_TEXTURE_2D)
        
        # Add listener
        glutKeyboardFunc(self.keyBoardListener)
        
        # Set ambient lighting
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.5,0.5,0.5,1)) 
        
        
        
        
 
    def draw_scene(self):
        """[Opengl render loop]
        """
#        _, image = self.webcam.read()# get image from webcam camera.
##
        image = cv2.imread("aruco.jpg")
##
        self.draw_background(image)  # draw background
        # glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.draw_objects(image, mark_size = 0.06) # draw the 3D objects.
        glutSwapBuffers()
    
        
        # TODO add close button
        # key = cv2.waitKey(20)
        
       
        
 
 
 
    def draw_background(self, image):
        """[Draw the background and tranform to opengl format]
        
        Arguments:
            image {[np.array]} -- [frame from your camera]
        """
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # Setting background image project_matrix and model_matrix.
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(33.7, 1.3, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
     
        # Convert image to OpenGL texture format
        bg_image = cv2.flip(image, 0)
        bg_image = Image.fromarray(bg_image)     
        ix = bg_image.size[0]
        iy = bg_image.size[1]
        bg_image = bg_image.tobytes("raw", "BGRX", 0, -1)
  
  
        # Create background texture
        texid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texid)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, 3, ix, iy, 0, GL_RGBA, GL_UNSIGNED_BYTE, bg_image)
                
        glTranslatef(0.0,0.0,-10.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 1.0); glVertex3f(-4.0, -3.0, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex3f( 4.0, -3.0, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex3f( 4.0,  3.0, 0.0)
        glTexCoord2f(0.0, 0.0); glVertex3f(-4.0,  3.0, 0.0)
        glEnd()

        glBindTexture(GL_TEXTURE_2D, 0)
 
 
 
    def draw_objects(self, image, mark_size = 0.05):
        """[draw models with opengl]
        
        Arguments:
            image {[np.array]} -- [frame from your camera]
        
        Keyword Arguments:
            mark_size {float} -- [aruco mark size: unit is meter] (default: {0.07})
        """
        # aruco data
        # aruco_dict = aruco.Dictionary_get(aruco.DICT_6X6_250)      
        aruco_dict = aruco.Dictionary_get(aruco.DICT_4X4_250)      
        parameters =  aruco.DetectorParameters_create()

        height, width, channels = image.shape
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        corners, ids, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters = parameters)
        
        rvecs, tvecs, model_matrix = None, None, None
        
        if ids is not None and corners is not None:
            rvecs, tvecs, _= aruco.estimatePoseSingleMarkers(corners, mark_size , self.cam_matrix, self.dist_coefs)
            new_rvecs = rvecs[0,:,:]
            new_tvecs = tvecs[0,:,:]
            # test = draw_axis(image, new_rvecs, new_tvecs, self.cam_matrix, self.dist_coefs)
            for i in range(rvecs.shape[0]):
                cv2.drawFrameAxes(image, self.cam_matrix, self.dist_coefs, rvecs[i, :, :], tvecs[i, :, :], 0.03)
            
        projectMatrix = intrinsic2Project(self.cam_matrix, width, height, 0.01, 100.0)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glMultMatrixf(projectMatrix)
        
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
       
        
        # if tvecs is not None:
        #     if self.filter.update(tvecs): # the mark is moving
        #         model_matrix = extrinsic2ModelView(rvecs, tvecs)
        #     else:
        #         model_matrix = self.pre_extrinsicMatrix
        # else:
        #     model_matrix =  self.pre_extrinsicMatrix

        model_matrix = extrinsic2ModelView(rvecs, tvecs)
        # print(model_matrix)
            
        if model_matrix is not None:     
            self.pre_extrinsicMatrix = model_matrix
            glLoadMatrixf(model_matrix)
            glScaled(self.model_scale, self.model_scale, self.model_scale)
            glTranslatef(self.translate_x, self.translate_y, self.translate_z)

            glCallList(self.model.gl_list)
            
        cv2.imshow("Frame",image)
        ch = cv2.waitKey(20)
        # print(int(ch))
        if ch == 32: exit()
        

    def keyBoardListener(self, key, x, y):
        """[Use key board to adjust model size and position]
        
        Arguments:
            key {[byte]} -- [key value]
            x {[x cordinate]} -- []
            y {[y cordinate]} -- []
        """
        key = key.decode('utf-8')
        if key == '=':
            self.model_scale += 0.01
        elif key == '-':
            self.model_scale -= 0.01
        elif key == 'x':
            self.translate_x -= 0.01
        elif key == 'X':
            self.translate_x += 0.01
        elif key == 'y':
            self.translate_y -= 0.01
        elif key == 'Y':
            self.translate_y += 0.01
        elif key == 'z':
            self.translate_z -= 0.01
        elif key == 'Z':
            self.translate_z += 0.01 
        elif key == '0':
            self.translate_x, self.translate_y, self.translate_z = 0, 0, 0
        
    def run(self):
        # Begin to render
        glutMainLoop()
  

if __name__ == "__main__":
    # The value of cam_matrix and dist_coeff from your calibration by using chessboard.
    cam_matrix = np.array([
         [544.91, 0.00, 316.75],
         [0.00, 606.31, 261.07],
         [0.00, 0.00, 1.00],
    ])

    # dist_coeff = np.array([0.49921041, -2.2731793, -0.01392174, 0.01677649, 3.99742617])    
    dist_coeff = np.array([ 2.84542709e-01,-1.92052859e+00,1.35772811e-05,-7.62765800e-04,4.00245238e+00]) 
    ar_instance = AR_render(cam_matrix, dist_coeff, './Models/plastic_cup/Plastic_Cup.obj', model_scale = 0.02)
    # ar_instance = AR_render(cam_matrix, dist_coeff, './Models/Monster/Sinbad_4_000001.obj', model_scale = 0.02)
    ar_instance.run() 
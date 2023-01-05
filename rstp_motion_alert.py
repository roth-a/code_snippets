#%%

import smtplib    , datetime    
import time
# For guessing MIME type
# import mimetypes

# Import the email modules we'll need
import email , os
import email.mime.application
import email.mime.multipart as multipart
from email.mime.text import MIMEText



from getpass import getpass
class Mailer():
    def __init__(self, enable_send_email=True, mail_address = "test@mail.com",
              smtp_server = 'smtp.server.org', smtp_port = 587):
                
        self.enable_send_email = enable_send_email
        self.mail_address = mail_address
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        
        if self.enable_send_email:
            self.mail_password = getpass(f'Enter the {mail_address} password:')
            if not self.mail_password:
                self.enable_send_email = False
    
        
    def send_email(self, body_text="<h1>Alarm</h1>", filenames=None):
        if not self.enable_send_email: return
        print(' Sending email')
        #Establish SMTP Connection
        with  smtplib.SMTP(self.smtp_server, self.smtp_port)  as s:
            
            
            # Create a text/plain message
            msg = multipart.MIMEMultipart()
            msg['Subject'] = 'Alarm'
            msg['From'] = self.mail_address
            msg['To'] = self.mail_address
            
            # The main body is just another attachment
            body = MIMEText(body_text)
            msg.attach(body)
            
            for filename in filenames or []:
                with open(filename,'rb') as f: 
    #                 print(os.path.basename(filename))
                    att = email.mime.application.MIMEApplication(f.read(), Name=os.path.basename(filename))
                    att.add_header('Content-Disposition','attachment',filename=os.path.basename(filename))
                    msg.attach(att)
            
            
            s.starttls()
            s.login(self.mail_address, self.mail_password)
            s.sendmail(self.mail_address, [self.mail_address], msg.as_string())        
#           
        print(' Email sent')
    
          
      



#%%
import signal
import cv2, datetime
import numpy as np
from collections import deque
import requests, xmltodict, time


class Camera():
    pass

class Foscam(Camera):
    """
    
    please switch off human detection, otherwise motion detection will not work.

    Args:
        Camera (_type_): _description_
    """
    def __init__(self, username, password, ip, port = 88, past_video_recording_length=2):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.past_video_recording_length = past_video_recording_length
        self.video_capture = None

    def url_rtsp(self):
        return f"rtsp://{self.username}:{self.password}@{self.ip}:{self.port}/videoMain"

    def url_cgi(self, data=None):
        "Data must contain the key 'cmd' "
        import urllib.parse
        if data is None:
            data = {}
        data['usr'] = self.username
        data['pwd'] = self.password         
        return f"http://{self.ip}:{self.port}/cgi-bin/CGIProxy.fcgi?{urllib.parse.urlencode(data)}"



    def get_width_height(self):
        return int(self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    def get_fps(self):
        # Find OpenCV version
        major_ver, minor_ver, subminor_ver = (cv2.__version__).split('.')

        if int(major_ver)  < 3 :
            fps = self.video_capture.get(cv2.cv.CV_CAP_PROP_FPS)
        else :
            fps = self.video_capture.get(cv2.CAP_PROP_FPS)
                
        if fps > 60 or fps < 5:
            print(f'the fps of opencv gives {fps} --> Setting to 30')
            try:
                fps = self.get_main_video_stream_infos().get('frameRate')
            except:
                fps = 30
        return fps
    


    def create_video_capture(self):
        self.video_capture = cv2.VideoCapture(self.url_rtsp(), cv2.CAP_FFMPEG)
        print('Video size {}x{}, fps = {}'.format(*self.get_width_height(), self.get_fps()))

        print(f'The fps is {self.get_fps()}')
        self.frames = deque(maxlen=int(self.past_video_recording_length*self.get_fps()))  # + 1 for the current frame
        return self.video_capture

        
    def get_frame(self, endless_retry=False):
        if not self.video_capture:
            self.create_video_capture()

        check, frame = self.video_capture.read()
        while endless_retry and not check and not self.signal_interupt:
            print('Error: restarting camera')
            self.create_video_capture()
            check, frame = self.video_capture.read()
        
        self.frames.append(frame)
        
        key = cv2.waitKey(1)    
        return frame

    def free(self):
        if self.video_capture:
            self.video_capture.release()
            cv2.destroyAllWindows()
        self.video_capture = None
    
        
                         
    def requests_command(self, data=None, timeout=3):
        response = requests.get(self.url_cgi(data), timeout=timeout)
        doc = xmltodict.parse(response.content)  
        return doc.get('CGI_Result') if 'CGI_Result' in doc else doc
        
        

    def set_datetime(self):
        import requests, datetime
        now = datetime.datetime.now()
        data = {'cmd':'setSystemTime',
                'timeSource':1,
                'ntpServer':'',
                'dateFormat':0,
                'timeFormat':1,
                'timeZone':0,
                'isDst':1,
                'dst':0,
                'year':now.year,
                'mon':now.month,
                'day':now.day,
                'hour':now.hour,
                'minute':now.minute,
                'sec':now.second,
                }

        try:
            res = self.requests_command(data, timeout=10)['result']
            # print(f"Answer from setting datetime: \n{res}")
            return res
        except:
            print('Could not set the time')

        
        
    def get_dev_state(self):
        return self.requests_command({'cmd':'getDevState'})
            
    def detected_motion(self):  
        # 0-Disabled, 1-No Alarm, 2-Detect Alarm
        state = int(self.get_dev_state()['motionDetectAlarm'][0])
        if state == 0:
            print('Warning: The motion detection is disabled. No detection possible')
            return None
        return True if state == 2 else False
            
    def get_motion_detection(self):
        return bool(self.getMotionDetectConfig()['isEnable'][0])

    def getMotionDetectConfig(self):
        return self.requests_command({'cmd':'getMotionDetectConfig'})

    def set_motion_detection(self, enabled=True, timeout=10):
        "https://www.foscam.es/descarga/Foscam-IPCamera-CGI-User-Guide-AllPlatforms-2015.11.06.pdf"
        enabled = bool(enabled)
        data = {
                'cmd':'setMotionDetectConfig',
                'isEnable':int(enabled),
                'linkage':0,
                'snapInterval':3,
                'sensitivity':1,
                'triggerInterval':5,
                'schedule0':281474976710655,
                'schedule1':281474976710655,
                'schedule2':281474976710655,
                'schedule3':281474976710655,
                'schedule4':281474976710655,
                'schedule5':281474976710655,
                'schedule6':281474976710655,
                'area0':1023,
                'area1':1023,
                'area2':1023,
                'area3':1023,
                'area4':1023,
                'area5':1023,
                'area6':1023,
                'area7':1023,
                'area8':1023,
                'area9':1023,
                'isMovAlarmEnable':int(enabled),
                'isPirAlarmEnable':int(enabled),
                }
    
        try: 
            return self.requests_command({'cmd':'getMotionDetectConfig'}, timeout=timeout)['result'][0]
        except:
            print('Error in set_motion_detection')
            
    def get_night_light_status(self):  
        return bool(int( self.requests_command({'cmd':'getNightLightState'})['state']))
            
    def set_night_light_status(self, enabled='toggle'):
        if enabled == 'toggle':
            enabled = not self.get_night_light_status()
        
        return self.requests_command({'cmd':'setNightLightState', 'state':int(enabled)})['result'][0]
    
    def get_video_stream_parameters(self):
        return self.requests_command({'cmd':'getVideoStreamParam'})                                    
                 
    def get_image_setting(self):
        return self.requests_command({'cmd':'getImageSetting'}) 
                                                 
    def get_wifi_list(self):
        return self.requests_command({'cmd':'getWifiList'}) 

    def refresh_wifi_list(self):
        return self.requests_command({'cmd':'refreshWifiList'}, timeout=60) 
    
    def getwifi_config(self):
        return self.requests_command({'cmd':'getWifiConfig'}) 
    def get_port_info(self):
        return self.requests_command({'cmd':'getPortInfo'}) 
    def get_infrared_led_config(self):
        """
        0 Auto mode
        1 Manual mode
        """
        return int(self.requests_command({'cmd':'getInfraLedConfig'})['mode'])
    
    def set_infrared_led_config(self, mode='toggle'):
        """
        0 Auto mode
        1 Manual mode
        """
        if mode == 'toggle':
            mode = int(not bool(self.get_infrared_led_config()))
        assert int(mode) in [0, 1]
        return self.requests_command({'cmd':'setInfraLedConfig', 'mode':int(mode)})
    
    
    def get_infrared_led(self):
        return bool(int(self.get_dev_state()['infraLedState']))
        
    def set_infrared_led(self, enabled='toggle'):
        if enabled == 'toggle':
            enabled = not self.get_infrared_led()
            
        cmd = 'openInfraLed' if int(enabled) else 'closeInfraLed'
        result = self.requests_command({'cmd':cmd}) 
        if result.get('ctrlResult') == "-1" :
            print('Failed.  Please do:  set_infrared_led_config(1)')
        return result
            
    def get_log(self):
        return self.requests_command({'cmd':'getLog'})  
    def get_main_video_stream_type(self):
        "The stream type 0~3"
        return int(self.requests_command({'cmd':'getMainVideoStreamType'})['streamType'])
    def set_main_video_stream_type(self, value=1):
        "The stream type 0~3,  0 seems to be too high quality"
        return self.requests_command({'cmd':'setMainVideoStreamType', 'streamType':value})

    def get_video_stream_infos(self):
        info = self.get_video_stream_parameters()
        keys = ['resolution', 'bitRate', 'isVBR', 'frameRate']
        infos = [{
            key:info.get(f'{key}{i}') for key in keys
        } for i in range(4)]
        return infos

    def get_main_video_stream_infos(self):
        return self.get_video_stream_infos()[self.get_main_video_stream_type()]



class MotionRecorder():
    def __init__(self, camera, video_recording_length=10, past_video_recording_length=2,
              enable_motion_alarm=True, rec_folder = '/tmp', mailer=None):
        
        self.signal_interupt = False
        self.camera = camera
        signal.signal(signal.SIGINT, self.interrupt_handler)        


        self.reference_frame = None
        self.reference_frame_time = datetime.datetime.now()
        self.reference_frame_reset = 10*video_recording_length
        self.show_video = not enable_motion_alarm
        self.motion_thresholds_percentage = [1, 60]
        self.gaussianblur = 25
        self.boxblur = 5
        
        self.video_recording_length = video_recording_length
        self.enable_motion_alarm = enable_motion_alarm
        
        
        self.rec_folder = rec_folder
        self.create_data_folder()
            
        self.mailer = mailer


    def create_data_folder(self):
        try:
            os.makedirs(self.rec_folder, exist_ok=True)
        except:
            pass    
        if not os.path.exists(self.rec_folder):
            self.rec_folder = '/tmp'
            
        
    def interrupt_handler(self, signum, frame):
        print("Ctrl-c was pressed. Quitting. ")
        self.signal_interupt = True
        self.camera.free()

    
        
        
    def set_reference_frame(self, blur_frame):
        print('Reset reference frame')
        self.reference_frame = blur_frame
        self.reference_frame_time = datetime.datetime.now()
        
        
    def get_contours(self, frame, set_as_reference_frame=False, save_intermediate_frames=False):
        save_image_counter = 0

        def save_transformed_frame(frame):
            if save_intermediate_frames:  
                self.save_frame(frame, prefix=f'transformed_{save_image_counter}_')
            return save_image_counter + 1
        
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        save_image_counter = save_transformed_frame(gray_frame)  #  if  save_intermediate_frames
        gray_frame = cv2.GaussianBlur(gray_frame, (self.gaussianblur, self.gaussianblur), 0)
        save_image_counter = save_transformed_frame(gray_frame)  #  if  save_intermediate_frames
    
        blur_frame = cv2.blur(gray_frame, (self.boxblur, self.boxblur))
        save_image_counter = save_transformed_frame(blur_frame)  #  if  save_intermediate_frames
        
        if self.reference_frame is None:
            self.set_reference_frame(blur_frame)
            return 
    
        delta_frame = cv2.absdiff(self.reference_frame, blur_frame)

        # threshold the diff image so that we get the foreground
        #thresholded = cv2.threshold(delta_frame, 25, 255, cv2.THRESH_BINARY)[1]        
        #save_image_counter = save_transformed_frame(thresholded)  #  if  save_intermediate_frames

        if (datetime.datetime.now() - self.reference_frame_time  > datetime.timedelta(seconds=self.reference_frame_reset)) or set_as_reference_frame:
            self.set_reference_frame(blur_frame)
    
        threshold_frame = cv2.threshold(delta_frame,35,255, cv2.THRESH_BINARY)[1]
        contours, _ = cv2.findContours(threshold_frame,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        return contours
    
    
    def contour_over_threshold(self, area):     
        if not isinstance(area, (int, float)):
            area = cv2.contourArea(area)
        width, height = self.camera.get_width_height()
        return self.motion_thresholds_percentage[0]/100  <= area/(width*height+1) <= self.motion_thresholds_percentage[1]/100
    
    
    def contours_over_threshold(self, contours):     
        "Checks if the largest area fulfills the threshold criteria"
        if contours:
            max_area = max([cv2.contourArea(c) for c in contours])
            width, height = self.camera.get_width_height()
            if self.contour_over_threshold(max_area):
                print('Largest area changed {0:.5f}% of the image'.format(100*max_area/(width*height+1)))
                #print(f'contour_over_threshold,  Max area: {max_area} of {width*height+1}')
                return True
        return False
                
    def paint_contours(self, contours, frame):
        if not contours:
            return
        for c in contours:
            if  self.contour_over_threshold(c):
                (x, y, w, h)=cv2.boundingRect(c)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 1)
    
    
    
    def save_frame(self, frame, prefix=''):
        self.create_data_folder()
        filename = os.path.join(self.rec_folder, f"{prefix}frame_{datetime.datetime.now()}.jpg")
        cv2.imwrite(filename, frame)  
        return filename
        
        
        
    def record_video(self):    
        self.create_data_folder()
        filename = os.path.join(self.rec_folder, f"frame_{datetime.datetime.now()}.avi")            
        width, height = self.camera.get_width_height()
        writer= cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'XVID'), self.camera.get_fps(),  (width, height))
            
            
        print('  Start recording')
        def write_frame(frame, set_as_reference_frame=False):
            contours = self.get_contours(frame, set_as_reference_frame=set_as_reference_frame)
            self.paint_contours(contours, frame)            
            writer.write(cv2.resize(frame, (width, height)))            
        
        print(f'Writing {len(self.camera.frames)} old frames')
        for frame in self.camera.frames:
            write_frame(frame)
            
        start_time = datetime.datetime.now()
        continue_recording = True
        while continue_recording:
            if datetime.datetime.now() - start_time >= datetime.timedelta(seconds=self.video_recording_length):
                continue_recording = False
                
            write_frame(self.camera.get_frame(), set_as_reference_frame=not continue_recording)
            
        print('  End recording --> {}'.format(filename))
        self.camera.frames.clear() # all were written via write_frame
        self.camera.set_datetime()
        return filename
        
    
        
    def callback_alarm(self, frame):
        print(f'\n========== alarm {datetime.datetime.now()}  =============')
        print(f"   View with dragon {self.camera.url_rtsp()}" )
        image_filename = self.save_frame(frame)
        if self.mailer:
            self.mailer.send_email(filenames=[image_filename])
    
        video_filename = self.record_video()
        if self.mailer:
            self.mailer.send_email(filenames=[video_filename])
        print('------- finished alarm   -----------')
    
    
    def start(self, show_transformation_images=True):        
        self.camera.set_datetime()
        # get initial transformed frames to see the transformations
        if show_transformation_images:
            frame = self.camera.get_frame(endless_retry=True)
            contours = self.get_contours(frame, save_intermediate_frames=True)


        while not self.signal_interupt:
            frame = self.camera.get_frame(endless_retry=True)
            contours = self.get_contours(frame)

#             width, height = self.get_width_height()
            detected_movement = self.contours_over_threshold(contours)
            if detected_movement:
                self.paint_contours(contours, frame)
                if self.enable_motion_alarm:
                    try:
                        self.callback_alarm(frame)
                    except:
                        print('error')
#                         raise
                else:
                    print('Alarm')
        
            if self.show_video:
                cv2.imshow('motion detector', frame) 
        #     record_video(video)

        self.camera.free()

        
    def record_on_motion_alarm(self):                
        inital_settings_done = False
        def inital_settings():
            self.camera.set_datetime()
            self.camera.set_motion_detection(True)
            self.camera.set_main_video_stream_type(value=1)

        # if there is no camera connected, retry this until it works
        while not self.signal_interupt:
            try:          
                inital_settings()          
                inital_settings_done = True
                break
            except:
                print('Error in record_on_motion_alarm. Stuck in set_datetime, set_motion_detection. Is the camera connected?')
                time.sleep(2)

        print('Starting detected_motion loop')
        while not self.signal_interupt:
            try:                    
                if self.camera.detected_motion():                    
                    frame = self.camera.get_frame(endless_retry=False)
                    self.callback_alarm(frame)
                    self.camera.free()
                    

                    # do this again if the camera was offline or changed for some reason
                    if not inital_settings_done:
                        inital_settings()
                        inital_settings_done = True
                else:
                    time.sleep(1)
            except Exception as e:
                print('Error in record_on_motion_alarm. Is the camera connected?')
                print(traceback.format_exc(), e)
                time.sleep(2)
                # if there are errors (like the camera being offline), then ensure that inital_settings will we done again
                inital_settings_done = False
            finally:
                self.camera.free()
                

 
 #%%
from collections import defaultdict
import sys 
import traceback


def load_config():
    folder = os.path.dirname(os.path.abspath( __file__))
    if os.path.exists(os.path.join(folder, 'config.py')):
        sys.path.append(folder)
        import config
        print('Config imported successfully')
        return config.CONFIG    
    else:
        return defaultdict(str)
CONFIG = load_config()
    
 
 # arguments
import argparse

parser = argparse.ArgumentParser(description='Motion recording for rtsp cameras')
parser.add_argument('--video_recording_length', type=int, default=10, help='length of videos in seconds\n(default: %(default)s)') 
parser.add_argument('--past_video_recording_length', type=int, default=2, help='Record previous seconds\n(default: %(default)s)') 
parser.add_argument('--rec_folder', type=str, default=CONFIG['rec_folder'], help='Recording folder\n(default: "%(default)s")') 
parser.add_argument('--password', type=str, default=CONFIG['password'], help='rtsp password\n(default: %(default)s)') 
parser.add_argument('--ip', type=str, default=CONFIG['ip'], help='ip of foscam \n(default: %(default)s)') 
parser.add_argument('--username', type=str, default=CONFIG['username'], help='rtsp username\n(default: %(default)s)') 
parser.add_argument('--port', type=int, default=88, help='rtsp port\n(default: %(default)s)')

parser.add_argument('--mail_address', type=str, default=CONFIG['mail_address'], help='mail_address\n(default: %(default)s)') 
parser.add_argument('--smtp_server', type=str, default=CONFIG['smtp_server'], help='smtp_server\n(default: %(default)s)') 
parser.add_argument('--smtp_port', type=int, default=587, help='smtp port\n(default: %(default)s)') 

parser.add_argument('--enable_mailer', action='store_true')
parser.add_argument('--record_all_video_motion', action='store_true')
parser.add_argument('--record_human_video_motion', action='store_true')
parser.add_argument('--call_camera_function', type=str, nargs='+', default="", help=', '.join([s for s in dir(Foscam) if not s.startswith('_')]))

args = parser.parse_args()
#print(args)
     
#%%

mailer = Mailer(enable_send_email=True,  mail_address=args.mail_address, smtp_server=args.smtp_server, smtp_port=args.smtp_port) if args.enable_mailer else None

#%%

camera = Foscam(args.username, args.password, args.ip, past_video_recording_length=args.past_video_recording_length, port=args.port)


#%%
mr = MotionRecorder(camera, video_recording_length=args.video_recording_length, rec_folder=args.rec_folder, mailer=mailer)
mr.motion_thresholds_percentage = [0.1,60]
mr.gaussianblur = 3
mr.boxblur = 2


if args.record_all_video_motion:
    mr.start()
elif args.record_human_video_motion:
    mr.record_on_motion_alarm()
elif args.call_camera_function:
    if args.call_camera_function[0] in dir(camera):
        print(getattr(camera, args.call_camera_function[0])(*args.call_camera_function[1:]))


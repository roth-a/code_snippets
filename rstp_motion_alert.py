import smtplib	, datetime	
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
	# 				print(os.path.basename(filename))
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
from collections import deque



class MotionRecorder():
	def __init__(self, video_recording_length=10, past_video_recording_length=2,
			  enable_motion_alarm=True, rec_folder = '/tmp',
			  rtsp_username = "username", rtsp_password = "password", rtsp_IP = "this.ip", rtsp_port = 554,
			  mailer=None):
		
		self.signal_interupt = False
		signal.signal(signal.SIGINT, self.interrupt_handler)		
		
		self.rtsp = f"rtsp://{rtsp_username}:{rtsp_password}@{rtsp_IP}:{rtsp_port}/videoMain" 
		self.video = self.create_camera()
		
		self.frames = deque(maxlen=int(past_video_recording_length*self.get_fps()))  # + 1 for the current frame
		
		self.reference_frame = None
		self.reference_frame_counter = 0
		self.reference_frame_reset = self.get_fps() * video_recording_length
		self.show_video = not enable_motion_alarm
		self.motion_thresholds_percentage = [1, 90]
		
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
		self.video.release()
		cv2.destroyAllWindows()
		self.signal_interupt = True
	
		
	
	
	def get_width_height(self):
		return int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))
	
	def get_fps(self):
		return self.video.get(cv2.CAP_PROP_FPS)
	
	def create_camera(self):
		self.video = cv2.VideoCapture(self.rtsp, cv2.CAP_FFMPEG)	
		print('Video size {}x{}, fps = {}'.format(*self.get_width_height(), self.get_fps()))
		return self.video
	
	
	
	
	
	
	

		
	def get_frame(self, endless_retry=False):
		check, frame = self.video.read()
		while endless_retry and not check and not self.signal_interupt:
			print('Error: restarting camera')
			self.create_camera()
			check, frame = self.video.read()
		
		self.frames.append(frame)
		
		key = cv2.waitKey(1)	
		return frame
		
		
	def set_reference_frame(self, blur_frame):
		print('Reset reference frame')
		self.reference_frame = blur_frame
		self.reference_frame_counter = 0
	
	def get_contours(self, frame, set_as_reference_frame=False):
		gray_frame=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
		gray_frame=cv2.GaussianBlur(gray_frame,(25,25),0)
	
		blur_frame = cv2.blur(gray_frame, (5,5))
		
		if self.reference_frame is None:
			self.set_reference_frame(blur_frame)
			return  
	
		delta_frame=cv2.absdiff(self.reference_frame, blur_frame)
		self.reference_frame_counter += 1
		if self.reference_frame_counter > self.reference_frame_reset or set_as_reference_frame:
			self.set_reference_frame(blur_frame)
	
		threshold_frame=cv2.threshold(delta_frame,35,255, cv2.THRESH_BINARY)[1]
		(contours,_)=cv2.findContours(threshold_frame,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
		return contours
	
	
	def contour_over_threshold(self, area): 	
		if not isinstance(area, (int, float)):
			area = cv2.contourArea(area)
		width, height = self.get_width_height()
		return self.motion_thresholds_percentage[0]/100  <= area/(width*height+1) <= self.motion_thresholds_percentage[1]/100
	
	
	def contours_over_threshold(self, contours): 	
		"Checks if the largest area fulfills the threshold criteria"
		if contours:
			max_area = max([cv2.contourArea(c) for c in contours])
			if self.contour_over_threshold(max_area): 
				width, height = self.get_width_height()
				print(f'Largest area changed {100*max_area/(width*height)}% of the image')
	# 			print('Max area: {}'.format(max_area)) 
				return True
		return False
				
	def paint_contours(self, contours, frame):
		for c in contours:
			if  self.contour_over_threshold(c):
				(x, y, w, h)=cv2.boundingRect(c)
				cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 1)
	
	
	
	def save_frame(self, frame):
		self.create_data_folder()
		filename = os.path.join(self.rec_folder, f"frame_{datetime.datetime.now()}.jpg")
		cv2.imwrite(filename, frame)  
		return filename
		
		
		
	def record_video(self):	
		self.create_data_folder()
		filename = os.path.join(self.rec_folder, f"frame_{datetime.datetime.now()}.avi")			
		width, height = self.get_width_height()
		writer= cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'XVID'), self.get_fps(),  (width, height))
			
			
		print('  Start recording')
		def write_frame(frame, set_as_reference_frame=False):
			contours = self.get_contours(frame, set_as_reference_frame=set_as_reference_frame)
			self.paint_contours(contours, frame)			
			writer.write(cv2.resize(frame, (width, height)))			
		
		print(f'Writing {len(self.frames)} old frames')
		for frame in self.frames:
			write_frame(frame)		
			
		start_time = datetime.datetime.now()
		continue_recording = True
		while continue_recording:
			if datetime.datetime.now() - start_time >= datetime.timedelta(seconds=self.video_recording_length):
				continue_recording = False
				
			write_frame(self.get_frame(), set_as_reference_frame=not continue_recording)
			
		print('  End recording --> {}'.format(filename))
		return filename
		
	
		
	def callback_alarm(self, frame):
		print('alarm {}'.format(datetime.datetime.now()))
		print(f"   View with VLC {self.rtsp}" )
		image_filename = self.save_frame(frame)
		mailer.send_email(filenames=[image_filename])
	
		video_filename = self.record_video()
		mailer.send_email(filenames=[video_filename])
		print('finished alarm')
	
	
	
	def start(self):
		while not self.signal_interupt:
			frame = self.get_frame(endless_retry=True)		
			contours = self.get_contours(frame)
# 			width, height = self.get_width_height()
			if self.contours_over_threshold(contours):
				self.paint_contours(contours, frame)	
				if self.enable_motion_alarm:
					try:
						self.callback_alarm(frame)
					except:
						print('error')
# 						raise
				else:
					print('Alarm')
		
			if self.show_video:
				cv2.imshow('motion detector', frame) 
		# 	record_video(video)
			
		self.video.release()
		cv2.destroyAllWindows()
		
	
	

#%%

mailer = Mailer(enable_send_email=True, mail_address = "email@mail.com",
			  smtp_server = 'smtp.server.com', smtp_port = 587)

#%%

mr = MotionRecorder(video_recording_length=10, past_video_recording_length=2,
			  enable_motion_alarm=True, rec_folder = '/tmp/data',
			  rtsp_username = "username", rtsp_password = "password", rtsp_IP = "1.1.1.1", rtsp_port = 544,
			  mailer=mailer)
mr.start()

production = True    # switch to False for testing
video_recording_length = 10
rec_folder = '/tmp/'
mail_address = "my@mail.com"
smtp_server = 'smtp.servr.com'
smtp_port = 587

#Enter credentials for CCTV
rtsp_username = "username"
rtsp_password = "password"
rtsp_IP = "ip.of.camera"   
rtsp_port = 554   
rtsp = f"rtsp://{rtsp_username}:{rtsp_password}@{rtsp_IP}:{rtsp_port}/some/path" 

# customize lines above 
    
#%%
enable_send_email = production
enable_motion_alarm = production

#%%
from collections import deque

frame_rate = 20
past_record_frames = int(video_recording_length/2 * frame_rate) 
frames = deque(maxlen=past_record_frames + 1)  # + 1 for the current frame

reference_frame = None
reference_frame_counter = 0
reference_frame_reset = 20 * video_recording_length
show_video = not enable_motion_alarm
threshold = 4000
#%%

import smtplib		
# For guessing MIME type
# import mimetypes

# Import the email modules we'll need
import email , os
import email.mime.application
import email.mime.multipart as multipart
from email.mime.text import MIMEText



from getpass import getpass
if enable_send_email:
	mail_password = getpass(f'Enter the {mail_address} password:')
	if not mail_password:
		enable_send_email = False

	
def send_email(filenames=None):
	print(' Sending email')
	#Establish SMTP Connection
	with  smtplib.SMTP(smtp_server, smtp_port)  as s:
		
		
		# Create a text/plain message
		msg = multipart.MIMEMultipart()
		msg['Subject'] = 'Alarm'
		msg['From'] = mail_address
		msg['To'] = mail_address
		
		# The main body is just another attachment
		body = MIMEText("""<h1>Alarm</h1>""")
		msg.attach(body)
		
		for filename in filenames or []:
			with open(filename,'rb') as f: 
# 				print(os.path.basename(filename))
				att = email.mime.application.MIMEApplication(f.read(), Name=os.path.basename(filename))
				att.add_header('Content-Disposition','attachment',filename=os.path.basename(filename))
				msg.attach(att)
		
		
		s.starttls()
		s.login(mail_address, mail_password)
		s.sendmail(mail_address, [mail_address], msg.as_string())		
	  
	print(' Email sent')

	  
  

#%%


import signal
signal_interupt = False
def handler(signum, frame):
	print("Ctrl-c was pressed. Quitting. ")
	video.release()
	cv2.destroyAllWindows()
	global signal_interupt
	signal_interupt = True

signal.signal(signal.SIGINT, handler)		
		
#%%

#!/usr/bin/env python3
import cv2, datetime
# import threading



def create_camera():
	cap = cv2.VideoCapture(rtsp, cv2.CAP_FFMPEG)	
	return cap


#%%

def get_frame(video, endless_retry=False):
	check, frame = video.read()
	while endless_retry and not check and not signal_interupt:
		print('Error: restarting camera')
		video=create_camera()
		check, frame = video.read()
	
	frames.append(frame)
	
	key = cv2.waitKey(1)	
	return frame
	
	

def get_contours(frame):
	gray_frame=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
	gray_frame=cv2.GaussianBlur(gray_frame,(25,25),0)

	blur_frame = cv2.blur(gray_frame, (5,5))
	
	global reference_frame 
	if reference_frame is None:
		reference_frame = blur_frame
		return  

	delta_frame=cv2.absdiff(reference_frame,blur_frame)
	global reference_frame_counter
	reference_frame_counter += 1
	if reference_frame_counter > reference_frame_reset:
		print('Reset reference frame')
		reference_frame_counter = 0
		reference_frame = blur_frame

	threshold_frame=cv2.threshold(delta_frame,35,255, cv2.THRESH_BINARY)[1]
	(contours,_)=cv2.findContours(threshold_frame,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
	return contours


def contours_over_threshold(contours, threshold=threshold): 	
	if contours:
		max_area = max([cv2.contourArea(c) for c in contours])
		if max_area >= threshold:
			print('Max area: {}'.format(max_area)) 
			return True
	return False
			
def paint_contours(contours, frame, threshold=threshold):
	for c in contours:
		if cv2.contourArea(c) < threshold:
			continue
		(x, y, w, h)=cv2.boundingRect(c)
		cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 1)



def save_frame(frame, folder=rec_folder):
	try:
		os.makedirs(folder, exist_ok=True)
	except:
		pass

	if not os.path.exists(folder):
		folder = '/tmp'
	filename = os.path.join(folder, f"frame_{datetime.datetime.now()}.jpg")
	cv2.imwrite(filename, frame)  
	return filename
	
	
	
def record_video(video, folder=rec_folder):	
	try:
		os.makedirs(folder, exist_ok=True)
	except:
		pass
	
	if not os.path.exists(folder):
		folder = '/tmp'
	start_time = datetime.datetime.now()
	filename = os.path.join(folder, f"frame_{datetime.datetime.now()}.avi")
	width=  int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
	height= int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
		
	writer= cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'XVID'), frame_rate, (width,height))
		
		
	print('  Start recording')
	def write_frame(frame):
		contours = get_contours(frame)
		paint_contours(contours, frame)			
		writer.write(cv2.resize(frame, (width, height)))			
	
	print(f'Writing {len(frames)} old frames')
	for frame in frames:
		write_frame(frame)		
		
	while True:
		frame = get_frame(video)		
		write_frame(frame)
		
		if datetime.datetime.now() - start_time >= datetime.timedelta(seconds=video_recording_length):
			break	
	print('  End recording')
	return filename
	

	
def callback_alarm(video, frame):
	print('alarm')
	print(f"   View with VLC {rtsp}" )
	image_filename = save_frame(frame)
	if enable_send_email:
		send_email([image_filename])

	video_filename = record_video(video)
	if enable_send_email:
		send_email([video_filename])
	print('finished alarm')



video=create_camera()

while not signal_interupt:
	frame = get_frame(video, endless_retry=True)		
	contours = get_contours(frame)
	if contours_over_threshold(contours):
		paint_contours(contours, frame)	
		if enable_motion_alarm:
			try:
				callback_alarm(video, frame)
			except:
				print('error')
		else:
			print('Alarm')

	if show_video:
		cv2.imshow('motion detector', frame) 
# 	record_video(video)
	
video.release()
cv2.destroyAllWindows()






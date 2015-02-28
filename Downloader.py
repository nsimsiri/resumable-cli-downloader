import os 
import socket
import TrackHandler
import HeaderHandler as H
import subprocess
from urlparse import urlparse

class Downloader(object):
	def __init__(self, filename, host, path=None, server_port=None, user_directory='/Users/Shared/rget_natcha'):

		# clean up
		if (path==None or len(path)==0): path='/'
		# instance field setup
		self._connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		self._port = 80
		self._server_port = server_port #will implement
		self._host = host
		self._path = path
		self._url = host+path
		self._urlhash = str(hash(self._url))
		self._tempfilename = 'file-%s'%(self._urlhash)
		self._filename = filename
		#directories
		self._usrdir = user_directory
		self._usrdir_download = "%s/download"%(self._usrdir)
		self._usrdir_temp = "%s/temp"%(self._usrdir)

		self._track_filedir = '%s/.tracktable.txt'%(self._usrdir_temp)
		self._temp_track_filedir = '%s/.track_hash-%s.txt'%(self._usrdir_temp, self._urlhash)
		self._filedir = '%s/temp_%s'%(self._usrdir_temp, self._tempfilename)

		self._finished_filedir = "%s/%s"%(self._usrdir_download, self._filename)

		print"\nfile=> %s\n\ttrack=> %s\n\ttemp track=>%s\n\turl=> %s\n\tfinished@=>%s"%(self._filedir, self._track_filedir, self._temp_track_filedir, self._url, self._finished_filedir)
		# directory creation
		if (not os.path.exists(self._usrdir)): os.mkdir(self._usrdir)
		if (not os.path.exists(self._usrdir_download)):  os.mkdir(self._usrdir_download)
		if (not os.path.exists(self._usrdir_temp)):  os.mkdir(self._usrdir_temp)

		self._connection.connect((socket.gethostbyname(self._host), self._port)) ## connect sockets

	def _open_file(self, path, m, default_value=None):
		if (not os.path.exists(path)): 
			print("\ncreating %s\n"%(path))
			f = open(path, 'w')
			if (default_value!=None): f.write(str(default_value))
			f.close()
		return open(path, m)

	def request_header(self): 
		header = str()
		#self._connection.connect((socket.gethostbyname(self._host), self._port)) ## connect sockets
		self._connection.settimeout(3)
		request_string = H.HeaderHandler.create_headerrequest(self._host, path=self._path, port=self._server_port)
		print(request_string)
		self._connection.send(request_string)
		data=''
		breaker = 0
		while(not (H.HeaderHandler.get_headerpad() in header)):
			try:
				data = self._connection.recv(1)
			except(KeyboardInterrupt, SystemExit, socket.timeout):
				self._connection.close()
			if (len(header)==0): 
				breaker += 1
				if (breaker>100): return None
			header += data
		#self._connection.close()
		headerObj = H.HeaderHandler(header)
		return headerObj

		'HEAD /emacs-builds/Emacs-24.3-universal-10.6.8.dmg HTTP/1.1\r\nHost: bandwidth.porkrind.org\r\n\r\n'

	def download(self, pgksize=512):
		#track keeping
		main_tracker = TrackHandler.TrackHandler(self._track_filedir)
		track_val = main_tracker.get_trackvalueforfileurl(self._filedir, self._url)
		if (track_val == None): ## implies no entry for this filename and url, 
			main_tracker.write(self._filedir , self._url, 0) ## write encapsulates adding + checking redundancies  
			track_val = main_tracker.get_trackvalueforfileurl(self._filedir, self._url) 

		temp_tracker = TrackHandler.TrackHandler(self._temp_track_filedir)
		if (not temp_tracker.hastrack(self._filedir, self._url)): 
			temp_tracker.write(self._filedir, self._url, 0)
		print("\nDownload Track at: %i\n"%track_val)

		#handling header
		header = self.request_header()
		print('\nHeader Retrieved:\n%s\n'%header)

		#requesting for download
		self._connection.settimeout(3)
		download_file = self._open_file(self._filedir, 'a') ## open file to append data
		request_string = header.form_httprequest(self._host, self._path, track_val, port = self._server_port)
		
		self._connection.send(request_string)
		data = str()
		break_trial = 0
		data_length = None
		if (header.get_info('Content-Length') != None): 
			data_length = int(header.get_info('Content-Length'))
			print "Content-Length %i"%data_length

		print("CONNECTION INFO:\n%s\n"%request_string)
		#input("check your request..(press a number and enter to continue)")
		print('\ndownloading...\n')
		# status check
		if (not header.is_statusOK()): 
			print("HTTP REQUEST NOT SUCCCESSFUL. ERROR: %s"%(str(header.get_info('HTTP_STATUS'))))
			# redirection
			if (header.is_redirected()): self._redirect(header)
		else:
			while(True):

				if (data_length != None): 
					if (track_val>=data_length):
						#finished downloader for sure
						self._download_cleanup()
						self._finish_download()
						break

				## retrieve data 
				try:
					data = self._connection.recv(pgksize)
				except(KeyboardInterrupt, SystemExit, socket.timeout): ##case of Ctrl-C, program shutdown, disconnection 
					print('--exception thrown--\n')
					print("Session Interrupted..\n")
					self._download_cleanup(track_val)
					self._connection.close()
					if (data_length==None):
						self._finish_download()
					elif (data_length<track_val):
						self._finish_download()
					raise

				if (H.HeaderHandler.get_headerpad() in data): 
				 	data = data.split(H.HeaderHandler.get_headerpad())[1]
				 	#print(data.split(H.HeaderHandler.get_headerpad())[0])
				 

				## writing phase
				#print(data)
				track_val += len(data)
				#print('\ndata: %i, track: %i'%(len(data),track_val))
				if (len(data)>=1):
					download_file.write(data)
					temp_tracker.write(self._filedir, self._url, track_val)
				else: ## case of disconnection or complete download if connection is closed
					break_trial+= 1
					if (break_trial>1000): 
						self._download_cleanup(track_val)
						self._finish_download()
						break
					
		self._connection.close()

	def close(self): self._connection.close()
	def _redirect(self, header): 
		redirected_url = urlparse(header.get_info('Location'))
		self._host = redirected_url.netloc
		if (redirected_url.path != None): self._path = redirected_url.path
		else: self._path = '/'
		if (redirected_url.port != None): self._server_port = redirected_url.port
		else: self._server_port = None
		print("REDIRECTED: host=%s path=%s port=%s"%(self._host, self._path, self._port))
		self._reset()
		self.download()
	def _reset(self):
		self._connection.close()
		self._connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._connection.connect((socket.gethostbyname(self._host), self._port)) ## connect sockets


	def _download_cleanup(self, track_val='-1'):
		## Use this method to clean up tracks once download is "finished" (interupted, disconnected, etc)
		## such that clean up => delete .temp and updates main track file
		temp_tracker = TrackHandler.TrackHandler(self._temp_track_filedir)
		temp_tracker.write(self._filedir, self._url, track_val)
		flush_val = temp_tracker.get_trackvalueforfileurl(self._filedir, self._url)
		self._update_main_track(flush_val)
		temp_tracker.remove()

	def _finish_download(self):
		main_tracker = TrackHandler.TrackHandler(self._track_filedir)
		main_tracker.erase(self._filedir, self._url)
		counter = 1
		dest= self._finished_filedir
		ori = dest
		while(os.path.exists(dest)):
			dest = ori
			filename_splitted = dest.split('.')
			dest = ''.join(filename_splitted[:len(filename_splitted)-1]) + '(%i).'%(counter) + filename_splitted[len(filename_splitted)-1] 
			counter+=1
		os.rename(self._filedir, dest)
		print("Session Finished =)\n%s"%main_tracker)

	def _update_main_track(self, track_val):
		track = TrackHandler.TrackHandler(self._track_filedir)
		if (not track.get_trackvalueforfileurl(self._filedir, self._url)==track_val):
			track.write(self._filedir, self._url, track_val)
		


if (__name__=='__main__'):
	#r = Downloader('en.wikipedia.org', path='/wiki/Chunked_transfer_encoding')
	#r = Downloader('www.newhealthguide.org','/images/10439404/image001.jpg') #http://www.newhealthguide.org/images/10439404/image001.jpg
	#r = Downloader('walljozz.com', '/wp-content/uploads/new-best-Wallpaper.jpg') #http://walljozz.com/wp-content/uploads/new-best-Wallpaper.jpg
	#r = Downloader('www.sanook.com') #http://www.sanook.com
	#r = Downloader('releases.ubuntu.com', '/14.04/ubuntu-14.04-desktop-amd64.iso') #http://releases.ubuntu.com/14.04/ubuntu-14.04-desktop-amd64.iso
	#r = Downloader('emacsformacosx.com', '/emacs-builds/Emacs-24.3-universal-10.6.8.dmg') #http://emacsformacosx.com/emacs-builds/Emacs-24.3-universal-10.6.8.dmg
	#r = Downloader('www.w3.org', server_port=80) 
	#print(r.request_header())
	r.download(pgksize=2048)
	r.close()
	



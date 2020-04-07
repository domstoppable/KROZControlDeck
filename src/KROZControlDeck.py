import obspython as obs
import OBSScriptLib
import os, pathlib
import tkinter
from tkinter import ttk, messagebox
import subprocess
from datetime import datetime

from enum import Enum, auto

#from NetworkClient import NetworkClient

class KROZ_ControlDeck(OBSScriptLib.OBSScriptWithGUI):
	def __init__(self):
		desc = '''            ██╗      ██╗  ██████╗        ██████╗     ███████╗
			██║   ██╔╝  ██╔══██╗  ██╔═══██╗  ╚══███╔╝              😻
			█████╔╝     ██████╔╝  ██║         ██║        ███╔╝            Control
			██╔═██╗     ██╔══██╗  ██║         ██║     ███╔╝                 Deck
			██║      ██╗  ██║      ██║  ╚██████╔╝  ███████╗
			╚═╝      ╚═╝  ╚═╝      ╚═╝     ╚═════╝     ╚══════╝'''
		super().__init__(desc, KROZ_GUI)

		self.saveCompleteAction = None
		self.restartRecordingTimer = 0
#		self.pptClient = None


	def setupProperties(self):
		super().setupProperties()

		self.addProperty('font', 'Font', {'face': 'Merriweather', 'style': 'normal', 'size': 36}, obs.OBS_PROPERTY_FONT)

		self.addProperty('recording_text', 'Text when recording', '\\n⏺️\\n\\nRecording')
		self.addProperty('recording_bg_color', 'Background Color (recording)', '#f00007', obs.OBS_PROPERTY_COLOR)
		self.addProperty('recording_fg_color', 'Font Color (recording)', '#fffff0', obs.OBS_PROPERTY_COLOR)

		self.addProperty('paused_text', 'Text when paused', '\\n⏸\\n\\nPaused')
		self.addProperty('paused_bg_color', 'Background Color (paused)', '#ffff00', obs.OBS_PROPERTY_COLOR)
		self.addProperty('paused_fg_color', 'Font Color (paused)', '#000000', obs.OBS_PROPERTY_COLOR)

		self.addProperty('stopped_text', 'Text when stopped', '\\n⏹️\\n\\nStopped')
		self.addProperty('stopped_bg_color', 'Background Color (stopped)', '#000000', obs.OBS_PROPERTY_COLOR)
		self.addProperty('stopped_fg_color', 'Font Color (stopped)', '#ffffff', obs.OBS_PROPERTY_COLOR)

		self.addProperty('open_immediately', 'Launch with OBS', True)
		self.addProperty('pause_instead_of_stop', 'Pause recording (instead of stopping it)', False)

		self.addProperty('ffmpeg_path', 'Path to FFMPEG binary', pathlib.Path('C:\\Program Files\\ffmpeg-4.2.2-win64-static\\bin'))
		self.addProperty('video_path', 'Path to video location', pathlib.Path('~/Videos').expanduser())
		self.addProperty('resume_delay', 'Delay (s) before resuming record', .5)

#		self.addProperty('ppt_host', 'PowerPoint host', '127.0.0.1')
#		self.addProperty('ppt_port', 'PowerPoint port', 12345)
#
#	def _setupProperties(self):
#		def connectToPPT(props, prop):
#			self.connectToPPT()
#	
#		obsProps = super()._setupProperties()
#		obs.obs_properties_add_button(obsProps, 'connect_to_ppt', 'Connect to PPT', connectToPPT)
#	
#		return obsProps
#
#	def connectToPPT(self):
#		self.pptClient = NetworkClient(self.settings['ppt_host'], self.settings['ppt_port'])
#		if not self.pptClient.connect():
#			self.pptClient = None
#			self.log('PPT connection failed!')
#		else:
#			self.log('PPT connected')

	def onFrontendEvent(self, event):
		self.send(OBSScriptLib.MessageType.OBS_EVENT, event)

	def onLoad(self):
		super().onLoad()

		if self.settings['open_immediately']:
			self.toggleWindow()

		self.recordingSignalHandler = obs.obs_output_get_signal_handler(obs.obs_frontend_get_recording_output())
		self.registerForEvents()
		print(f'{self.name} Loaded!')

	def registerForEvents(self):
		def recordingFinished(*args):
			return self.onRecordingFinished(*args)
		
		obs.signal_handler_connect(self.recordingSignalHandler, 'stop', recordingFinished)

	def onGUIProcessStarted(self):
		super().onGUIProcessStarted()

		if obs.obs_frontend_recording_paused():
			self.send(OBSScriptLib.MessageType.OBS_EVENT, obs.OBS_FRONTEND_EVENT_RECORDING_PAUSED)
		elif obs.obs_frontend_recording_active():
			self.send(OBSScriptLib.MessageType.OBS_EVENT, obs.OBS_FRONTEND_EVENT_RECORDING_STARTED)
		else:
			self.send(OBSScriptLib.MessageType.OBS_EVENT, obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED)

	def onMessageReceived(self, msg):
		super().onMessageReceived(msg)

		if msg.type == OBSScriptLib.MessageType.UI_EVENT:
			if msg.data == 'click':
				if obs.obs_frontend_recording_paused():
					obs.obs_frontend_recording_pause(False)
				elif obs.obs_frontend_recording_active():
					if self.settings['pause_instead_of_stop']:
						obs.obs_frontend_recording_pause(True)
					else:
						obs.obs_frontend_recording_stop()
				else:
					obs.obs_frontend_recording_start()
			elif msg.data == 'reset':
				if obs.obs_frontend_recording_paused() or obs.obs_frontend_recording_active():
					self.log('Resetting to last checkpoint')
					self.saveCompleteAction = self.deleteOnSaveCompleteAndResume
					obs.obs_frontend_recording_stop()
				else:
					self.log('Starting recording')
					obs.obs_frontend_recording_start()
			elif msg.data == 'checkpoint':
				if obs.obs_frontend_recording_paused() or obs.obs_frontend_recording_active():
					self.log('Checkpoint!')
					self.saveCompleteAction = self.resume
					obs.obs_frontend_recording_stop()
				else:
					self.log('Starting recording')
					obs.obs_frontend_recording_start()
			elif msg.data == 'combine':
				if obs.obs_frontend_recording_paused() or  obs.obs_frontend_recording_active():
					obs.obs_frontend_recording_stop()

				self.combineVideos()

	def combineVideos(self):
		now = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

		path = pathlib.Path(self.settings['video_path'])
		chapters = sorted(path.glob('*.mkv'))

		processedFolder = path / 'processed'
		processedFolder.mkdir(parents=True, exist_ok=True)

		outputFilePath = path / f'combined/{now}-combined.mkv'
		outputFilePath.parent.mkdir(parents=True, exist_ok=True)

		chapterFilePath = path / f'chapters-{now}.txt'
		with chapterFilePath.open('w') as chapterFile:
			for c in chapters:
				chapterFile.write('file \'%s\'\n' % str(c))

		ffmpegPath = self.settings['ffmpeg_path'] / 'ffmpeg'
		ffmpegCommand = f'"{ffmpegPath}" -f concat -safe 0 -i "{chapterFilePath}" -c copy "{outputFilePath}"'
		self.log(ffmpegCommand)

		stdoutPath = outputFilePath.parent / (outputFilePath.stem + '-output.txt')
		stdoutPath.write_text(str(chapterFilePath) + '\r\n' + chapterFilePath.read_text() + '\r\n********\r\n' + ffmpegCommand + '\r\n')
		ffmpegResult = subprocess.run(ffmpegCommand, check=True, universal_newlines=True, stdout=stdoutPath.open('a'), stderr=subprocess.STDOUT)
		chapterFilePath.unlink()

		self.send(OBSScriptLib.MessageType.OBS_EVENT, 'combine-complete')

		for chapterVideo in chapters:
			try:
				chapterVideo.rename(processedFolder / chapterVideo.name)
			except:
				self.log('Failed to move ' + chapterVideo.name)

	def onTick(self, seconds):
		super().onTick(seconds)
		if self.restartRecordingTimer > 0:
			self.restartRecordingTimer -= seconds
			if self.restartRecordingTimer <= 0:
				self.debug('RESUMING')
				obs.obs_frontend_recording_start()

#		if self.pptClient is not None:
#			try:
#				pptMsgs = self.pptClient.getMessages()
#				for pptMsg in pptMsgs:
#					self.debug('Received PPT MSG: %s' % pptMsg)
#					self.onPPTMessage(pptMsg)
#			except ConnectionResetError:
#				self.log('Lost PPT connection')
#				self.pptClient = None
#	
#	def onPPTMessage(self, msg):
#		bits = msg.split('|')
#		if bits[0] == 'change-slide':
#			self.log('ppt checkpoint')
#			self.saveCompleteAction = self.resume
#			obs.obs_frontend_recording_stop()
#
	def onRecordingFinished(self, data):
		stopCode = obs.calldata_int(data, 'code')
		if stopCode == 0:
			if self.saveCompleteAction is not None:
				self.saveCompleteAction()

		return True

	def deleteOnSaveCompleteAndResume(self):
		latest = OBSScriptLib.findLatestCapture(self.settings['video_path'])
		self.debug('DELETING %s' % str(latest))
		
		latest.unlink()
		self.resume()

	def resume(self):
		self.saveCompleteAction = None
		self.restartRecordingTimer = self.settings['resume_delay']

class KROZ_GUI(OBSScriptLib.ScriptGUI):
	def initGUI(self, root):
		self.state = None

		root.geometry('360x360')
		root.title('KROZ Control Deck')

		root.geometry('360x360')
		root.title('KROZ Control Deck')
		root.iconphoto(False, tkinter.PhotoImage(file=OBSScriptLib.locateAsset('kroz-icon.png')))

		self.tabWidget = ttk.Notebook(root)
		self.recordingControlsTab = ttk.Frame(self.tabWidget)
		self.fileToolsTab = ttk.Frame(self.tabWidget)

		self.tabWidget.add(self.recordingControlsTab, text='Controller')
		self.tabWidget.add(self.fileToolsTab, text='File tools')
		self.tabWidget.pack(expand=1, fill=tkinter.BOTH)

		self.labelText = tkinter.StringVar()
		self.labelText.set('⌛')

		self.label = tkinter.Button(self.recordingControlsTab, textvariable=self.labelText, fg='gray', bg='black', command=self.onClick)
		self.label.config(font=('Impact', 44))
		self.label.pack(expand=True, fill=tkinter.BOTH)

		self.resetButton = tkinter.Button(self.recordingControlsTab, text='⎌ Reset', command=self.reset)
		self.resetButton.config(font=('Impact', 18))
		self.resetButton.pack(expand=True, fill=tkinter.BOTH, side=tkinter.LEFT)

		self.checkpointButton = tkinter.Button(self.recordingControlsTab, text='✓ Checkpoint', command=self.checkpoint)
		self.checkpointButton.config(font=('Impact', 18))
		self.checkpointButton.pack(expand=True, fill=tkinter.BOTH, side=tkinter.RIGHT)

		self.combineButton = tkinter.Button(self.fileToolsTab, text='Combine all loose videos', command=self.combine)
		self.combineButton.config(font=('Impact', 18))
		self.combineButton.pack(expand=True, fill=tkinter.BOTH)


	def setState(self, state):
		self.debug('Received state %s' % state)
		self.state = state
		self.refreshDisplay()
		
	def refreshDisplay(self):
		f = self.settings['font']
		self.label.config(font=(f['face'], f['size']))

		if self.state == States.RECORDING:
			self.label.config(bg=self.settings['recording_bg_color'], fg=self.settings['recording_fg_color'])
			self.labelText.set(decode(self.settings['recording_text']))
		elif self.state == States.STOPPED:
			self.label.config(bg=self.settings['stopped_bg_color'], fg=self.settings['stopped_fg_color'])
			self.labelText.set(decode(self.settings['stopped_text']))
		elif self.state == States.PAUSED:
			self.label.config(bg=self.settings['paused_bg_color'], fg=self.settings['paused_fg_color'])
			self.labelText.set(decode(self.settings['paused_text']))

	def onMessageReceived(self, msg):
		super().onMessageReceived(msg)

		if msg.type == OBSScriptLib.MessageType.OBS_EVENT:
			if msg.data in [obs.OBS_FRONTEND_EVENT_RECORDING_STARTED, obs.OBS_FRONTEND_EVENT_RECORDING_UNPAUSED]:
				self.setState(States.RECORDING)
			elif msg.data == obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED:
				self.setState(States.STOPPED)
			elif msg.data == obs.OBS_FRONTEND_EVENT_RECORDING_PAUSED:
				self.setState(States.PAUSED)
			elif msg.data == obs.OBS_FRONTEND_EVENT_EXIT:
				self.root.quit()
			elif msg.data == 'combine-complete':
				messagebox.showinfo('Render complete', 'All of your loose videos have been combined into a single render and organized!')
		elif msg.type == OBSScriptLib.MessageType.OBS_SETTINGS:
			self.refreshDisplay()

	def onClick(self):
		self.send(OBSScriptLib.MessageType.UI_EVENT, 'click')

	def checkpoint(self):
		self.send(OBSScriptLib.MessageType.UI_EVENT, 'checkpoint')

	def reset(self):
		self.send(OBSScriptLib.MessageType.UI_EVENT, 'reset')

	def combine(self):
		self.send(OBSScriptLib.MessageType.UI_EVENT, 'combine')

class States(Enum):
	PAUSED = auto()
	RECORDING = auto()
	STOPPED = auto()

def decode(text):
	return text.replace('\\n', '\n').replace('\\t', '\t')


scriptInstance = KROZ_ControlDeck()
scriptInstance.register()

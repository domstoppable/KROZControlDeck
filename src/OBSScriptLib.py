import multiprocessing
from multiprocessing import Process, Queue, Pipe

import sys, os
import argparse
import random
import time
import math
import inspect
import pathlib
import tkinter

from enum import Enum, auto

import obspython as obs

multiprocessing.set_executable(os.path.join(sys.exec_prefix, 'pythonw.exe'))

def findLatestCapture(directory, ignoreName=None):
	def new_video_sort_key(f):
		if f.name[-3:] in ['flv', 'mp4', 'mov', 'mkv'] and f.name is not ignoreName:
			return f.stat().st_mtime
		return 0

	newest_video_file = sorted(os.scandir(directory), key=new_video_sort_key, reverse=True)[0]
	if new_video_sort_key(newest_video_file) is 0:
		print("Could not find any video files!")
		return None

	return pathlib.Path(directory) / newest_video_file.name


def getOBSFont(settings, name):
	font = obs.obs_data_get_obj(settings, name)

	return {
		'face': obs.obs_data_get_string(font, 'face'),
		'style': obs.obs_data_get_string(font, 'style'),
		'size': obs.obs_data_get_int(font, 'size'),
		'flags': obs.obs_data_get_int(font, 'flags'),
	}

def setOBSFont(settings, name, props):
	font = obs.obs_data_create()

	if 'face' in props:
		obs.obs_data_set_default_string(font, 'face', props['face'])
	if 'size' in props:
		obs.obs_data_set_default_int(font, 'size', props['size'])
	if 'style' in props:
		obs.obs_data_set_default_string(font, 'style', props['style'])
	if 'flags' in props:
		obs.obs_data_set_default_int(font, 'flags', props['flags'])

	obs.obs_data_set_obj(settings, name, font)

def getOBSColor(settings, name):
	v = obs.obs_data_get_int(settings, name)
	v = hex(v)[4:]
	b,g,r = v[0:2], v[2:4], v[4:6]

	return '#' + (r+g+b)

def setOBSColor(settings, name, v):
	if v[0] == '#':
		v = v[1:]

	r,g,b = v[0:2], v[2:4], v[4:6]
	asInteger = int('0xff%s' % (b+g+r), 16)
	obs.obs_data_set_default_int(settings, name, asInteger)

def getOBSPath(settings, name):
	return pathlib.Path(obs.obs_data_get_string(settings, name))

def setOBSPath(settings, name, v):
	obs.obs_data_set_default_string(settings, name, str(v))

class OBSProp():
	obsTypeFuncMap = {
		obs.OBS_PROPERTY_COLOR: {
			'add': obs.obs_properties_add_color,
			'setDefault': setOBSColor,
			'get': getOBSColor
		},
		obs.OBS_PROPERTY_BOOL: {
			'add': obs.obs_properties_add_bool,
			'setDefault': obs.obs_data_set_default_bool,
			'get': obs.obs_data_get_bool
		},
		obs.OBS_PROPERTY_TEXT: {
			'add': lambda a,b,c: obs.obs_properties_add_text(a, b, c, obs.OBS_TEXT_DEFAULT),
			'setDefault': obs.obs_data_set_default_string,
			'get': obs.obs_data_get_string
		},
		obs.OBS_PROPERTY_FONT: {
			'add': obs.obs_properties_add_font,
			'setDefault': setOBSFont,
			'get': getOBSFont
		},
		obs.OBS_PROPERTY_PATH: {
			'add': lambda a,b,c: obs.obs_properties_add_path(a, b, c, obs.OBS_PATH_DIRECTORY, '', ''),
			'setDefault': setOBSPath,
			'get': getOBSPath,
		},
		obs.OBS_PROPERTY_FLOAT: {
			'add': lambda a,b,c: obs.obs_properties_add_float(a, b, c, -99999999, 99999999, 1.),
			'setDefault': obs.obs_data_set_default_double,
			'get': obs.obs_data_get_double,
		},
		# int
	}

	dataTypeMap = {
		bool: obs.OBS_PROPERTY_BOOL,
		int: obs.OBS_PROPERTY_INT,
		float: obs.OBS_PROPERTY_FLOAT,
		str: obs.OBS_PROPERTY_TEXT,

		pathlib.Path: obs.OBS_PROPERTY_PATH,
		pathlib.WindowsPath: obs.OBS_PROPERTY_PATH,
		pathlib.PosixPath: obs.OBS_PROPERTY_PATH,
	}

	def __init__(self, name, description, defaultValue, dataType=None):
		self.name = name
		self.description = description
		self.defaultValue = defaultValue

		if dataType is None:
			dataType = OBSProp.dataTypeMap[type(defaultValue)]

		self.type = dataType
		self.funcs = OBSProp.obsTypeFuncMap[self.type]

	def _addToProps(self, settings):
		self.funcs['add'](settings, self.name, self.description)

	def _setDefault(self, settings):
		if self.defaultValue is not None:
			self.funcs['setDefault'](settings, self.name, self.defaultValue)

	def get(self, settings):
		return self.funcs['get'](settings, self.name)


class OBSScript():
	def __init__(self, description='An OBS Script'):
		self.name = self.__class__.__name__

		self.description = description
		self.props = []
		self.settings = {}
		self.setupProperties()

	def setupProperties(self):
		self.addProperty('debug', 'Debug mode', False)
		
	def addProperty(self, name, description, defaultValue=None, dataType=None):
		self.props.append(OBSProp(name, description, defaultValue, dataType))

	def getDescription(self):
		return self.description

	def log(self, *args):
		print(*args)

	def debug(self, *args):
		if self.settings['debug']:
			self.log('[DEBUG]', *args)

	def _setupProperties(self, obsProps=None):
		if obsProps is None:
			obsProps = obs.obs_properties_create()

		for prop in self.props:
			prop._addToProps(obsProps)

		return obsProps

	def _setupDefaults(self, settings):
		for prop in self.props:
			prop._setDefault(settings)

	def register(self):
		stack = inspect.stack()
		callingFrame = stack[1]
		callingModule = inspect.getmodule(callingFrame[0])

		functionNameMap = {
			'script_description': 'getDescription',
			'script_properties': '_setupProperties',
			'script_defaults': '_setupDefaults',
			'script_tick': 'onTick',
			'script_load': '_onLoad',
			'script_update': '_onUpdate'
		}
		for obsFuncName,objFuncName in functionNameMap.items():
			if hasattr(self, objFuncName):
				func = getattr(self, objFuncName)
				setattr(callingModule, obsFuncName, func)

	def onFrontendEvent(self, event):
		pass

	def _onLoad(self, settings):
		def _onFrontendEvent(*args):
			event = args[0]
			self.onFrontendEvent(event)
			
		obs.obs_frontend_add_event_callback(_onFrontendEvent)

		self._loadNewSettings(settings)
		self.onLoad()

	def onLoad(self):
		pass

	def _onUpdate(self, settings):
		self._loadNewSettings(settings)
		self.onUpdate()

	def onUpdate(self):
		pass

	def _loadNewSettings(self, props):
		self.settings = {}
		for prop in self.props:
			self.settings[prop.name] = prop.get(props)


def decode(text):
	return text.replace('\\n', '\n').replace('\\t', '\t')

class MessageType(Enum):
	UI_EVENT = auto()
	OBS_EVENT = auto()
	OBS_SETTINGS = auto()
	LOG = auto()
	DEBUG = auto()
	EXCEPTION = auto()

class Message():
	def __init__(self, messageType, data):
		self.type = messageType
		self.data = data

	def __str__(self):
		return '[%s] %s' % (self.type, self.data)

class OBSScriptWithGUI(OBSScript):
	def __init__(self, description, GUIClass):
		super().__init__(description)

		self.GUIClass = GUIClass
		self.process = None
		self.pipe = None

	def _setupProperties(self):
		def toggleWindow(props, prop):
			self.toggleWindow()

		obsProps = obs.obs_properties_create()
		obs.obs_properties_add_button(obsProps, 'toggle_window', 'Show/Hide', toggleWindow)

		return super()._setupProperties(obsProps)

	def isGUIProcessActive(self):
		return self.process is not None and self.process.is_alive()

	def toggleWindow(self):
		if not self.isGUIProcessActive():
			self.debug('Starting new instance')
			pipe, childPipe = Pipe()
			self.pipe = pipe
			self.process = Process(target=_bootstrapGUIApp, args=(self.GUIClass, childPipe,))
			self.process.start()

			self.onGUIProcessStarted()
		else:
			self.debug('Toggle window')
			self.send(MessageType.UI_EVENT, 'toggle_visibility')


	def onGUIProcessStarted(self):
		self.send(MessageType.OBS_SETTINGS, self.settings)

	def onTick(self, seconds):
		try:
			isActive = self.isGUIProcessActive() and self.pipe is not None
			messageWaiting = False
			if isActive:
				try:
					messageWaiting = self.pipe.poll()
				except:
					pass

			if messageWaiting:
				msg = self.pipe.recv()
				self.onMessageReceived(msg)
		except:
			self.send(MessageType.EXCEPTION, sys.exc_info())

	def onMessageReceived(self, message):
		if message.type == MessageType.LOG:
			self.log('[GUI] %s' % message.data)
		elif message.type == MessageType.DEBUG:
			self.debug('[GUI] %s' % message.data)
		elif message.type == MessageType.EXCEPTION:
			self.log('[GUI][EXCEPTION] %s' % message.data)

	def send(self, msgType, data):
		if self.isGUIProcessActive():
			msg = Message(msgType, data)
			self.debug('Script Sending %s' % msg)
			self.pipe.send(msg)

	def onUpdate(self):
		super().onUpdate()
		if self.isGUIProcessActive():
			self.send(MessageType.OBS_SETTINGS, self.settings)

class ScriptGUI():
	def __init__(self, pipe):
		try:
			self.pipe = pipe
			self.root = tkinter.Tk()
			self.initGUI(self.root)
			self.settings = {}
		except Exception as exc:
			self.exception(exc)

	def _tick(self):
		try:
			self.root.after(250, self._tick)

			if self.pipe.poll():
				msg = self.pipe.recv()
				self.onMessageReceived(msg)

			self.onTick()
		except Exception as exc:
			self.exception(exc)

	def onTick(self):
		pass

	def onMessageReceived(self, message):
		if message.type == MessageType.OBS_SETTINGS:
			self.settings = message.data
		elif message.type == MessageType.UI_EVENT:
			if message.data == 'toggle_visibility':
				if self.root.winfo_viewable():
					self.root.withdraw()
				else:
					self.root.deiconify()

	def send(self, msgType, data):
		self.pipe.send(Message(msgType, data))

	def exception(self, exc=None):
		(type, value, traceback) = sys.exc_info()
		filename = traceback.tb_frame.f_code.co_filename
		lineno = traceback.tb_lineno
		self.send(MessageType.EXCEPTION, '%s\n\t\t%s:%d' % (exc, filename, lineno))

	def log(self, data):
		self.send(MessageType.LOG, data)

	def debug(self, data):
		self.send(MessageType.DEBUG, data)

	def run(self):
		self.debug('Starting up')
		try:
			self._tick()
			self.root.mainloop()
			self.log('Finished')
		except Exception as exc:
			self.exception(exc)

def _bootstrapGUIApp(GUIClass, pipe):
	app = GUIClass(pipe)
	app.run()
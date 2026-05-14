""" 
    name:      dvsTransferLauncher
    author:    Don Johnson
    
    Desc:       This program, expecting at least a playlist of absolute paths to images on the dts server, imports images
                into a dvsClip class and creates and creates a clipster project to view the images.
                
    Notes:     the fuseCpyClient class has been copied over and modified.

"""

import os
import sys
import shutil
import socket
import re
import tempfile
import datetime
from optparse import OptionParser

FFMPEG_PATH = '\\\\dtsdfs\\dts\\appl\\windows\\programs\\'
SERVER_TEMP = '\\\\dtsdfs\\DTS\\DTS_3D\\.tmp'
LOCAL_DRIVE = 'C:\\'

# common stereo image names
STEREO_TAGS = ['Left', 'left', 'Le', 'le', 'LE', 'Right', 'right', 'Re', 're', 'RE']
BAD_STEREO_TAGS = ['LeRe', 'lere', 'Lere', 'leRe', 'pre', 'PRE']

class fuseCpyClient:
    # Base class for managing the copy connection
    def __init__(self, host, log):
        # Define the socket parameters and connect
        self.host = host
        self.port = 1337
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.valid = True
        try:
            self.conn.connect((self.host,self.port))
        except:
            if log != None:
                log.write('[fuseCpyClient] error connecting to ' + str(self.host) + ' on port ' + str(self.port) + '\r\n')
            self.valid = False
            return None

        # Set the connection timeout to prevent blocking
        self.conn.settimeout(5)
        # Retrieve the video base drive for later use
        self.conn.send('basedrive\r\n')
        inDat = self.conn.recv(1024)
        self.baseDrive = inDat[:-2]
    
    def getBaseDrive(self):
        # return the video base drive string to the user
        retVal = re.sub('/', '\\\\', self.baseDrive)
        return retVal

    def chkDir(self,dirPath):
        # create a new subdirectory 
        try:
            # Clean out the base drive letter and conform the slashes to posix rules
            newDirPath = re.sub(self.baseDrive,'',re.sub('\\\\','/', dirPath))
            # Create the directory, return the path if successful
            self.conn.send("chkdir %s\r\n" % newDirPath)
            inDat = self.conn.recv(1024)
            if inDat[:-2] == "chkdir: path exists":
                return True
            else:
                return False
        except:
            return None
        
    def mkDir(self, dirPath, log):
        # create a new subdirectory 
        try:
            # Clean out the base drive letter and conform the slashes to posix rules
            newDirPath = re.sub(self.baseDrive,'',re.sub('\\\\','/', dirPath))
            # Create the directory, return the path if successful
            self.conn.send("mkdir %s\r\n" % newDirPath)
            inDat = self.conn.recv(1024)
            if inDat[:-2] == "mkdir: success":
                if log != None: log.write('Directory '+ dirPath + ' created successfully\r\n')
                return dirPath
            else:
                return None
        except:
            return None

    def copyFile(self, source, dest, log):
        # Copy a file from a remote source to the video directory
        # Conform the paths to posix rules
        newSource = re.sub('\\\\', '/', source)
        newDest = re.sub(self.baseDrive, '', re.sub('\\\\', '/', dest))
        #print 'newSource = ' + newSource
        #print 'newDest = ' + newDest
        # Extend the connection timeout for copying large files
        self.conn.settimeout(60)
        # Perform the copy.  Return the dest path if succesful, or raise an exception
        self.conn.send("copy %s %s\r\n" %(newSource, newDest))
        inDat = self.conn.recv(1024)
        # Set the connection timeout back down
        self.conn.settimeout(5)
        if inDat[:-2] == "copy: complete":
            if log != None: log.write('Copied ' + source + ' to ' + dest + '\r\n')
            return dest
        else:
            if log != None: log.write('Failed to copy ' + source + ' to ' + dest + '\r\n')
            raise Exception()
            
    def closeConn(self):
        # Close the current connection
        self.conn.send("quit\r\n")
        self.conn.close()
#END fuseCpyClient CLASS

# class to hold dvs clip info
class dvsClip:
    def __init__(self, image):
        self.imagesIn = []
        self.imagesOut = []
        self.start = 100000000000
        self.end = 0
        self.mod = None
        self.frames = None
        self.stereo = None
        self.tracked = False
        self.rev = None

        self.stereoChecked = False
        self.bin = '/'
        self.track = 0
        self.name = None

        # split folder path        
        splitName = image.split('\\')
        checkName = splitName[-1].split('.')
        # get the frame number, which comes at the end of the filename before the image format
        if len(checkName) > 4:
            # if the image has frame numbers, remove both the frame numbers and format and return
            self.name = splitName[-1:][0][:-9]
            self.frames = '.%04d'
        else:
            self.name = splitName[-1:][0][:-4]            
            self.frames = None

        self.format = checkName[-1:][0]

        # if hyphens in filename, replace temporarily
        splitName[len(splitName)-1] = splitName[len(splitName)-1].replace('-', '_')
        # split up the file name prefix (seq_shot_stage_version_revision_mod.frame.format)
        nameParts = splitName[len(splitName)-1].split('_')
        self.seq = nameParts[0]
        self.shot = nameParts[1]
        self.stage = nameParts[2]

        # if stereo modifier in the file name, then tag it as a stereo clip        
        for STEREO_TAG in STEREO_TAGS:
            if STEREO_TAG in image:
                self.stereo = STEREO_TAG
                break

        # make sure a stereo tag is not a bad stereo tag (ie, LeRe, etc) which
        # actually has no stereo pair
        for BAD_STEREO_TAG in BAD_STEREO_TAGS:
            if BAD_STEREO_TAG in image:
                self.stereo = None
                break

        # parse the rest of the file name for frame numbers and format
        if 'work' in image:
            self.ver = nameParts[3]
            if len(nameParts) > 5:                
                self.rev = nameParts[4]
                self.mod = nameParts[5].split('.')[0]
            else:
                self.rev = nameParts[5].split('.')[0]
        else:
            if len(nameParts) > 4:
                self.ver = nameParts[3]
                self.mod = nameParts[4].split('.')[0]
            else:
                self.ver = nameParts[3].split('.')[0]
                        

    # add a path, for the current clip, from which to grab an image
    def addImageIn(self, image):
        self.imagesIn.append(image)

    # add a path, for the current clip, to place an image
    def addImageOut(self, image):
        self.imagesOut.append(image)

    # get the the number of images in the current clip    
    def getLength(self):
        return len(self.imagesIn)

    # get the frame number of the current image      
    def getFrame(self, imageName):
        checkName = imageName[len(imageName)-1].split('.')
        # get the frame number, which comes at the end of the filename before the image format
        if len(checkName) > 4:
            return imageName[len(imageName)-1][len(imageName[len(imageName)-1])-8:len(imageName[len(imageName)-1])-4]
        else:
            return None

    # set the range of the clip       
    def setRange(self, frameBegin, frameEnd):
        self.start = int(frameBegin)
        self.end = int(frameEnd)

    # print out the clip info
    def printInfo(self):
        print ('self.imagesIn = ' +  str(self.imagesIn))
        print ('self.imagesOut = ' +  str(self.imagesOut))
        print ('self.start = ' + str(self.start))
        print ('self.end = ' + str(self.end))             
        print ('self.mod = ' + str(self.mod))
        print ('self.frames = ' + str(self.frames))
        print ('self.stereo = ' + str(self.stereo))
        print ('self.tracked = ' + str(self.tracked))
        print ('self.ver = ' + str(self.ver))
        print ('self.rev = ' + str(self.rev))
        print ('self.stereoChecked ' + str(self.stereoChecked))
        print ('self.bin = ' + str(self.bin))
        print ('self.track = ' + str(self.track))
        print ('self.seq = ' + str(self.seq))
        print ('self.shot = ' + str(self.shot))
        print ('self.stage = ' + str(self.stage))
        print ('self.format = ' + str(self.format))
# END dvsClip CLASS

# remove object from list, and return the clean list
def removeFromList(obj, list):
    for l in list:
        if obj in l: list.remove(l)
    return list

# return a list of files in a directory
def listFilesInDir(dtsPath):
    imageList = []
    try:
        imageList = os.listdir(dtsPath)
    except:
        print 'ERROR' + dtsPath
    return imageList
    
# create a directory
# if the directory already exists, upversion and attempt to add again
# return
def createDir(folder, server, testrun, log):
    i = 1
    tempPath = folder
    
    # check that folder doesn't already exist
    # if so, upversion folder name and recheck
    while server.chkDir(tempPath) is True:
        tempPath = folder + '_' + str(i)
        i +=1
    
    folder = tempPath
    if testrun:
        print 'TEST RUN: Able to create folder ' + folder        
        return folder
    
    # create directory with found valid name
    try:
        folder = server.mkDir(folder, log)
    except:
        if log != None:
            log.write('ERROR: unable to create project folder: ' + folder + '\r\n')
            log.close()
        return False
    
    return folder

# 
def getFrameCount(movie):    
    cmd = FFMPEG_PATH + 'ffprobe -show_format ' + movie
    
    f=os.popen(cmd)
    for i in f.readlines():
        if 'duration' in i:
            test = i.split('=')
            length = test[1].rsplit()
            frameCount = int(round(float(length[0])*24.0))
            return frameCount
    return False
        
#
def main():

    # create temp file, via Python
    foutTemp = tempfile.NamedTemporaryFile()
    # store random python file path
    tempName = foutTemp.name.split('\\')
    # close Python temp file, which deletes it
    foutTemp.close()
    # get random name created by temp file
    tempName = tempName[len(tempName)-1]
    
    # initialize playlist file name    
    playlist = None
    project = None
    
    # handle command line args    
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-n", "--name",     action="store",      type="string", default=None,   dest="project",  help="set clipster project name")
    parser.add_option("-p", "--playlist", action="store",      type="string", default=None,     dest="playlist", help="playlist file of absolute paths to images")    
    parser.add_option("-m", "--machine",  action="store",      type="string", default='bobble', dest="host",     help="Machine, either bobble or clank, on which the clipster project will be created", )
    parser.add_option("-t", "--testrun",  action="store_true",                default=False,    dest="testrun",  help="do a test run before actually transferring files and creating a clipster project")
    (options, args) = parser.parse_args()

    #set arguments to easier vars
    
    testrun = options.testrun
    playlist = options.playlist
    host = options.host
    project = options.project

    # setup log file
    log = None
    if not testrun:
        logPath = SERVER_TEMP + '\\' + tempName + '.log'
        log = open(logPath, 'w')    
        print 'LOGFILE created at ' + logPath    

    # if no project name argument, set to current date    
    if project == None:
        now = datetime.datetime.now()
        project = os.environ.get( "USERNAME" ) + '_dvsTransfer'+now.strftime("%Y-%m-%d")

    # if no playlist file included in args, send error
    if playlist == None:
        if not testrun:
            log.write('ERROR: No playlist file specified. Exiting.\r\n')
            log.close()
        parser.error("no playlist file specified")
        return False
    # write arg values to log file
    else:
        if not testrun:
            log.write('Argument NAME = ' + project + ' read in \r\n')
            log.write('Argument PLAYLIST = ' + playlist + ' read in \r\n')
            log.write('Argument MACINE = ' + host + ' read in \r\n')
            log.write('Argument TESTRUN = ' + str(testrun) + ' read in \r\n')
        else:
            print 'Argument NAME = ' + project + ' read in'
            print 'Argument PLAYLIST = ' + playlist + ' read in'
            print 'Argument MACINE = ' + host + ' read in'
            print 'Argument TESTRUN = ' + str(testrun) + ' read in'
    
    #initialize vars
    clipList = []
    thisClip = ''
    stageList = []
    imageName = []
    stereoStageCount = 0

    # open playlist
    try:
        imageList = open(playlist,'r')
    except:
        if testrun:
            print 'TESTRUN ERROR: Invalid playlist file ' + playlist
        else:
            log.write('ERROR: Invalid playlist file '+ playlist + '\r\n')
            log.close()
        return False

    if not testrun: log.write('Opened playlist file '+ playlist + '\r\n')    

    # initialize server     
    server =  fuseCpyClient(host, log)

    if not server.valid:
        if testrun:
            print 'TESTRUN ERROR: Unable to connect with host ' + host
        else:
            log.write('ERROR: Unable to connect with host ' + host + '\r\n')
        return False

    # drive letter on server
    DDSDRIVE = server.getBaseDrive()
    if not testrun: log.write('Base drive on server: ' + DDSDRIVE + '\r\n')
    # location of ffprobe
    if not testrun: log.write('Location of ffmpeg set to:' + FFMPEG_PATH + '\r\n')

    # setup output directory
    outDir = createDir(project, server, testrun, log)

    # if output directory not able to be created, quit    
    if not outDir:
        return False

    # path to folder on server where the images will be sent    
    outPath = DDSDRIVE + outDir
    print 'DIRECTORY for clipster project being created at ' + outPath + ' on host ' + host + '\r\n'
    if not testrun: log.write('Full output directory: ' + outPath + '\r\n')
    
    # check that playlist file exists
    if not os.access(playlist, os.F_OK):
        if not testrun: log.write('ERROR: Invalid playlist file: ' + playlist + '\r\n')
        return False

    sortedImageList = []
    # sort image list before parsing
    for image in imageList.readlines():
        # remove newline tages
        inFile =  image.rsplit()[0]
        sortedImageList.append(image)
    imageList.close()        
    sortedImageList.sort()
    if not testrun: log.write('Image list generated from playlist sorted succesfully\r\n')

    # read in each image in the playlist    
    #for image in imageList.readlines():
    for image in sortedImageList:
        # remove newline tages
        inFile =  image.rsplit()[0]

        # split up absolute path name of file for easier parsing
        imageName = inFile.split('\\')

        # store current image in a temporary clip until
        # determined if to add to clip list or create a new clip list
        tempClip = dvsClip(inFile)
        #tempClip.printInfo()

        # compare tempClip to current clip, and if current image is a frame in a clip, add it to the current clip
        if len(clipList) > 0 and thisClip.seq == tempClip.seq and thisClip.shot == tempClip.shot and thisClip.stage == tempClip.stage and tempClip.ver == thisClip.ver and thisClip.rev == tempClip.rev and thisClip.mod == tempClip.mod and thisClip.frames == tempClip.frames and thisClip.format == tempClip.format and thisClip.stereo == tempClip.stereo:
            thisClip.addImageIn(inFile)
            if not testrun: log.write('Image : ' + inFile + ' added to existing cliplist\r\n')
            thisClip.addImageOut(outPath + '\\' + imageName[len(imageName)-1])
            # check to see if frame numbers exist in image name
            frame = thisClip.getFrame(imageName)
            if frame != None:
                # figure out if the frame number is a new min or max for the frame range
                if int(frame) < int(thisClip.start):
                    thisClip.setRange(frame, thisClip.end)
                if int(frame) > int(thisClip.end):
                    thisClip.setRange(thisClip.start, frame)
            continue
        # if current image is not a frame in the current clip, create a new clip
        else:
            # initialize new clip array
            thisClip = dvsClip(inFile)
           
            # add clip to clip list
            clipList.append(thisClip)
            if not testrun: log.write('New clip created for : ' + inFile + '\r\n')
        
            # add image to clip list
            thisClip.addImageIn(inFile)
            thisClip.addImageOut(outPath + '\\' + imageName[len(imageName)-1])
            
            # check to see if frame numbers exist in image name
            frame = thisClip.getFrame(imageName)
            if frame != None:
                thisClip.setRange(frame, frame)
            # if image name comes without frame numbers, try to figure out the frame range using ffmpeg
            else:
                frameEnd = getFrameCount(image)
                thisClip.setRange(0, frameEnd)
            
            # temp store stage for this clip
            tempStage = thisClip.stage

            # if stage list already initialized, then check to see if stage already exists
            if len(stageList) > 0:
                stageCheck = False
                for stage in stageList:
                    if stage == tempStage:
                        stageCheck = True
                        # store track number in clip info
                        thisClip.track = stageList.index(stage)
                        if not testrun: log.write('Stage ' + stage + ' already tracked\r\n')
                        break
                if not stageCheck:
                    if not testrun: log.write('Stage created for ' + tempStage + '\r\n')
                    if thisClip.stereo != None:
                        stereoStageCount += 1
                    stageList.append(tempStage)
                    # store track number in clip info
                    thisClip.track = stageList.index(tempStage)
            # if stagelist uninitialized, then create it
            else:
                if not testrun: log.write('Stage created for ' + tempStage + '\r\n')
                stageList.append(tempStage)
                thisClip.track = 0
                if thisClip.stereo != None:
                        stereoStageCount += 1

    if not testrun: log.write('All images from playlist read into clips\r\n')
    
    # for each clip, go through each image and copy over to dds
    for c in clipList:                
        for frame in range (0, c.getLength()):
            # if testrun, check that playlist file exists
            if testrun:
                # if image path is invalid
                if not os.access(c.imagesIn[frame], os.F_OK):
                    print 'TESTRUN: INVALID file in playlist: ' + c.imagesIn[frame]
                    return False
                else:
                    print 'TESTRUN: Good file in playlist: ' + c.imagesIn[frame]
                    continue                    
            else:
                try:
                    server.copyFile(c.imagesIn[frame], c.imagesOut[frame], log)
                except:
                    if not testrun: log.write('ERROR: failed to copy ' + c.imagesIn[frame] + ' to ' + c.imagesOut[frame] + '\r\n')
        
    # for each clip, figure out if it's a stereo clip
    if not testrun: log.write('Checking to see if each clip is part of a stereo pair\r\n')
    for c in clipList:
        if c.stereo != None:
            nameC = c.name
            # get name less stereo string value
            nameC = nameC[:len(nameC)-len(c.stereo)]
            for d in clipList:     
                if d.stereo != None:       
                    nameD = d.name
                    # get name less stereo string value
                    nameD = nameD[:len(nameD)-len(d.stereo)]
                
                    # is the clip a stereo clip, does it not have the same stereo tag as another with the same name                
                    if nameC == nameD and c.stereo != d.stereo and c.format == d.format and c.stereoChecked == False and d.stereoChecked == False:
                        #print nameC + ' c.stereoChecked = ' + str(c.stereoChecked)
                        #print nameD + ' d.stereoChecked = ' + str(d.stereoChecked)
                        c.stereoChecked = True
                        d.stereoChecked = True
                        if not testrun:
                            log.write('Clip ' + nameC + ' is a stereo clip\r\n')
                            log.write('Clip ' + nameD + ' is a stereo clip\r\n')
                        # if clip has a frame range
                        if c.getLength() > 1:
                            c.stereo = nameD + d.stereo + '.%04d' + d.format
                            d.stereo = nameC + c.stereo + '.%04d' + c.format
                        else:
                            temp = c.stereo
                            c.stereo = nameD + d.stereo + '.' + d.format
                            d.stereo = nameC + temp + '.' + c.format
                        break
    
    # create xml file for clipster project
    # initialize list to store lines of xml info
    outCmd = []

    # opening lines of a clipster project
    if not testrun: log.write('Creating clipster project\r\n')
    xmlFirst = '<?xml version="1.0" encoding="UTF-8"?>'
    outCmd.append(xmlFirst + '\r\n')        
    outCmd.append('<CLIPSTER >\r\n')
    if not testrun: ('Creating cliplist\r\n')
    outCmd.append('<CLIPLIST>\r\n')
    outCmd.append('<SORT ASCENDING="true">\r\n<KEY TYPE="" />\r\n<KEY TYPE="" />\r\n<KEY TYPE="" />\r\n</SORT>\r\n')
    
    bin = '/'

    # for each clip in the clip list, bring it into a bin in Fuze    
    for c in clipList:

        if not testrun: log.write('Clip ' + c.name + ' being imported into bin ' + bin + '\r\n')
        
        outCmd.append('<CLIP TYPE="directory">\r\n')
        outCmd.append('<NAME>' + bin + '</NAME>\r\n')
        outCmd.append('</CLIP>\r\n')
        outCmd.append('<CLIP TYPE="video">\r\n')

        # if clip is a list of frames        
        outCmd.append('<NAME>' + bin + c.name + '</NAME>\r\n')
        outCmd.append('<PATH VALUE="' + outPath + '/">' + outPath + '/</PATH>\r\n')

        if c.frames is None:
            outCmd.append('<FILENAME VALUE="' + c.name + '.' + c.format + '">' + c.name + '.' + c.format + '</FILENAME>\r\n')
        else:
            outCmd.append('<FILENAME VALUE="' + c.name + c.frames + '.' + c.format + '">' + c.name + c.frames + '.' + c.format + '</FILENAME>\r\n')            
            
        outCmd.append('<RANGE START="' + str(c.start) + '" END="' + str(c.end) + '" IN="' + str(c.start) + '" OUT="' + str(c.end) + '" />\r\n')
        if c.format == 'mov':
            outCmd.append('<COLOR MODE="head" />\r\n')
        outCmd.append('</CLIP>\r\n')
        
    outCmd.append('</CLIPLIST>\r\n')
    if not testrun: log.write('Finished creating cliplist\r\n')
    
    # determine number of tracks by finding the number of stages in the clip list, and subtracting half the number of stereo stages
    if stereoStageCount > 1:
        numStages = str(len(stageList)+stereoStageCount/2)
    else:
        numStages = str(len(stageList)+stereoStageCount + 1)
    # start tracks
    if not testrun: log.write('Importing clips into tracks\r\n')
    
    outCmd.append('<TIMELINE DEVICE="dvsvideo" JACK="VideoOut" TYPE="video" FLAGS="rtmode,audioscrubbing" RATE="23976p" LRATE="23976sF" TRACKS="' + numStages + '" ATRACKS="' + numStages + '">\r\n')
    outCmd.append('<TIMELINESETTINGS SETTINGSTYPE="output" DEVICE="dvsvideo" TYPE="video,sF,274,yuvhead" LFRATE="23976" RASTER="smpte274m2398sf">\r\n')
    if stereoStageCount > 0:
        outCmd.append('<STEREOSCOPIC3DOUTPUT ENABLED="true" />\r\n')
    outCmd.append('</TIMELINESETTINGS>\r\n')
    
    # for each stage, create a track and add clips with the same stage
    currentTrack = 0
    currentPriTrack = 1
    currentSecTrack = 0
    for stage in stageList:
        inPos = 0
        caughtStereo = False
        if not testrun: log.write('Creating track for ' + stage + '\r\n')
        outCmd.append('<TRACK NUMBER="' + str(currentTrack) + '" HEIGHT="55">\r\n')
        for c in clipList:
            
            if c.track != stageList.index(stage) or c.tracked:
                continue
                
            if c.stereo != None:
                outCmd.append('<NUMBER CUR="' + str(currentTrack) + '" PRI="' + str(currentPriTrack) + '" SEC="' + str(currentSecTrack) + '" />\r\n')
                outCmd.append('<EYEMODE CUR="both" PRI="left" SEC="right" />\r\n')
                
            clipLength = c.getLength()

            # increment current out position by the clip length
            if clipLength > 1:
                outPos = inPos + clipLength
            else:
                outPos = inPos + c.end
            
            outCmd.append('<CLIP SOURCE="' + c.bin + c.name + '" TYPE="video">\r\n')        
            outCmd.append('<POSITION START="' + str(inPos) + '" STOP="' + str(outPos) + '" SPEED="1.000000" />\r\n')
            #
            inPos = outPos            
            outCmd.append('<OFFSET IN="' + str(c.start) + '.000000" OUT="' + str(c.end) + '.000000" />\r\n')            

            # if clip is part of a stereo pair            
            if c.stereo != None:
                caughtStereo = True
                tempIndex = None
                for d in clipList:
                    tempStereoName = ''
                    # if clip is a single movie or list of images
                    if d.getLength() > 1:
                        tempStereoName = d.name+ '.%04d' + d.format
                    else:
                        tempStereoName = d.name + '.' + d.format
                    # if clip has a pair in the clip list, store the match's position in a temp var
                    if c.stereo == tempStereoName:
                        tempIndex = clipList.index(d)
                        break
                if tempIndex == None:
                    print 'WARNING: unable to add images for [' + c.name + '.' + c.format + '] to a clipster timeline.'
                    if not testrun: log.write('WARNING: unable to add images for [' + c.name + '.' + c.format + '] to a clipster timeline.\r\n')
                    outCmd = outCmd[:len(outCmd)-6]
                    break
                # if clip has not already been added to a track
                if not clipList[tempIndex].tracked:
                    clipList[tempIndex].tracked = True
                    outCmd.append('<TRACK NUMBER="' + str(currentTrack) + '" />\r\n')
                    outCmd.append('<EYE MODE="right" LAST="true">\r\n')
                    outCmd.append('<OFFSET IN="' + str(clipList[tempIndex].start) + '.000000" OUT="' + str(clipList[tempIndex].end) + '.000000" />\r\n')
                    outCmd.append('<SOURCE NAME="' + clipList[tempIndex].bin + clipList[tempIndex].name + '" />\r\n')
                    outCmd.append('</EYE>\r\n')                       

            # mark clip as added to a track            
            c.tracked = True
            outCmd.append('</CLIP>\r\n')
        
        outCmd.append('</TRACK>\r\n')
        if not testrun: log.write('Finished creating track for ' + stage + '\r\n')

        # increment Tracks        
        currentTrack += 1
        currentSecTrack = stageList.index(stage)+1
        currentPriTrack = currentSecTrack + 1
    
    outCmd.append('</TIMELINE>\r\n')
    if not testrun: log.write('Finished importing clips into tracks\r\n')
    outCmd.append('</CLIPSTER>\r\n')
    if not testrun: log.write('Finished creating clipster project\r\n')
    # end of xml for clipster creation

    # if a testrun, and if made it through clipster project creation
    # then end and return okay
    if testrun:
        print 'TESTRUN: Able to create clipster project'
        return True

    # temp location on dts servers
    tempPath = SERVER_TEMP + '\\' + tempName + '.cp'
    fout = open(tempPath, 'w')
    if not testrun: log.write('Opened temp file ' + tempPath + ' to write clipster file\r\n')
    for cmd in outCmd:
        fout.write(cmd)
    fout.close()
    if not testrun: log.write('Closed temp file\r\n')
    # copy temp file on server to dds drive
    server.copyFile(tempPath, outPath + '\\' + project + '.cp', log)
    if not testrun:
        log.write('Finished importing playlist into clipster project\r\n')
        log.close()

    return True
        
if __name__ == "__main__":
    main()

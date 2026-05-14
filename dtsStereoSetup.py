import maya.cmds as cmds
import maya.OpenMaya as OM
import maya.mel as MM
import math

########################################
DEG2RAD = math.pi/180.0
RAD2DEG = 180.0/math.pi

imageWidth = 1920
imageHeight = 1080

selection = cmds.ls(selection=True)[0]
cam = 'sceneCam_camera_ctrl'

startFrame = int(cmds.getAttr('defaultRenderGlobals.startFrame'))
endFrame = int(cmds.getAttr('defaultRenderGlobals.endFrame'))
byFrame = int(cmds.getAttr('defaultRenderGlobals.byFrame'))
################################################################################

################################################################################
# Switch the renderer to RenderMan
if not cmds.pluginInfo('RenderMan_for_Maya', q=True, l=True):
    cmds.loadPlugin('RenderMan_for_Maya')
MM.eval('setCurrentRenderer renderMan; rmanChangeRendererUpdate;')

if not cmds.pluginInfo('nearestPointOnMesh', query=True, l=True):
    cmds.loadPlugin('nearestPointOnMesh')
    
if not cmds.pluginInfo('decomposeMatrix.mll', q=True, l=True):
    cmds.loadPlugin('decomposeMatrix.mll')
################################################################################

################################################################################
################################################################################
################################################################################
#MM.eval('unifiedRenderGlobalsWindow;')
#MM.eval('rmanSetPtRenderDspy rmanFinalOutputGlobals0 "Tiff16 (tif)";')
MM.eval('unifiedRenderGlobalsWindow;')
MM.eval('rmanSetAttr("rmanFinalOutputGlobals0","rman__riopt__Display_type","tiff");')
MM.eval('rmanSetPtRenderDspy rmanFinalOutputGlobals0 "Tiff16 (tif)";')

quant = MM.eval('rmanGetImageFormatQuantization("Tiff16 (tif)");')
dither = MM.eval('rmanGetImageFormatDither("Tiff16 (tif)");')
if dither != "": print True


if MM.eval('attributeExists rman__param__ptrender_depth rmanFinalOutputGlobals0'):
    MM.eval('rmanSetPtRenderDspy rmanFinalOutputGlobals0 "Tiff16 (tif)";')
else:
    quant = MM.eval('rmanGetImageFormatQuantization("Tiff16 (tif)");')
    dither = MM.eval('rmanGetImageFormatDither("Tiff16 (tif)");')
    if quant != "":
        MM.eval('rmanAddAttr rmanFinalOutputGlobals0 rman__riopt__Display_quantize ' + quant + ';')
        MM.eval('rmanAddAttr rmanFinalOutputGlobals0 rman__riopt__Display_dither ' + dither + ';')
    else:
        cmds.deleteAttr('rmanFinalOutputGlobals0.rman__riopt__Display_quantize')
        cmds.deleteAttr('rmanFinalOutputGlobals0.rman__riopt__Display_dither')
################################################################################
################################################################################
################################################################################

cmds.setAttr('defaultRenderGlobals.startFrame', startFrame)
cmds.setAttr('defaultRenderGlobals.endFrame', endFrame)
cmds.setAttr('defaultRenderGlobals.byFrameStep', byFrame)
cmds.setAttr('defaultResolution.width', imageWidth)
cmds.setAttr('defaultResolution.height', imageHeight)
cmds.setAttr('defaultResolution.lockDeviceAspectRatio', 0)
cmds.setAttr('defaultResolution.imageSizeUnits', 0)
cmds.setAttr('defaultResolution.dotsPerInch', 72)
cmds.setAttr('defaultResolution.pixelDensityUnits', 0)
cmds.setAttr('defaultResolution.deviceAspectRatio', 1.778)
cmds.setAttr('defaultResolution.pixelAspect', 1)
cmds.setAttr('defaultRenderGlobals.extensionPadding', 4)
cmds.setAttr('topShape.renderable', 0)
cmds.setAttr('frontShape.renderable', 0)
cmds.setAttr('sideShape.renderable', 0)
cmds.setAttr('perspShape.renderable', 0)
MM.eval('insertKeywordMenuCallback "<Scene>";')
cmds.setAttr('defaultRenderGlobals.preMel', '', type='string')
cmds.setAttr('defaultRenderGlobals.postMel', '', type='string')
cmds.setAttr('defaultRenderGlobals.preRenderLayerMel', '', type='string')
cmds.setAttr('defaultRenderGlobals.postRenderLayerMel', '', type='string')
cmds.setAttr('defaultRenderGlobals.preRenderMel', '', type='string')
cmds.setAttr('defaultRenderGlobals.postRenderMel', '', type='string')

##################
# Renderman Advanced Settings
##################
cmds.setAttr('renderManGlobals.rman__toropt___shaderCleanupJob', 1)
cmds.setAttr('renderManGlobals.rman__toropt___renderDataCleanupJob', 0)
cmds.setAttr('renderManGlobals.rman__toropt___textureCleanupJob', 1)
cmds.setAttr('renderManGlobals.rman__toropt___ribCleanupJob', 1)
cmds.setAttr('renderManGlobals.rman__toropt___renderDataCleanupFrame', 0)
cmds.setAttr('renderManGlobals.rman__toropt___textureCleanupFrame', 1)
cmds.setAttr('renderManGlobals.rman__toropt___ribCleanupFrame', 1)
################################################################################

################################################################################
# turn on Smooth Mesh Preview for all geometry
objects = cmds.ls()
print objects
for object in objects:
    try:
        cmds.setAttr(object+'.displaySubdComps', 0)
    except:
        continue
    try:
        cmds.displaySmoothness(object, polygonObject=2) 
    except:
        continue
    try:
        cmds.setAttr(object+'.useSmoothPreviewForRender', 1)
    except:
        continue
##########################################################################################

##########################################################################################
closestLoc = cmds.spaceLocator(n='closestPoint')
cmds.addAttr(closestLoc, ln="closestOrthoDistance", at='double', min=0)
cmds.setAttr(closestLoc[0]+'.closestOrthoDistance', e=True, keyable=True)
cmds.addAttr(closestLoc, ln="depthShaderRange", at='double', min=0)
cmds.setAttr(closestLoc[0]+'.depthShaderRange', 10,  e=True, keyable=True)
camAov = cmds.camera(cam, q=True, hfv=True)

dmCam = cmds.createNode('decomposeMatrix')
cmds.connectAttr(cam+'.worldMatrix[0]', dmCam+'.inputMatrix', f=True)
camLoc = cmds.spaceLocator(n='camLoc')
cmds.expression(s=camLoc[0]+'.translateX = `getAttr -t (frame) ' + dmCam + '.outputTranslateX`;')
cmds.expression(s=camLoc[0]+'.translateY = `getAttr -t (frame) ' + dmCam + '.outputTranslateY`;')
cmds.expression(s=camLoc[0]+'.translateZ = `getAttr -t (frame) ' + dmCam + '.outputTranslateZ`;')

dmFrustrum = cmds.createNode('decomposeMatrix')
camFrustrum = 'sceneCam_frustum_cluster_ctrl'
cmds.connectAttr(camFrustrum+'.worldMatrix[0]', dmFrustrum+'.inputMatrix', f=True)
camTumblePivot = cmds.getAttr(cam+'Shape.tumblePivot')
camTumblePivotLoc = cmds.spaceLocator(n='camTumblePivot')
cmds.move(camTumblePivot[0][0], camTumblePivot[0][1], camTumblePivot[0][2], camTumblePivotLoc, absolute=True)
cmds.expression(s=camTumblePivotLoc[0]+'.translateX = `getAttr -t (frame) ' + dmFrustrum + '.outputTranslateX`;')
cmds.expression(s=camTumblePivotLoc[0]+'.translateY = `getAttr -t (frame) ' + dmFrustrum + '.outputTranslateY`;')
cmds.expression(s=camTumblePivotLoc[0]+'.translateZ = `getAttr -t (frame) ' + dmFrustrum + '.outputTranslateZ`;')

camOrthoLoc = cmds.spaceLocator(n='camOrtho')

cmds.select(selection)
meshes = cmds.listRelatives(selection, allDescendents=True, type='mesh', fullPath=True)
##########################################################################################

##########################################################################################
#for frame in range(startFrame, endFrame+1):
for frame in range(startFrame, endFrame+1):
    cmds.currentTime(frame)
    
    closestP = []
    closestOrthoDistance = 100000000
    
    camV = OM.MVector(cmds.getAttr(camLoc[0]+'.translateX'), cmds.getAttr(camLoc[0]+'.translateY'), cmds.getAttr(camLoc[0]+'.translateZ'))
    camTumbleV = OM.MVector(cmds.getAttr(camTumblePivotLoc[0]+'.translateX'), cmds.getAttr(camTumblePivotLoc[0]+'.translateY'), cmds.getAttr(camTumblePivotLoc[0]+'.translateZ'))
    tumble2Cam = camTumbleV-camV
    tumble2Cam.normalize()
    
    for mesh in meshes:
        cpom = MM.eval('nearestPointOnMesh ' + mesh + ';')
        constrainPt = cmds.createNode('transform', name='nearestPointOnMesh')
        cmds.setAttr(constrainPt+".inheritsTransform", False, lock=True)
        MM.eval('delete `pointConstraint ' + cam + ' ' + constrainPt + '`;')
        MM.eval('delete `orientConstraint ' + cam + ' ' + constrainPt + '`;')
        MM.eval('delete `geometryConstraint ' + mesh + ' ' + constrainPt + '`;')
        cmds.connectAttr(constrainPt+".t", cpom+".inPosition")    
        
        cpomPos = cmds.getAttr(constrainPt+'.translate')
        cpomV = OM.MVector(cpomPos[0][0], cpomPos[0][1], cpomPos[0][2])
        checkV = (cpomV-camV)
        length = checkV.length()             
        checkV.normalize()
        
        ang = math.acos(tumble2Cam*checkV)
        orthoLength = length * math.cos(ang)
        
        if orthoLength > 0 and orthoLength < closestOrthoDistance:
            closestOrthoDistance = orthoLength
            closestP = [cpomV.x, cpomV.y, cpomV.z]
            
        cmds.delete(constrainPt)
        cmds.delete(cpom)
        
    cmds.move(closestP[0], closestP[1], closestP[2], closestLoc, absolute=True)
    cmds.setKeyframe(closestLoc[0]+'.translate')
    cmds.setAttr(closestLoc[0]+'.closestOrthoDistance', closestOrthoDistance)
    cmds.setKeyframe(closestLoc[0]+'.closestOrthoDistance')
    
    tumble2Cam.x = tumble2Cam.x*closestOrthoDistance
    tumble2Cam.y = tumble2Cam.y*closestOrthoDistance
    tumble2Cam.z = tumble2Cam.z*closestOrthoDistance
    camOrthoV = camV + tumble2Cam
    cmds.move(camOrthoV.x, camOrthoV.y, camOrthoV.z, camOrthoLoc, absolute=True)
    cmds.setKeyframe(camOrthoLoc[0]+'.translate')
##########################################################################################

##########################################################################################    
def zDepthShader(selection, closest):
	surfaceShader = cmds.shadingNode('surfaceShader', asShader=True, name=selection+'SurfaceShader')
	surfaceShaderSG = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=selection+'SurfaceShaderSG')
	reverse = cmds.shadingNode('reverse', asUtility=True, name=selection+'Reverse')
	setRange = cmds.shadingNode('setRange', asUtility=True, name=selection+'SetRange')
	multDiv = cmds.shadingNode('multiplyDivide', asUtility=True, name=selection+'MultiplyDivide')
	samplerInfo = cmds.shadingNode('samplerInfo', asUtility=True, name=selection+'SamplerInfo')
	cmds.connectAttr(setRange+'.outValueZ', reverse+'.inputZ', force=True)
	cmds.connectAttr(surfaceShader+'.outColor', surfaceShaderSG+'.surfaceShader', force=True)
	cmds.connectAttr(reverse+'.outputZ', surfaceShader+'.outColorR', force=True)
	cmds.connectAttr(reverse+'.outputZ', surfaceShader+'.outColorG', force=True)
	cmds.connectAttr(reverse+'.outputZ', surfaceShader+'.outColorB', force=True)
	cmds.connectAttr(multDiv+'.output', setRange+'.value', force=True)
	
	cmds.setAttr(multDiv+'.input2Z', -1)
	cmds.setAttr(setRange+'.maxZ', 1)
	cmds.connectAttr(samplerInfo+'.pointCameraZ', multDiv+'.input1Z', force=True)
	cmds.expression(s=setRange+'.oldMinZ = `getAttr -t (frame) ' + closest +'.closestOrthoDistance' + '`;')
	cmds.expression(s=setRange+'.oldMaxZ = `getAttr -t (frame) ' + closest +'.closestOrthoDistance' + '` + `getAttr -t (frame) ' + closest +'.depthShaderRange' + '`;')
	cmds.setAttr(setRange+'.maxZ', 1)
	cmds.select(selection)
	cmds.sets(e=True, forceElement=surfaceShaderSG)
	return surfaceShader

zDepthShader(selection, closestLoc[0])


#depthRangeLoc = cmds.spaceLocator(n='depthRangeExport')
#cmds.expression(s=depthRangeLoc[0] + '.translateX = `getAttr -t (frame) ' + closestLoc[0] + '.closestOrthoDistance' + '`;')
#cmds.expression(s=depthRangeLoc[0] + '.translateY = `getAttr -t (frame) ' + closestLoc[0] + '.closestOrthoDistance` + `getAttr -t (frame) ' + closestLoc[0] + '.depthShaderRange' + '`;')
#cmds.bakeResults(depthRangeLoc[0] + '.translateX', sampleBy=1, time=(startFrame,endFrame), preserveOutsideKeys=True, sparseAnimCurveBake=0)
#cmds.bakeResults(depthRangeLoc[0] + '.translateY', sampleBy=1, time=(startFrame,endFrame), preserveOutsideKeys=True, sparseAnimCurveBake=0)

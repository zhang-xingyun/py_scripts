#!/usr/bin/python

import logging 

from suds.client import *
from suds.wsse import *
from datetime import timedelta
from optparse import OptionParser

import sys
reload(sys)
sys.setdefaultencoding('UTF-8')



##########
# Basic operational SUDs stuff
##########
class Services :
	def __init__(self) :
		self.host = "http://127.0.0.1"
		self.port = "8080"
	
	def setHost(self, in_host) :
		self.host = in_host

	def getHost(self) :
		return self.host

	def setPort(self, in_port) :
		self.port = in_port
	
	def getPort(self) :
		return self.port

	def getURL(self, in_url) :
		return self.host + ":" + self.port + "/ws/v9/" + in_url + "?wsdl"

	def setServicesSecurity(self, client, in_user, in_pass) :
		security = Security()
		token = UsernameToken(in_user, in_pass)
		security.tokens.append(token)
		client.set_options(wsse=security)
		
##########
# Configuration Service (WebServices)
##########
class ConfigurationService(Services) :
	def __init__(self, in_host, in_port) :
		#print "Starting configurationservice\n"
		self.setHost(in_host)
		self.setPort(in_port)
		self.client = Client(self.getURL("configurationservice"))
	
	def setSecurity(self, in_user, in_pass) :
		self.setServicesSecurity(self.client, in_user, in_pass)

	def create(self, in_obj) :
		return self.client.factory.create(in_obj)

	def getSnapshotsForStream(self, stream_name) :
		sido = self.client.factory.create("streamIdDataObj")
		sido.name = stream_name
		snapshots = self.client.service.getSnapshotsForStream(sido)
		return snapshots

	def getSnapshotInformation(self, snapshots) :
		snapshot_info = self.client.service.getSnapshotInformation(snapshots)
		return snapshot_info

	def getComponent(self, component_name) :
		# create a component identifier
		ciddo = self.client.factory.create("componentIdDataObj")
		ciddo.name = component_name
		return self.client.service.getComponent(ciddo)

	def doNotify(self, subscribers) :
		subject = "Notification of Receipt of Defects"
		message  = "<p>Your junk is broken</p><p>It is still broken</p>"
		message += "<a href=\"http://www.wunderground.com\">Wunderground</a>"
		self.client.service.notify(subscribers, subject, message)

##########
# Defect Service (WebServices)
##########
class DefectService(Services) :
	def __init__(self, in_host, in_port) :
		#print "Starting DefectService\n"
		self.setHost(in_host)
		self.setPort(in_port)
		self.client = Client(self.getURL("defectservice"))
	
	def setSecurity(self, in_user, in_pass) :
		self.setServicesSecurity(self.client, in_user, in_pass)

	def create(self, in_obj) :
		return self.client.factory.create(in_obj)

	# This method obtains CIDs that exist in a stream
	# with a given set of one or more "Classification(s)"
	# AND found by a given set of one or more "Checker(s)" 
	def getSnapshotCIDs(self, stream_name) :
		# Create a stream identifier
		sido = self.client.factory.create("streamIdDataObj")
		sido.name = stream_name

		filterSpec = self.client.factory.create("mergedDefectFilterSpecDataObj")

		# add set of Stream(s) to be included in defect selection,
		# to the filter object
		ssfsdo = self.client.factory.create("streamSnapshotFilterSpecDataObj")
		ssfsdo.streamId = sido
		filterSpec.streamSnapshotFilterSpecIncludeList.append(ssfsdo)

		# Add set of defect Classification(s) to be
		# included in defect selection to the filter the object 
		filterSpec.classificationNameList.append("Pending")
		
		# Add set of Checkers to be included in defect selection
		# to the filter object
		csfsdo = self.client.factory.create("checkerSubcategoryFilterSpecDataObj")
		csfsdo.checkerName = "FORWARD_NULL"
		filterSpec.checkerSubcategoryFilterSpecList.append(csfsdo)

		# specify if only the defects that appear in all the
		# snapshots to be included in defect selection
		# (otherwise defects that occur in any snapshots will be included) 
		filterSpec.streamSnapshotIncludeAll = False

		# make the WebServices call to get the defects 
		# matching the filter critera
		return self.client.service.getCIDsForStreams(sido, filterSpec)

	def getMergedDefectsForStreams(self, stream_name) :

		# create a filter to access the data we need for each of the CIDs
		#filterSpecDO = self.client.factory.create("snapshotScopeDefectFilterSpecDataObj")
		#filterSpec.cidList = cids

		# create a stream identifier
                streamIdDO = self.client.factory.create('streamIdDataObj')
                streamIdDO.name=stream_name
                
                # create a filter to access the data we need for each of the CIDs
                filterSpecDO = self.client.factory.create('snapshotScopeDefectFilterSpecDataObj')

                # create a page specification object
                pageSpecDO = self.client.factory.create('pageSpecDataObj')
                pageSpecDO.pageSize=500
                pageSpecDO.sortAscending = True             
                pageSpecDO.startIndex=0
                #snapshotScopeDO=defectServiceClient.client.factory.create('mergedDefectFilterSpecDataObj')
                #snapshotScopeDO.showSelector='last()'
                #print('get1')
                mergedDefects = self.client.service.getMergedDefectsForStreams(streamIdDO, filterSpecDO, pageSpecDO)
                #print('get2')
                return mergedDefects

		# gather the information from all of the CIDs in our list
		#return_cids = self.client.service.getMergedDefectsForStreams(sido, filterSpec, pageSpec)
		#return return_cids

	def getStreamDefectList(self, cid, stream_name) :

                mergedDefectIdDO = self.client.factory.create('mergedDefectIdDataObj')
                mergedDefectIdDO.cid=cid
                streamIdDO = self.client.factory.create('streamIdDataObj')
                streamIdDO.name=stream_name
                streamsList = [streamIdDO]
                filterSpecDO = self.client.factory.create('streamDefectFilterSpecDataObj')
                filterSpecDO.includeDefectInstances = True
                filterSpecDO.includeHistory = True
                filterSpecDO.streamIdList = streamsList
                return self.client.service.getStreamDefects(mergedDefectIdDO, filterSpecDO)#, streamsList)

	def updateDefect(self, defectID, updateProperties) :
		# create a stream identifier
		return self.client.service.updateStreamDefects(defectID, updateProperties)

	def newDefectStateSpecDataObj(self) :
		return self.client.factory.create("defectStateSpecDataObj")


##########
# Main Entry Point
##########
def main() :
	# Configuration Information
	target_stream = options.stream
	port = options.port
	hostname = options.hostname
	username = options.username
	password = options.password

	# Begin by getting the configuration service 
	cs = ConfigurationService("http://" + hostname, port)
        #print('1')
	cs.setSecurity(username, password)
        #print('2')
	# get the snapshots in this stream
	ssfs = cs.getSnapshotsForStream(target_stream)
        #print('3')
	# if we do not have any snapshots, simply return with a -1
	ln = len(ssfs);
	if ln < 1 :
		return -1

	# Begin defect service
	ds = DefectService("http://" + hostname, port)
	ds.setSecurity(username, password)
        #print('4')
        #print(target_stream)
	# get CIDs from all snapshots in this stream
	#cids = ds.getSnapshotCIDs(target_stream)

	# get merged defects for the gathered CIDs 
	cid_list = ds.getMergedDefectsForStreams(target_stream)
	print "CID count:",len(cid_list.mergedDefects)

	i=0
	for cid in cid_list.mergedDefects :
		# get the actual defect instances 
		# for each merged defect CID
		defects = ds.getStreamDefectList(cid.cid, target_stream)
		
		for defect in defects :
			
			for defectInstance in defect.defectInstances :
				print "CID:",defect.cid
				print "Impact:",defectInstance.impact.displayName 
				i=i+1
				for event in defectInstance.events :
					if (event.main) :
						print "LINE:", event.lineNumber, "FILE:", event.fileId.filePathname, "DESC:", event.eventDescription
						print " "
	print "i=",i




##########
# Should be at bottom of "Main Entry Point".  Points the script back up into
# the appropriate entry function
##########
parser = OptionParser()
parser.add_option("-c", "--host", dest="hostname", 
                  help="Set hostname or IP address of CIM",
				  default="127.0.0.1")
parser.add_option("-p", "--port", dest="port",
				  help="Set port number to use",
				  default="8080")
parser.add_option("-u", "--user", dest="username",
				  help="Set username to perform query",
				  default="admin")
parser.add_option("-a", "--password", dest="password",
				  help="Set password token for the username specified",
				  default="coverity")
parser.add_option("-s", "--stream", dest="stream",
				  help="Set target stream for access",
				  default="")
(options, args) = parser.parse_args()
if __name__ == "__main__" :
	main()



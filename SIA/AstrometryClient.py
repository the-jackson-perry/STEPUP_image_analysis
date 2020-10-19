# This toolkit was made to wrap the Astrometry.net API 
# It can be used to upload an image from the file system and download the 
# corresponding "new-image.fits" file
#
# Maintained by Brendan Sackett (bhs25@pitt.edu)

import json
import os
import random
import requests
import sys
import time

# Object that represents a logged in user of Astrometry.net
# In order to upload an image, a valid API-key needs to be provided
# A logged in user can find their API-key on nova.Astrometry.net by clicking the
# 'Dashboard' tab, then clicking 'My profile'. The API-key should appear 
# under 'Account Info'
class AstrometryClient:
    # Constructor for Astrometry user
    # Args:
    #   apikey: unique API-key of the nova.Astrometry.net user
    # Returns:
    #   AstrometryClient object corresponding to specified user
    def __init__(self, apikey=None):
        self.apikey = apikey
        self.session = self.__get_session_key()
        self.subid = None
        self.jobid = None
    
    # Method to upload file to Astrometry.net.
    # Args: 
    #   filepath: path to image being uploaded
    # Returns:
    #   True if upload was successful and then sets class variable 'subid',
    #   False if upload fails and sets 'subid' to None
    def upload_image(self,filepath):
        if self.session is None:
            print("User must provide valid API-key to upload an image.")
            return False

        # Read in image as bytes
        try:
            with open(filepath, 'rb') as file:
                file_args = (filepath, file.read())
        except IOError:
            print("%s not accessible" % file)
            return False

        # Configurations for uploading images to Astrometry
        args = {"allow_commercial_use": "d", "allow_modifications": "d",
                "publicly_visible": "y", 'session' : self.session }

        url, headers, data = self.__prep_upload_image(args, file_args)
        response = self.__post(url, headers=headers, data=data)
        
        if response is not None:
            if response["status"] == "success":
                print("Upload was successful.")
                self.subid = response['subid']
                return True
        
        print("Upload failed.")
        self.subid = None
        return False
    
    # Method to check if a submission has left the queue and been assigned a job 
    # Args:
    #   None
    # Returns:
    #   True if the submission has left the submission queue
    #   False if otherwise
    def submission_is_finished(self):
        if self.subid is None:
            print("There was no submission to check. Please upload an image.")
            return False
        
        response = self.__get('http://nova.astrometry.net/api/submissions/%s' % self.subid)
        if response is not None:
            jobs = response["jobs"]
            if jobs and jobs != [None]:
                self.jobid = jobs[0]
                return True
        
        self.jobid = None
        return False
    
    # Method to wait until submission has left submission queue 
    # Args:
    #   None
    # Returns:
    #   None
    def wait_for_submission_finished(self):
        while((not self.submission_is_finished()) and (self.subid is not None)):
            time.sleep(5)
    
    # Method to check if job has finished processing image 
    # Args:
    #   None
    # Returns:
    #   True if the submission has left the submission queue
    #   False if otherwise
    def job_is_finished(self):
        if self.jobid is None:
            print("There is no job processing. Please upload an image.")
            return False
        
        response = self.__get('http://nova.astrometry.net/api/jobs/%s' % self.jobid)
        if response is not None:
            if response["status"] == "success":
                return True
        
        return False
        
    # Method to wait until job has finished processing 
    # Args:
    #   None
    # Returns:
    #   None
    def wait_for_job_finished(self):
        while((not self.job_is_finished()) and (self.jobid is not None)):
            time.sleep(5)
    
    # Method to download new-image.fits file. If submission and job are not finished, 
    # the file will not be downloaded 
    # Args:
    #   None
    # Returns:
    #   True if the file could be downloaded
    #   False if otherwise
    def download_new_image_fits(self):
        if(not self.submission_is_finished()):
            print("Submisson %s has not left the submission queue yet." % self.subid)
            print(" Please wait for submission to complete")
            return False
        if(not self.wait_for_job_finished()):
            print("Job %s has not finished processing yet." % self.subid)
            print(" Please wait for image processing to complete")
            return False
            
        r = requests.get('http://nova.astrometry.net/new_fits_file/%s' % self.jobid)
        if r.status_code != 200:
            return False
            
        try:
            with open("new-image.fits", "wb") as f:
                f.write(r.content)
        except:
            print("Could not download new-image.fits")
            return False

        return True 

    # Private Wrapper to login to Astrometry.net using the user API-key
    # Args:
    #   None
    # Returns:
    #   A string representing the user session used to verify all requests that
    #   require a user to be logged in.
    #   If log in is not successful, None will be returned
    def __get_session_key(self):
        url = 'http://nova.astrometry.net/api/login'
        data={'request-json': json.dumps({"apikey": self.apikey})}
        response = self.__post(url, data=data)
        
        if response is not None:
            if response["status"] == "success":
                return response["session"]
        
        print("Login failed. Please check the API-key provided.")
        return None
        
    # Private Wrapper for requests.post method.
    def __post(self, url, headers=None, data=None):
        try:
            R = requests.post(url=url, headers=headers, data=data)
        except requests.ConnectionError:
            print("%s could not reach the internet. Request failed." % sys.argv[0])
            return None

        if R.status_code == 200:
            return R.json()
        else:
            return None
            
    # Private Wrapper for requests.get method.
    def __get(self, url):
        try:
            R = requests.get(url=url)
        except requests.ConnectionError:
            print("%s could not reach the internet. Request failed." % sys.argv[0])
            return None

        if R.status_code == 200:
            return R.json()
        else:
            return None
    
    # Private method to create a mutlipart/form-data post request to upload a file
    def __prep_upload_image(self, args, file_args):

        url="http://nova.astrometry.net/api/upload"
        
        json_args = json.dumps(args)

        # format a multipart/form-data
        if file_args is not None:
            boundary_key = ''.join([random.choice('0123456789') for i in range(19)])
            boundary = '===============%s==' % boundary_key
            headers = {'Content-Type':
                       'multipart/form-data; boundary="%s"' % boundary}
                       
            data_pre = (
                '--' + boundary + '\n' +
                'Content-Type: text/plain\r\n' +
                'MIME-Version: 1.0\r\n' +
                'Content-disposition: form-data; name="request-json"\r\n' +
                '\r\n' +
                json_args + '\n' +
                '--' + boundary + '\n' +
                'Content-Type: application/octet-stream\r\n' +
                'MIME-Version: 1.0\r\n' +
                'Content-disposition: form-data; name="file"; filename="%s"' % file_args[0] +
                '\r\n' + '\r\n')
                
            data_post = (
                '\n' + '--' + boundary + '--\n')
                
            data = data_pre.encode() + file_args[1] + data_post.encode()

        return url, headers, data
